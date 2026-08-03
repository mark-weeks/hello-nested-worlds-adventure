import { readdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const buildDirectory = fileURLToPath(
  new URL("../../static/app/", import.meta.url),
);
const textExtensions = new Set([".css", ".html", ".js"]);

async function normalizeDirectory(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = `${directory}/${entry.name}`;
    if (entry.isDirectory()) {
      await normalizeDirectory(path);
      continue;
    }

    const extension = entry.name.slice(entry.name.lastIndexOf("."));
    if (!textExtensions.has(extension)) continue;

    const source = await readFile(path, "utf8");
    const normalized = source.replace(/[\t ]+$/gm, "");
    if (normalized !== source) await writeFile(path, normalized);
  }
}

await normalizeDirectory(buildDirectory);
