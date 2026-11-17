"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..", "..");
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const STAGING = path.join(INSTALL_ROOT, ".staging-cli-" + process.pid);
const RUNTIME_MANIFEST = path.join(INSTALL_ROOT, "runtime", "manifest.json");
const INSTALL_MARKER = path.join(INSTALL_ROOT, ".install.json");
const PACKAGE_NAME = "@himate/knowledge-cli";

// Models are owned by @himate/knowledge-models and must survive CLI updates.
const ITEMS = [
  "knowledge.py",
  ".gitattributes",
  "runtime",
  "distribution/source",
  "docs/DEPLOY.md",
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
    // Node 24's unfiltered recursive copy can skip Windows Unicode paths.
    filter: () => true,
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
  const manifest = JSON.parse(fs.readFileSync(RUNTIME_MANIFEST, "utf8"));
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

function previousEntrypoints() {
  try {
    const installation = JSON.parse(fs.readFileSync(INSTALL_MARKER, "utf8"));
    const manifest = JSON.parse(fs.readFileSync(RUNTIME_MANIFEST, "utf8"));
    if (installation?.package === PACKAGE_NAME && typeof installation.version === "string"
        && installation.version === manifest?.version) {
      return manifest.entrypoints ?? {};
    }
  } catch {
    // An unrecognized installation does not establish ownership of any wrapper.
  }
  return {};
}

function removeRetiredWrappers(previous) {
  for (const name of ["knowledge.cmd", "knowledge.sh"]) {
    const digest = previous[name]?.sha256;
    const file = path.join(INSTALL_ROOT, name);
    if (typeof digest === "string" && fs.lstatSync(file, { throwIfNoEntry: false })?.isFile()
        && sha256(file) === digest) {
      fs.rmSync(file, { force: true });
    }
  }
}

function main() {
  fs.mkdirSync(INSTALL_ROOT, { recursive: true });
  fs.rmSync(STAGING, { recursive: true, force: true });
  const previous = previousEntrypoints();

  try {
    for (const item of ITEMS) {
      copyItem(item);
    }
    for (const item of ITEMS) {
      commitItem(item);
    }
    verifyRuntime();

    if (process.platform !== "win32") {
      fs.chmodSync(path.join(INSTALL_ROOT, "knowledge.py"), 0o755);
    }
    removeRetiredWrappers(previous);

    fs.writeFileSync(
      INSTALL_MARKER,
      JSON.stringify(
        {
          package: PACKAGE_NAME,
          version: require(path.join(PACKAGE_ROOT, "package.json")).version,
          packageRoot: PACKAGE_ROOT,
          launcherSha256: sha256(path.join(__dirname, "knowledge.js")),
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
