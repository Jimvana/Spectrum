import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, readFileSync, unlinkSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const npmCli = process.env.npm_execpath;
if (!npmCli) {
  throw new Error("npm_execpath is not set. Run this script with npm run smoke:packed.");
}

function run(command, args, options = {}) {
  console.log(`$ ${[command, ...args].join(" ")}`);
  return execFileSync(command, args, {
    cwd: root,
    stdio: "pipe",
    encoding: "utf8",
    ...options,
  });
}

function runNpm(args, options = {}) {
  return run(process.execPath, [npmCli, ...args], options);
}

function runSpectrum(globalRoot, args, options = {}) {
  const spectrumBin = join(globalRoot.trim(), "spectrumstore", "bin", "spectrumstore.js");
  return run(process.execPath, [spectrumBin, ...args], options);
}

let tarballPath;
let workspace;

try {
  const packOutput = runNpm(["pack", "--json"]);
  const packInfo = JSON.parse(packOutput);
  tarballPath = join(root, packInfo[0].filename);

  runNpm(["install", "-g", "--force", tarballPath], { stdio: "inherit" });
  const globalRoot = runNpm(["root", "-g"]);

  workspace = mkdtempSync(join(tmpdir(), "spectrum-packed-smoke-"));
  const project = join(workspace, "auth-service");
  mkdirSync(join(project, "src"), { recursive: true });
  writeFileSync(
    join(project, "src", "auth.js"),
    [
      "export function authenticationMiddleware(request, response, next) {",
      "  const header = request.headers.authorization || '';",
      "  if (!header.startsWith('Bearer ')) {",
      "    response.statusCode = 401;",
      "    response.end('missing bearer token');",
      "    return;",
      "  }",
      "  next();",
      "}",
      "",
    ].join("\n"),
    "utf8",
  );
  writeFileSync(
    join(project, "README.md"),
    "Auth service sample with bearer token middleware.\n",
    "utf8",
  );

  const packPath = join(workspace, "auth-service.specpack");
  const restored = join(workspace, "restored");

  runSpectrum(globalRoot, ["doctor", "--json"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["pack", project, packPath, "--json"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["index", packPath, "--embed", "--json"], { cwd: workspace, stdio: "inherit" });
  const searchOutput = run(
    process.execPath,
    [
      join(globalRoot.trim(), "spectrumstore", "bin", "spectrumstore.js"),
      "search",
      packPath,
      "authentication bearer middleware",
      "--top",
      "1",
      "--json",
    ],
    { cwd: workspace },
  );
  const searchResults = JSON.parse(searchOutput);
  if (!Array.isArray(searchResults) || searchResults.length === 0) {
    throw new Error("Expected at least one search result from packed CLI smoke test.");
  }
  runSpectrum(globalRoot, ["verify", packPath, "--json"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["unpack", packPath, restored, "--json"], { cwd: workspace, stdio: "inherit" });

  const original = readFileSync(join(project, "src", "auth.js"), "utf8");
  const decoded = readFileSync(join(restored, "src", "auth.js"), "utf8");
  if (original !== decoded) {
    throw new Error("Decoded auth.js did not match the original source.");
  }

  console.log("Packed CLI smoke test passed.");
} finally {
  if (workspace) {
    rmSync(workspace, { recursive: true, force: true });
  }
  if (tarballPath) {
    try {
      unlinkSync(tarballPath);
    } catch {
      // Best-effort cleanup only.
    }
  }
}
