#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { join } = require("node:path");

const cli = join(__dirname, "..", "spectrum_cli", "main.py");
const env = {
  ...process.env,
  SPECTRUM_CLI_DIR: join(__dirname, ".."),
};

const baseArgs = [cli, ...process.argv.slice(2)];
const candidates = process.platform === "win32"
  ? [
      { command: "py", args: ["-3", ...baseArgs] },
      { command: "python", args: baseArgs },
      { command: "python3", args: baseArgs },
    ]
  : [
      { command: "python3", args: baseArgs },
      { command: "python", args: baseArgs },
      { command: "py", args: ["-3", ...baseArgs] },
    ];

let lastError = null;
for (const candidate of candidates) {
  const result = spawnSync(candidate.command, candidate.args, { stdio: "inherit", env });
  if (!result.error) {
    process.exit(result.status ?? 1);
  }
  lastError = result.error;
  if (result.error.code !== "ENOENT") {
    break;
  }
}

console.error(`spec: failed to start Python: ${lastError ? lastError.message : "unknown error"}`);
console.error("spec: install Python 3 or make sure the Windows 'py' launcher is available on PATH.");
process.exit(1);
