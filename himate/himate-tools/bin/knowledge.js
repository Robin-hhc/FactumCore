#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn, spawnSync } = require("child_process");

const SUPPORTED = new Set(["3.10", "3.11", "3.12"]);
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const ENTRY = path.join(INSTALL_ROOT, "knowledge.py");
const VENV = path.join(INSTALL_ROOT, ".venv");
const MANAGED_PYTHON = process.platform === "win32"
  ? path.join(VENV, "Scripts", "python.exe")
  : path.join(VENV, "bin", "python");

function candidateInterpreters() {
  const candidates = [];
  if (process.platform === "win32") {
    candidates.push(
      { command: "py", prefix: ["-3.11"] },
      { command: "py", prefix: ["-3.12"] },
      { command: "py", prefix: ["-3.10"] },
      { command: "python", prefix: [] },
      { command: "python3", prefix: [] }
    );
  } else {
    candidates.push(
      { command: "python3", prefix: [] },
      { command: "python", prefix: [] },
      { command: "python3.11", prefix: [] },
      { command: "python3.12", prefix: [] },
      { command: "python3.10", prefix: [] }
    );
  }
  return candidates;
}

function inspectInterpreter(candidate) {
  const probe = spawnSync(
    candidate.command,
    [
      ...candidate.prefix, "-I", "-B", "-c",
      "import json, sys; print(json.dumps({'version': '%d.%d' % sys.version_info[:2], " +
        "'venv': sys.prefix != sys.base_prefix, 'base': sys._base_executable}))",
    ],
    { encoding: "utf8", windowsHide: true, timeout: 10000 }
  );
  if (probe.error || probe.status !== 0) {
    return null;
  }
  try {
    const info = JSON.parse(probe.stdout);
    return SUPPORTED.has(info.version) ? info : null;
  } catch (error) {
    return null;
  }
}

function hasManagedVenv() {
  try {
    return fs.lstatSync(VENV).isDirectory() && fs.existsSync(path.join(VENV, "pyvenv.cfg"));
  } catch (error) {
    return false;
  }
}

function findInterpreter() {
  const configured = process.env.HIMATE_KNOWLEDGE_PYTHON;
  const explicit = { command: configured, prefix: [] };
  const explicitInfo = configured ? inspectInterpreter(explicit) : null;
  if (explicitInfo?.venv) {
    return explicit;
  }

  const managed = { command: MANAGED_PYTHON, prefix: [] };
  if (hasManagedVenv() && inspectInterpreter(managed)?.venv) {
    return managed;
  }
  if (explicitInfo) {
    return explicit;
  }

  for (const candidate of candidateInterpreters()) {
    const info = inspectInterpreter(candidate);
    if (!info) {
      continue;
    }
    if (!info.venv) {
      return candidate;
    }
    // PATH can point at an activated project venv. Bootstrap from its base Python.
    if (info.base && path.isAbsolute(info.base)) {
      const base = { command: info.base, prefix: [] };
      if (inspectInterpreter(base)?.venv === false) {
        return base;
      }
    }
  }
  return null;
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
  [...python.prefix, "-I", "-B", ENTRY, ...process.argv.slice(2)],
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
