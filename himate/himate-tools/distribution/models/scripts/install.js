"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const MODELS_ROOT = path.join(os.homedir(), ".himate", "knowledge", "tools", "deploy", "models");
const REQUIRED_FILES = new Set([
  "docling-project--docling-layout-heron/config.json",
  "docling-project--docling-layout-heron/preprocessor_config.json",
  "docling-project--docling-layout-heron/model.safetensors",
  "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
  "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
  "RapidOcr/PP-OCRv6_det_small.onnx",
  "RapidOcr/PP-OCRv6_rec_small.onnx",
  "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
]);

function noLinks(file) {
  for (let current = path.resolve(file); ; current = path.dirname(current)) {
    if (fs.lstatSync(current, { throwIfNoEntry: false })?.isSymbolicLink()) {
      throw new Error("Model path must not contain links or junctions: " + current);
    }
    if (current === path.dirname(current)) break;
  }
}

function bundlePath(root, reference) {
  if (typeof reference !== "string" || reference.includes("\\") || reference.includes(":")
      || reference.split("/").some((part) => !part || part === "." || part === "..")) {
    throw new Error("Invalid model path: " + reference);
  }
  const file = path.join(root, ...reference.split("/"));
  noLinks(file);
  return file;
}

function validateRow(row) {
  if (!row || !Number.isSafeInteger(row.bytes) || row.bytes <= 0
      || typeof row.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(row.sha256)) {
    throw new Error("Invalid model size or digest");
  }
  bundlePath(PACKAGE_ROOT, row.path);
}

function readManifest() {
  const manifest = JSON.parse(fs.readFileSync(bundlePath(PACKAGE_ROOT, "manifest.json"), "utf8"));
  if (!["1.0", "1.1"].includes(manifest.schema_version) || manifest.model_set !== "docling-cpu"
      || !Array.isArray(manifest.files) || manifest.files.length !== REQUIRED_FILES.size) {
    throw new Error("Invalid model manifest");
  }
  const remaining = new Set(REQUIRED_FILES);
  let total = 0;
  for (const row of manifest.files) {
    validateRow(row);
    if (!remaining.delete(row.path)) throw new Error("Missing or duplicate required model: " + row.path);
    total += row.bytes;
    if (row.parts !== undefined) {
      if (!Array.isArray(row.parts) || row.parts.length < 2) {
        throw new Error("Invalid model parts: " + row.path);
      }
      let partBytes = 0;
      row.parts.forEach((part, index) => {
        validateRow(part);
        const suffix = String(index + 1).padStart(3, "0");
        if (part.path !== row.path + ".part" + suffix || part.bytes > 48 * 1024 * 1024) {
          throw new Error("Invalid model part order or size: " + part.path);
        }
        partBytes += part.bytes;
      });
      if (partBytes !== row.bytes) throw new Error("Model parts total size mismatch: " + row.path);
    }
  }
  if (manifest.total_bytes !== total) throw new Error("Model bundle total size mismatch");
  return manifest;
}

function appendVerified(source, destination, row, combined) {
  const info = fs.lstatSync(source);
  if (!info.isFile() || info.size !== row.bytes) {
    throw new Error("Model size mismatch or file missing: " + source);
  }
  const digest = crypto.createHash("sha256");
  const input = fs.openSync(source, "r");
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    let read;
    while ((read = fs.readSync(input, buffer, 0, buffer.length, null)) > 0) {
      const chunk = buffer.subarray(0, read);
      digest.update(chunk);
      combined.update(chunk);
      let written = 0;
      while (written < read) written += fs.writeSync(destination, buffer, written, read - written);
    }
  } finally {
    fs.closeSync(input);
  }
  if (digest.digest("hex") !== row.sha256) throw new Error("Model digest mismatch: " + source);
}

function materializeModels(staging, manifest) {
  const sourceRoot = bundlePath(PACKAGE_ROOT, "docling-cpu");
  const targetRoot = path.join(staging, "docling-cpu");
  for (const row of manifest.files) {
    const target = bundlePath(targetRoot, row.path);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const output = fs.openSync(target, "wx");
    const combined = crypto.createHash("sha256");
    try {
      for (const part of row.parts || [row]) {
        appendVerified(bundlePath(sourceRoot, part.path), output, part, combined);
      }
      fs.fsyncSync(output);
    } finally {
      fs.closeSync(output);
    }
    if (fs.statSync(target).size !== row.bytes || combined.digest("hex") !== row.sha256) {
      throw new Error("Combined model size or digest mismatch: " + row.path);
    }
  }
}

function copyItem(staging, reference) {
  const source = bundlePath(PACKAGE_ROOT, reference);
  if (!fs.existsSync(source)) throw new Error("Package is incomplete, missing: " + reference);
  fs.cpSync(source, path.join(staging, reference), {
    recursive: true,
    preserveTimestamps: true,
    filter: (entry) => {
      noLinks(entry);
      const info = fs.lstatSync(entry);
      if (!info.isDirectory() && !info.isFile()) throw new Error("Invalid model package entry: " + entry);
      return true;
    },
  });
}

function main() {
  const manifest = readManifest();
  noLinks(MODELS_ROOT);
  const parent = path.dirname(MODELS_ROOT);
  fs.mkdirSync(parent, { recursive: true });
  const staging = fs.mkdtempSync(path.join(parent, ".staging-models-"));
  const backup = path.join(parent, ".previous-models-" + crypto.randomBytes(12).toString("hex"));
  let previous = false;
  try {
    materializeModels(staging, manifest);
    for (const reference of ["manifest.json", "README.md", "source-cards"]) copyItem(staging, reference);
    noLinks(MODELS_ROOT);
    if (fs.existsSync(MODELS_ROOT)) {
      if (!fs.statSync(MODELS_ROOT).isDirectory()) throw new Error("Expected model directory: " + MODELS_ROOT);
      fs.renameSync(MODELS_ROOT, backup);
      previous = true;
    }
    try {
      fs.renameSync(staging, MODELS_ROOT);
    } catch (error) {
      if (previous) fs.renameSync(backup, MODELS_ROOT);
      previous = false;
      throw error;
    }
    if (previous) fs.rmSync(backup, { recursive: true, force: true });
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
  }
  process.stdout.write("knowledge models installed to " + MODELS_ROOT + "\n");
}

main();
