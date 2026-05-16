#!/usr/bin/env node

const { spawn } = require("node:child_process");
const { delimiter, join } = require("node:path");

const root = join(__dirname, "..");
const pythonPaths = [
  join(root, "packages", "core", "src"),
  join(root, "packages", "index", "src"),
  join(root, "packages", "cli", "src"),
  join(root, "packages", "server", "src"),
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

const signalExitCodes = {
  SIGHUP: 129,
  SIGINT: 130,
  SIGTERM: 143,
};

function runCandidate(candidate) {
  return new Promise((resolve) => {
    const child = spawn(candidate.command, candidate.args, { stdio: "inherit", env });
    const cleanup = [];

    const removeHandlers = () => {
      for (const remove of cleanup) {
        remove();
      }
    };

    for (const signal of Object.keys(signalExitCodes)) {
      const handler = () => {
        if (child.exitCode === null && child.signalCode === null) {
          child.kill(signal);
          return;
        }
        process.exit(signalExitCodes[signal]);
      };
      process.on(signal, handler);
      cleanup.push(() => process.off(signal, handler));
    }

    child.once("error", (error) => {
      removeHandlers();
      resolve({ error });
    });
    child.once("exit", (status, signal) => {
      removeHandlers();
      resolve({ status, signal });
    });
  });
}

async function main() {
  let lastError = null;
  for (const candidate of candidates) {
    const result = await runCandidate(candidate);
    if (!result.error) {
      if (result.signal) {
        process.exit(signalExitCodes[result.signal] ?? 1);
      }
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
}

main();
