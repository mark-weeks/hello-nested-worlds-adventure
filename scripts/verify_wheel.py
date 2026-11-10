"""Build and smoke-test the distributable application wheel.

Dependencies come from the ambient environment by design: this verifies
packaging, not dependency resolution; the lock files own that contract.

With no argument, builds a throwaway wheel and verifies it (the CI and
check.sh gate). Given a wheel path, verifies that exact file instead — the
Release workflow passes the artifact it is about to publish, so the smoke
result and the published bytes can never describe different wheels.
"""
from __future__ import annotations

import os
from email.parser import BytesParser
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PREFIX = "persistence/migrations/"
_SCHEMA_VERSIONS = list(range(1, 31))


def _run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def source_migrations(root: Path) -> dict[str, bytes]:
    """Every SQL migration in the source tree, keyed by its wheel path."""
    directory = root / "persistence" / "migrations"
    found: dict[str, bytes] = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.sql")):
            if path.is_file():
                found[f"{_MIGRATION_PREFIX}{path.name}"] = path.read_bytes()
    return found


def migration_versions(names: list[str]) -> list[int]:
    versions: list[int] = []
    for name in names:
        head = Path(name).name.split("_", 1)[0]
        versions.append(int(head))
    return versions


def assert_source_schema_inventory(source: dict[str, bytes]) -> None:
    """Ship versions 0001 through 0030, with blocks as the only migration 0030."""
    retired = f"{_MIGRATION_PREFIX}0030_cost_budget_names.sql"
    if retired in source:
        raise RuntimeError(f"source contains a deleted migration: {retired}")
    blocks = f"{_MIGRATION_PREFIX}0030_participant_blocks.sql"
    if blocks not in source:
        raise RuntimeError(f"schema 30 must include {blocks}")
    versions = migration_versions(list(source))
    if sorted(versions) != _SCHEMA_VERSIONS or len(versions) != len(_SCHEMA_VERSIONS):
        raise RuntimeError(
            "source migrations must be exactly versions 0001 through 0030, "
            f"found {sorted(versions)}"
        )


def assert_migration_inventory(packaged: dict[str, bytes], source: dict[str, bytes]) -> None:
    """The packaged SQL files are the source files, byte for byte.

    An extra file, a missing file, or a changed byte fails. A stale
    ``build/lib`` copy of a deleted migration is an extra file.
    """
    extra = sorted(set(packaged) - set(source))
    missing = sorted(set(source) - set(packaged))
    changed = sorted(
        name for name in source
        if name in packaged and packaged[name] != source[name]
    )
    problems: list[str] = []
    if extra or missing:
        problems.append(
            "migration inventory does not match source: "
            f"extra={extra or 'none'} missing={missing or 'none'}"
        )
    if changed:
        problems.append(f"migration bytes differ from source: {changed}")
    if problems:
        raise RuntimeError("; ".join(problems))


def assert_build_tree_migrations(root: Path) -> None:
    """Refuse a ``build/lib`` tree that still holds a deleted or edited migration.

    A missing file there is only an incomplete copy. An extra file or
    different bytes would be packed into the wheel.
    """
    staged = root / "build" / "lib" / "persistence" / "migrations"
    if not staged.is_dir():
        return
    source = source_migrations(root)
    packaged: dict[str, bytes] = {}
    for path in sorted(staged.glob("*.sql")):
        if path.is_file():
            packaged[f"{_MIGRATION_PREFIX}{path.name}"] = path.read_bytes()
    extra = sorted(set(packaged) - set(source))
    changed = sorted(
        name for name in packaged
        if name in source and packaged[name] != source[name]
    )
    if extra or changed:
        raise RuntimeError(
            "stale build/lib migrations do not match source; remove build/ and retry. "
            f"extra={extra or 'none'} changed={changed or 'none'}"
        )


def archive_migrations(archive: zipfile.ZipFile) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for name in archive.namelist():
        if name.startswith(_MIGRATION_PREFIX) and name.endswith(".sql"):
            found[name] = archive.read(name)
    return found


def main() -> None:
    supplied = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if supplied is not None and not supplied.is_file():
        raise RuntimeError(f"no wheel at {supplied}")
    with tempfile.TemporaryDirectory(prefix="enfolded-wheel-") as raw_tmp:
        tmp = Path(raw_tmp)
        if supplied is not None:
            wheel = supplied
        else:
            wheel_dir = tmp / "dist"
            wheel_dir.mkdir()
            source = source_migrations(ROOT)
            assert_source_schema_inventory(source)
            assert_build_tree_migrations(ROOT)
            _run(
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-cache-dir",
                "--no-build-isolation",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
                str(ROOT),
            )
            wheels = list(wheel_dir.glob("enfolded-*.whl"))
            if len(wheels) != 1:
                raise RuntimeError(f"expected one Enfolded wheel, found {wheels}")
            wheel = wheels[0]

        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            source = source_migrations(ROOT)
            assert_source_schema_inventory(source)
            assert_migration_inventory(archive_migrations(archive), source)
            metadata_names = [n for n in names if n.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise RuntimeError("wheel must contain one package metadata record")
            metadata_name = metadata_names[0]
            metadata = BytesParser().parsebytes(archive.read(metadata_name))
            if metadata.get("License-Expression") != "Apache-2.0":
                raise RuntimeError("wheel must declare the Apache-2.0 license")
            # The Anthropic SDK is an optional extra. A wheel that requires it
            # unconditionally cannot import or run the fixture provider without it.
            requires = metadata.get_all("Requires-Dist") or []
            base = [item for item in requires if "extra ==" not in item]
            if any(item.split(";", 1)[0].split(">", 1)[0].split("=", 1)[0]
                   .split("[", 1)[0].strip().lower() == "anthropic" for item in base):
                raise RuntimeError(
                    "anthropic must be an optional extra, not a required dependency"
                )
            extras = metadata.get_all("Provides-Extra") or []
            if "anthropic" not in extras:
                raise RuntimeError("wheel must provide the anthropic extra")
            extra_reqs = [
                item for item in requires
                if "anthropic" in item.lower() and 'extra == "anthropic"' in item
            ]
            if not extra_reqs:
                raise RuntimeError("wheel must declare the anthropic extra dependency")
            license_files = {"LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.txt"}
            if set(metadata.get_all("License-File", [])) != license_files:
                raise RuntimeError("wheel metadata must declare all license and notice files")
            info_dir = metadata_name.rsplit("/", 1)[0]
            for filename in license_files:
                license_path = f"{info_dir}/licenses/{filename}"
                browser_filename = filename if filename.endswith(".txt") else f"{filename}.txt"
                browser_path = f"static/app/{browser_filename}"
                if license_path not in names or browser_path not in names:
                    raise RuntimeError(f"wheel is missing distributed license/notice: {filename}")
                contents = archive.read(license_path)
                if not contents.strip() or archive.read(browser_path) != contents:
                    raise RuntimeError(f"browser and package license/notice differ: {filename}")
                if supplied is None and contents != (ROOT / filename).read_bytes():
                    raise RuntimeError(f"built wheel has stale license/notice: {filename}")
        required = {
            "main.py",
            "content_screen.py",
            "persistence/ideas_cli.py",
            "static/ideas.html",
            "static/interface.js",
            "static/interface.css",
            "static/navigation.js",
            "static/map.css",
            "static/ideas.js",
            "persistence/migrations/0025_community_ideas.sql",
            "persistence/migrations/0013_world_nodes.sql",
            "persistence/migrations/0026_idea_promotions.sql",
            "server/idea_promotion.py",
            "persistence/migrations/0024_history_read_indexes.sql",
            "persistence/recovery.py",
            "static/index.html",
            "static/score.js",
            "static/sensory.js",
            "static/interventions.js",
            "static/media/score/cello.mp3",
            "static/media/score/VSCO-LICENSE.txt",
            "static/media/places/orchard-v1.png",
            "static/media/places/chain-v1.png",
            "persistence/migrations/0027_expressive_interventions.sql",
            "multiverse/interventions_v1.py",
            "multiverse/interventions_v2.py",
            "multiverse/interventions_v3.py",
            "static/media/score/horn.mp3",
            "static/media/score/marimba.mp3",
            "static/media/score/bassoon.mp3",
            "static/media/score/glock.mp3",
            "static/media/score/pizzicato.mp3",
            "static/clientlogic.js",
            "static/app/index.html",
        }
        missing = sorted(required - names)
        if missing:
            raise RuntimeError(f"wheel is missing runtime files: {missing}")
        if not any(name.startswith("static/app/assets/") for name in names):
            raise RuntimeError("wheel is missing the built frontend bundle")
        if not any(name.endswith(".dist-info/entry_points.txt") for name in names):
            raise RuntimeError("wheel is missing the enfolded CLI entry point")

        venv_dir = tmp / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
        bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("enfolded.exe" if os.name == "nt" else "enfolded")
        _run(str(python), "-m", "pip", "install", "--no-deps", str(wheel))

        smoke_env = os.environ.copy()
        smoke_env["HOME"] = str(tmp / "home")
        smoke = (
            "import persistence; "
            "persistence.init_db(); "
            "from server.handlers import _STATIC_DIR; "
            "assert (_STATIC_DIR / 'index.html').is_file(); "
            "assert persistence._MIGRATIONS_DIR.is_dir(); "
            "from server import idea_promotion; "
            "assert (_STATIC_DIR / 'ideas.html').is_file(); "
            "assert (_STATIC_DIR / 'ideas.js').is_file(); "
            "assert persistence._connect().execute(\"SELECT count(*) FROM community_promotions\").fetchone()[0] == 0"
        )
        _run(str(python), "-c", smoke, cwd=tmp, env=smoke_env)
        _run(str(cli), "--help", cwd=tmp, env=smoke_env)
        _run(str(cli), "work-report", "--db",
             str(tmp / "home" / ".nested-worlds" / "worlds.db"), "--json",
             cwd=tmp, env=smoke_env)
        print(f"verified wheel: {wheel.name}")


if __name__ == "__main__":
    main()
