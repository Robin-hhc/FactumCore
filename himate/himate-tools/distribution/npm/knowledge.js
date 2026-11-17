#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn, spawnSync } = require("child_process");

const SUPPORTED = new Set(["3.10", "3.11", "3.12"]);
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const ENTRY = path.join(INSTALL_ROOT, "knowledge.py");

function pathExecutable(name, directories) {
  for (const directory of directories) {
    const candidate = path.join(directory, name);
    try {
      if (!fs.statSync(candidate).isFile()) continue;
      fs.accessSync(candidate, fs.constants.X_OK);
      return candidate;
    } catch {
      // This PATH entry does not contain an executable for this name.
    }
  }
  return null;
}

function candidateInterpreters() {
  const candidates = [];
  const directories = (process.env.PATH || "").split(path.delimiter)
    .map((item) => item.replace(/^"|"$/g, ""))
    .filter((item) => path.isAbsolute(item));
  const configured = process.env.HIMATE_KNOWLEDGE_PYTHON;
  if (configured && path.isAbsolute(configured)) {
    candidates.push({ command: configured, prefix: [] });
  }
  const windows = process.platform === "win32";
  if (windows) {
    const systemRoot = process.env.SystemRoot;
    const launcherDirs = systemRoot && path.isAbsolute(systemRoot)
      ? [...directories, systemRoot] : directories;
    const launcher = pathExecutable("py.exe", launcherDirs);
    if (launcher) {
      for (const version of ["-3.11", "-3.12", "-3.10"]) {
        candidates.push({ command: launcher, prefix: [version] });
      }
    }
  }
  const names = windows ? ["python.exe", "python3.exe"] : ["python3", "python", "python3.11", "python3.12", "python3.10"];
  for (const name of names) {
    const command = pathExecutable(name, directories);
    if (command) candidates.push({ command, prefix: [] });
  }
  return candidates;
}

function inspectInterpreter(candidate) {
  const probe = spawnSync(
    candidate.command,
    [...candidate.prefix, "-I", "-B", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
    { encoding: "utf8", windowsHide: true, timeout: 10000 }
  );
  return !probe.error && probe.status === 0 && SUPPORTED.has(probe.stdout.trim());
}

function findInterpreter() {
  return candidateInterpreters().find(inspectInterpreter);
}

function fail(message) {
  process.stderr.write(message + "\n");
  process.exit(1);
}

if (!fs.existsSync(ENTRY)) {
  fail(
    "knowledge is not installed at " +
      INSTALL_ROOT +
      "\nRun: npm i -g @himate/knowledge-cli" +
      "\nOn npm 12, add --allow-scripts=@himate/knowledge-cli to allow the package's install script."
  );
}

const python = findInterpreter();
if (!python) {
  fail(
    "No supported Python found (need 3.10, 3.11 or 3.12).\n" +
      "Set HIMATE_KNOWLEDGE_PYTHON to the interpreter path, or install Python 3.11."
  );
}

const child = spawn(
  python.command,
  [...python.prefix, "-E", "-B", ENTRY, ...process.argv.slice(2)],
  { stdio: "inherit", windowsHide: false }
);

child.on("error", (error) => {
  fail("Failed to start Python: " + error.message);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code === null ? 1 : code);
});
