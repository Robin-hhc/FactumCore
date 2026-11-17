"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const MODELS_ROOT = path.join(os.homedir(), ".himate", "knowledge", "tools", "deploy", "models");
const STAGING = path.join(path.dirname(MODELS_ROOT), ".staging-models-" + process.pid);
const ITEMS = ["docling-cpu", "manifest.json", "README.md", "source-cards"];
const BUNDLE = path.join(PACKAGE_ROOT, "docling-cpu");

function sha256(file) {
  const digest = crypto.createHash("sha256");
  const stream = fs.openSync(file, "r");
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    let read;
    while ((read = fs.readSync(stream, buffer, 0, buffer.length, null)) > 0) {
      digest.update(buffer.subarray(0, read));
    }
  } finally {
    fs.closeSync(stream);
  }
  return digest.digest("hex");
}

function verifyFile(file, row) {
  if (!fs.existsSync(file) || fs.statSync(file).size !== row.bytes) {
    throw new Error("Model size mismatch or file missing: " + file);
  }
  if (sha256(file) !== row.sha256) {
    throw new Error("Model digest mismatch: " + file);
  }
}

function verifyBundle() {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(PACKAGE_ROOT, "manifest.json"), "utf8")
  );
  if (manifest.model_set !== "docling-cpu" || !Array.isArray(manifest.files)) {
    throw new Error("Invalid model manifest");
  }
  for (const row of manifest.files) {
    if (Array.isArray(row.parts)) {
      for (const part of row.parts) {
        verifyFile(path.join(BUNDLE, part.path), part);
      }
    } else {
      verifyFile(path.join(BUNDLE, row.path), row);
    }
  }
}

function copyItem(relative) {
  const source = path.join(PACKAGE_ROOT, relative);
  if (!fs.existsSync(source)) {
    throw new Error("Package is incomplete, missing: " + relative);
  }
  const destination = path.join(STAGING, relative);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, {
    recursive: true,
    force: true,
    preserveTimestamps: true,
    verbatimSymlinks: true,
  });
}

function commitItem(relative) {
  const staged = path.join(STAGING, relative);
  const target = path.join(MODELS_ROOT, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.rmSync(target, { recursive: true, force: true });
  fs.renameSync(staged, target);
}

function main() {
  verifyBundle();

  fs.mkdirSync(MODELS_ROOT, { recursive: true });
  fs.rmSync(STAGING, { recursive: true, force: true });

  try {
    for (const item of ITEMS) {
      copyItem(item);
    }
    for (const item of ITEMS) {
      commitItem(item);
    }
  } finally {
    fs.rmSync(STAGING, { recursive: true, force: true });
  }

  process.stdout.write("knowledge models installed to " + MODELS_ROOT + "\n");
}

main();
