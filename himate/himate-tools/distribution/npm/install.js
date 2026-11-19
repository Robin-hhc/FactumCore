"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..", "..");
const INSTALL_ROOT = path.join(os.homedir(), ".himate", "knowledge");
const RUNTIME_MANIFEST = path.join(INSTALL_ROOT, "runtime", "manifest.json");
const INSTALL_MARKER = path.join(INSTALL_ROOT, ".install.json");
const PACKAGE_NAME = "@himate/knowledge-cli";
const RETRY_WAIT = new Int32Array(new SharedArrayBuffer(4));

// Models are owned by @himate/knowledge-models and must survive CLI updates.
const ITEMS = [
  "knowledge.py",
  ".gitattributes",
  "runtime",
  "distribution/source",
  "docs/DEPLOY.md",
];

function copyItem(relative, staging) {
  const source = path.join(PACKAGE_ROOT, relative);
  if (!fs.existsSync(source)) {
    throw new Error("Package is incomplete, missing: " + relative);
  }
  const destination = path.join(staging, relative);
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

function renameWithRetry(source, target) {
  for (let attempt = 0; ; attempt++) {
    try {
      fs.renameSync(source, target);
      return;
    } catch (error) {
      const busy = error.code === "EPERM" || error.code === "EBUSY";
      if (process.platform !== "win32" || !busy || attempt === 3) throw error;
      Atomics.wait(RETRY_WAIT, 0, 0, 100 * (attempt + 1));
    }
  }
}

function claimSwitch(work) {
  // Publish our claim before checking peers. A competing live installer either
  // sees this claim or has already published one for us to see.
  const current = path.basename(work);
  fs.writeFileSync(path.join(work, "switching"), "");
  for (const name of fs.readdirSync(INSTALL_ROOT)) {
    const owner = /^\.staging-cli-([1-9][0-9]{0,9})-[a-zA-Z0-9]+$/.exec(name);
    if (name === current || !owner) continue;
    if (!fs.lstatSync(path.join(INSTALL_ROOT, name, "switching"), { throwIfNoEntry: false })) continue;
    try {
      process.kill(Number(owner[1]), 0);
    } catch (error) {
      // A stopped installer can leave a backup here. Keep it for recovery.
      if (error.code === "ESRCH") continue;
      if (error.code !== "EPERM") throw error;
    }
    throw new Error("Another CLI installation is switching files (PID " + owner[1] + ")");
  }
}

function commitItem(relative, staging, backup, undo) {
  const target = path.join(INSTALL_ROOT, relative);
  if (fs.lstatSync(target, { throwIfNoEntry: false })) {
    const previous = path.join(backup, relative);
    fs.mkdirSync(path.dirname(previous), { recursive: true });
    renameWithRetry(target, previous);
    undo.push([previous, target]);
  }
  if (staging) {
    const staged = path.join(staging, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    renameWithRetry(staged, target);
    undo.push([target, staged]);
  }
}

function restoreItems(undo) {
  const errors = [];
  for (const [source, target] of undo.reverse()) {
    try {
      renameWithRetry(source, target);
    } catch (error) {
      errors.push(error);
    }
  }
  return errors;
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function verifyRuntime(staging, version) {
  const manifest = JSON.parse(fs.readFileSync(path.join(staging, "runtime/manifest.json"), "utf8"));
  if (manifest?.schema_version !== "1.1" || manifest.version !== version) {
    throw new Error("Invalid staged runtime manifest schema or version");
  }
  const sections = [
    [staging, manifest.entrypoints, ["knowledge.py"]],
    [path.join(staging, "runtime"), manifest.files,
      ["requirements.lock.txt", "himate_knowledge/__init__.py", "himate_knowledge/cli.py"]],
    [staging, manifest.assets, ["runtime/governance/framework.lock.yaml"]],
  ];
  for (const [root, rows, required] of sections) {
    if (!rows || typeof rows !== "object" || required.some((ref) => !Object.hasOwn(rows, ref))) {
      throw new Error("Invalid staged runtime manifest: missing required files");
    }
    for (const [reference, row] of Object.entries(rows)) {
      if (reference.split("/").some((part) => !part || part === "." || part === ".." || /[:\\\x00]/.test(part))) {
        throw new Error("Invalid staged runtime manifest path: " + reference);
      }
      const file = path.join(root, reference);
      if (!fs.lstatSync(file, { throwIfNoEntry: false })?.isFile()) {
        throw new Error("Runtime file missing in staged package: " + reference);
      }
      if (sha256(file) !== row?.sha256) {
        throw new Error("Runtime digest mismatch in staged package: " + reference);
      }
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

function retiredWrappers(previous) {
  return ["knowledge.cmd", "knowledge.sh"].filter((name) => {
    const digest = previous[name]?.sha256;
    const file = path.join(INSTALL_ROOT, name);
    return typeof digest === "string" && fs.lstatSync(file, { throwIfNoEntry: false })?.isFile()
        && sha256(file) === digest;
  });
}

function main() {
  fs.mkdirSync(INSTALL_ROOT, { recursive: true });
  const work = fs.mkdtempSync(path.join(INSTALL_ROOT, ".staging-cli-" + process.pid + "-"));
  const staging = path.join(work, "new");
  const backup = path.join(work, "previous");
  let preserveBackup = false;
  const undo = [];
  try {
    for (const item of ITEMS) {
      copyItem(item, staging);
    }
    const version = require(path.join(PACKAGE_ROOT, "package.json")).version;
    verifyRuntime(staging, version);

    if (process.platform !== "win32") {
      fs.chmodSync(path.join(staging, "knowledge.py"), 0o755);
    }

    fs.writeFileSync(
      path.join(staging, ".install.json"),
      JSON.stringify(
        {
          package: PACKAGE_NAME,
          version,
          packageRoot: PACKAGE_ROOT,
          launcherSha256: sha256(path.join(__dirname, "knowledge.js")),
          installedAt: new Date().toISOString(),
        },
        null,
        2
      ) + "\n"
    );

    claimSwitch(work);
    const retired = retiredWrappers(previousEntrypoints());
    for (const item of ITEMS) {
      commitItem(item, staging, backup, undo);
    }
    for (const name of retired) {
      commitItem(name, null, backup, undo);
    }
    commitItem(".install.json", staging, backup, undo);
  } catch (error) {
    const failures = restoreItems(undo);
    if (failures.length) {
      preserveBackup = true;
      throw new AggregateError([error, ...failures], "CLI installation rollback was incomplete. Backup retained at " + backup);
    }
    throw error;
  } finally {
    try {
      if (!preserveBackup) {
        fs.rmSync(work, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
      }
    } catch (error) {
      process.stderr.write("Could not remove temporary CLI installation files: " + error.message + "\n");
    }
  }

  process.stdout.write("knowledge CLI installed to " + INSTALL_ROOT + "\n");
}

main();
