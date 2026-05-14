#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { delimiter, join } = require("node:path");

const root = join(__dirname, "..");
const pythonPaths = [
  join(root, "packages", "core", "src"),
  join(root, "packages", "index", "src"),
  join(root, "packages", "cli", "src"),
];

const env = {
  ...process.env,
  SPECTRUM_NODE_COMMAND: process.execPath,
  SPECTRUM_PACKAGE_ROOT: root,
  SPECTRUM_REPO_ROOT: process.env.SPECTRUM_REPO_ROOT || join(root, "CLI Tool", "vendor", "spectrum_algo"),
  PYTHONPATH: [
    ...pythonPaths,
    process.env.PYTHONPATH || "",
  ].filter(Boolean).join(delimiter),
};

const moduleArgs = ["-m", "spectrum_cli.main", ...process.argv.slice(2)];
const candidates = process.platform === "win32"
  ? [
      { command: "py", args: ["-3", ...moduleArgs] },
      { command: "python", args: moduleArgs },
      { command: "python3", args: moduleArgs },
    ]
  : [
      { command: "python3", args: moduleArgs },
      { command: "python", args: moduleArgs },
      { command: "py", args: ["-3", ...moduleArgs] },
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

console.error(`spectrumstore: failed to start Python: ${lastError ? lastError.message : "unknown error"}`);
console.error("spectrumstore: install Python 3.10+ or make sure it is available on PATH.");
process.exit(1);
