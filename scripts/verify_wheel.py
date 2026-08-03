"""Build and smoke-test the distributable application wheel."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="enfolded-wheel-") as raw_tmp:
        tmp = Path(raw_tmp)
        wheel_dir = tmp / "dist"
        wheel_dir.mkdir()
        _run(
            sys.executable,
            "-m",
            "pip",
            "wheel",
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
        required = {
            "main.py",
            "persistence/migrations/0013_world_nodes.sql",
            "static/index.html",
            "static/nodesound.js",
        }
        missing = sorted(required - names)
        if missing:
            raise RuntimeError(f"wheel is missing runtime files: {missing}")
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
            "assert persistence._MIGRATIONS_DIR.is_dir()"
        )
        _run(str(python), "-c", smoke, cwd=tmp, env=smoke_env)
        _run(str(cli), "--help", cwd=tmp, env=smoke_env)
        print(f"verified wheel: {wheel.name}")


if __name__ == "__main__":
    main()
