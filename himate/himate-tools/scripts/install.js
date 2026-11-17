"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const STAGING = path.join(INSTALL_ROOT, ".staging-cli-" + process.pid);

// Models are owned by @himate/knowledge-models and must survive CLI updates.
const ITEMS = [
  "knowledge.py",
  "knowledge.cmd",
  "knowledge.sh",
  ".gitattributes",
  "runtime",
  "governance",
  "tools/deploy/deploy.py",
  "tools/deploy/environment.py",
  "tools/deploy/README.md",
  "tools/knowledge",
];

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
  const target = path.join(INSTALL_ROOT, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.rmSync(target, { recursive: true, force: true });
  fs.renameSync(staged, target);
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function verifyRuntime() {
  const manifestPath = path.join(INSTALL_ROOT, "runtime", "manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const rows = manifest.entrypoints || {};
  for (const [reference, row] of Object.entries(rows)) {
    const file = path.join(INSTALL_ROOT, reference);
    if (!fs.existsSync(file)) {
      throw new Error("Runtime entrypoint missing after install: " + reference);
    }
    if (sha256(file) !== row.sha256) {
      throw new Error(
        "Runtime digest mismatch after install: " +
          reference +
          " (line endings or file bytes were altered)"
      );
    }
  }
}

function main() {
  fs.mkdirSync(INSTALL_ROOT, { recursive: true });
  fs.rmSync(STAGING, { recursive: true, force: true });

  try {
    for (const item of ITEMS) {
      copyItem(item);
    }
    for (const item of ITEMS) {
      commitItem(item);
    }
    verifyRuntime();

    if (process.platform !== "win32") {
      for (const script of ["knowledge.py", "knowledge.sh"]) {
        fs.chmodSync(path.join(INSTALL_ROOT, script), 0o755);
      }
    }

    fs.writeFileSync(
      path.join(INSTALL_ROOT, ".install.json"),
      JSON.stringify(
        {
          package: "@himate/knowledge-cli",
          version: require(path.join(PACKAGE_ROOT, "package.json")).version,
          packageRoot: PACKAGE_ROOT,
          launcherSha256: sha256(path.join(PACKAGE_ROOT, "bin/knowledge.js")),
          installedAt: new Date().toISOString(),
        },
        null,
        2
      ) + "\n"
    );
  } finally {
    fs.rmSync(STAGING, { recursive: true, force: true });
  }

  process.stdout.write("knowledge CLI installed to " + INSTALL_ROOT + "\n");
}

main();
