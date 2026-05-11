import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import assert from "node:assert/strict";

import { SpectrumPack } from "../src/index.js";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

test("creates, verifies, inspects, and unpacks a Spectrum pack", async () => {
  const root = await mkTempDir("spectrum-js-sdk-");
  const docs = join(root, "docs");
  const decoded = join(root, "decoded");
  const packPath = join(root, "docs.specpack");
  await mkdir(docs);
  await writeFile(join(docs, "note.md"), Buffer.from("# JS SDK\r\n\r\nRound trip.\r\n"));

  const sdkOptions = {
    command: "python",
    baseArgs: ["-m", "spectrum_cli.main"],
    env: {
      ...process.env,
      PYTHONPATH: [
        join(repoRoot, "packages/core/src"),
        join(repoRoot, "packages/cli/src"),
        join(repoRoot, "packages/index/src"),
      ].join(process.platform === "win32" ? ";" : ":"),
    },
  };

  const pack = await SpectrumPack.create({ inputPath: docs, outputPath: packPath }, sdkOptions);
  assert.equal((await pack.inspect()).entries, 1);
  assert.equal((await pack.verify()).valid, true);
  assert.equal((await pack.buildIndex()).embedded, true);
  const results = await pack.search("js sdk round trip", { topK: 1 });
  assert.equal(results[0].path.endsWith("note.md.spec"), true);
  assert.equal(results[0].source_path, "note.md");

  const unpacked = await pack.unpack(decoded);
  assert.equal(unpacked.length, 1);
  assert.equal((await readFile(join(decoded, "note.md"))).toString(), "# JS SDK\r\n\r\nRound trip.\r\n");
});

async function mkTempDir(prefix) {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(join(tmpdir(), prefix));
}
