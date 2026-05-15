import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, readFileSync, unlinkSync } from "node:fs";
import { createServer } from "node:net";
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

function spectrumBinPath(globalRoot) {
  return join(globalRoot.trim(), "spectrumstore", "bin", "spectrumstore.js");
}

function runSpectrum(globalRoot, args, options = {}) {
  return run(process.execPath, [spectrumBinPath(globalRoot), ...args], options);
}

function getFreePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = address.port;
      server.close(() => resolvePort(port));
    });
  });
}

async function waitForJson(url, attempts = 40) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return await response.json();
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  const exited = new Promise((resolveExit) => {
    child.once("exit", resolveExit);
  });
  child.kill();
  await Promise.race([
    exited,
    new Promise((resolveDelay) => setTimeout(resolveDelay, 5000)),
  ]);
}

let tarballPath;
let workspace;
let serverProcess;

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
  runSpectrum(globalRoot, ["serve", "--help"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["load", "--help"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["pack", project, packPath, "--json"], { cwd: workspace, stdio: "inherit" });
  runSpectrum(globalRoot, ["index", packPath, "--embed", "--json"], { cwd: workspace, stdio: "inherit" });
  const searchOutput = run(
    process.execPath,
    [
      spectrumBinPath(globalRoot),
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

  const port = await getFreePort();
  serverProcess = spawn(
    process.execPath,
    [spectrumBinPath(globalRoot), "serve", packPath, "--port", String(port), "--quiet"],
    { cwd: workspace, stdio: ["ignore", "pipe", "pipe"] },
  );
  let serverStdout = "";
  let serverStderr = "";
  serverProcess.stdout.on("data", (chunk) => {
    serverStdout += chunk.toString();
  });
  serverProcess.stderr.on("data", (chunk) => {
    serverStderr += chunk.toString();
  });
  serverProcess.once("exit", (code, signal) => {
    if (code !== null && code !== 0 && code !== 130) {
      console.error(`spectrum serve exited with ${code}${signal ? `/${signal}` : ""}`);
      console.error(serverStdout);
      console.error(serverStderr);
    }
  });

  const health = await waitForJson(`http://127.0.0.1:${port}/health`);
  if (health.status !== "ok") {
    throw new Error("Expected /health to report ok.");
  }
  const packs = await waitForJson(`http://127.0.0.1:${port}/packs`);
  if (!Array.isArray(packs.packs) || packs.packs[0]?.id !== "repo") {
    throw new Error("Expected spectrum serve to register the positional pack as id 'repo'.");
  }

  console.log("Packed CLI smoke test passed.");
} finally {
  if (serverProcess) {
    await stopProcess(serverProcess);
  }
  if (workspace) {
    rmSync(workspace, { recursive: true, force: true, maxRetries: 5, retryDelay: 250 });
  }
  if (tarballPath) {
    try {
      unlinkSync(tarballPath);
    } catch {
      // Best-effort cleanup only.
    }
  }
}
