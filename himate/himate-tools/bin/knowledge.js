#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn, spawnSync } = require("child_process");

const SUPPORTED = new Set(["3.10", "3.11", "3.12"]);
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const ENTRY = path.join(INSTALL_ROOT, "knowledge.py");

function candidateInterpreters() {
  const candidates = [];
  const configured = process.env.HIMATE_KNOWLEDGE_PYTHON;
  if (configured) {
    candidates.push({ command: configured, prefix: [] });
  }
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

function interpreterVersion(candidate) {
  const probe = spawnSync(
    candidate.command,
    [...candidate.prefix, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
    { encoding: "utf8", windowsHide: true }
  );
  if (probe.error || probe.status !== 0) {
    return null;
  }
  const version = (probe.stdout || "").trim();
  return SUPPORTED.has(version) ? version : null;
}

function findInterpreter() {
  for (const candidate of candidateInterpreters()) {
    const version = interpreterVersion(candidate);
    if (version) {
      return { ...candidate, version };
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
      "\nRun: npm i -g @himate/knowledge-cli"
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
  [...python.prefix, "-B", ENTRY, ...process.argv.slice(2)],
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
