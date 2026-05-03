import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const specBin = join(repoRoot, "bin", "spec.js");

function run(args, options = {}) {
  return execFileSync("node", [specBin, ...args], {
    cwd: options.cwd ?? repoRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

test("prints version", () => {
  assert.match(run(["--version"]), /^spec 0\.4\.1\s*$/);
});

test("encodes, verifies, and decodes a file", async () => {
  const dir = mkdtempSync(join(tmpdir(), "spectrum-cli-file-"));
  try {
    const source = join(dir, "hello.txt");
    const encoded = join(dir, "hello.txt.spec");
    const decoded = join(dir, "decoded.txt");
    writeFileSync(source, "Spectrum keeps searchable archives small.\n", "utf8");

    run(["encode", source, "--lang", "txt", "-o", encoded]);
    assert.match(run(["verify", encoded]), /Verify OK: 1 file/);

    run(["decode", encoded, "-o", decoded]);
    assert.equal(readFileSync(decoded, "utf8"), "Spectrum keeps searchable archives small.\n");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("creates a searchable specpack", async () => {
  const dir = mkdtempSync(join(tmpdir(), "spectrum-cli-pack-"));
  try {
    const docs = join(dir, "docs");
    await mkdir(docs);
    writeFileSync(join(docs, "auth.md"), "OAuth callback handler validates state tokens.\n", "utf8");
    writeFileSync(join(docs, "billing.md"), "Invoices are reconciled after payment webhook delivery.\n", "utf8");

    const pack = join(dir, "docs.specpack");
    run(["encode", docs, "-a", "--index", "--lang", "txt", "-o", pack], { cwd: dir });
    const info = run(["info", pack], { cwd: dir });
    assert.match(info, /Type:\s+\.specpack/);
    assert.match(info, /Index:\s+embedded/);

    const results = run(["search", "oauth state callback", pack], { cwd: dir });
    assert.match(results, /auth/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
