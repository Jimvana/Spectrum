#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { join } = require("node:path");

const cli = join(__dirname, "..", "spectrum_cli", "main.py");
const args = [cli, ...process.argv.slice(2)];
const env = {
  ...process.env,
  SPECTRUM_CLI_DIR: join(__dirname, ".."),
};

let result = spawnSync("python3", args, { stdio: "inherit", env });
if (result.error && result.error.code === "ENOENT") {
  result = spawnSync("python", args, { stdio: "inherit", env });
}

if (result.error) {
  console.error(`spec: failed to start Python: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
