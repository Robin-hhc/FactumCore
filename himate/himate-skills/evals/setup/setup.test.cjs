"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { runSetup } = require("../../skills/hs-knowledge-setup/scripts/setup.cjs");

const CLI = "@himate/knowledge-cli";
const MODELS = "@himate/knowledge-models";
const REGISTRY = "http://10.143.57.12:4873";
const VERSION = require("../../../himate-tools/package.json").version;
const manifest = require("../../../himate-tools/distribution/models/manifest.json");

function write(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, typeof value === "string" ? value : JSON.stringify(value));
}

function fixture(t) {
  const temp = fs.realpathSync(os.tmpdir());
  const base = fs.mkdtempSync(path.join(temp, "hs-setup-"));
  t.after(() => {
    assert.equal(path.dirname(fs.realpathSync(base)), temp);
    assert.match(path.basename(base), /^hs-setup-[a-z0-9]+$/i);
    fs.rmSync(base, { recursive: true, force: true });
  });
  const toolRoot = path.join(base, "user tools", "knowledge");
  const root = path.join(base, "chosen 知识库");
  fs.mkdirSync(path.join(root, "docs-raw"), { recursive: true });
  fs.mkdirSync(path.join(root, "knowledge"));
  write(path.join(root, "config.yml"), "schema_version: '2.0'\n");
  const packageRoot = path.join(base, "npm prefix", "node_modules", "@himate", "knowledge-cli");
  const dispatcher = path.join(packageRoot, "distribution", "npm", "knowledge.js");
  const bin = path.join(base, "npm executable");
  const npm = path.join(bin, process.platform === "win32" ? "npm.cmd" : "npm");
  const python = path.join(base, "isolated python");
  write(path.join(bin, "node_modules", "npm", "bin", "npm-cli.js"), "test only");
  write(path.join(bin, "node_modules", "npm", "package.json"), { name: "npm" });

  const state = { dependencies: false, documents: false, libreOfficeGap: null, pip: true, cliInstallError: false,
    brokenConfig: false, registry: "undefined", reportedRoot: root, setupPython: python };
  const probes = [];
  const installCli = () => {
    write(path.join(toolRoot, "knowledge.py"), "# fixture");
    write(path.join(toolRoot, "runtime", "manifest.json"), { version: VERSION });
    write(path.join(packageRoot, "package.json"), { name: CLI, version: VERSION, bin: { knowledge: "distribution/npm/knowledge.js" } });
    const script = "// dispatcher test fixture";
    write(dispatcher, script);
    write(path.join(toolRoot, ".install.json"), { package: CLI, version: VERSION, packageRoot,
      launcherSha256: createHash("sha256").update(script).digest("hex") });
  };
  const installModels = () => {
    const modelsRoot = path.join(toolRoot, "tools", "deploy", "models");
    const files = manifest.files.map(({ path: file }) => ({ path: file, bytes: 2 }));
    for (const { path: file } of files) write(path.join(modelsRoot, "docling-cpu", file), "ok");
    write(path.join(modelsRoot, "manifest.json"), { model_set: "docling-cpu", files });
  };
  const respond = (payload, status = 0) => ({ status, stdout: typeof payload === "string" ? payload : JSON.stringify(payload) });
  const execute = (argv, args) => {
    probes.push(args);
    if (args.length >= 3 && args.includes("-c")) return respond(args.at(-1).includes("find_spec") ? "" : "3.12", state.pip || !args.at(-1).includes("find_spec") ? 0 : 1);
    if (args[0] === "config") return respond(args[2] === "@himate:registry" ? state.registry : "false");
    if (args[0] === "install") {
      assert.deepEqual(args.slice(3), ["--registry", REGISTRY, "--allow-scripts=" + args[2]]);
      if (args[2] === MODELS) installModels();
      if (args[2] === CLI && state.cliInstallError) return respond("", 1);
      if (args[2] === CLI) installCli();
      return respond("");
    }
    assert.deepEqual(argv, [process.execPath, dispatcher]);
    const scope = args.includes("--capability") ? args[args.indexOf("--capability") + 1] : null;
    assert.ok([null, "documents", "libreoffice"].includes(scope));
    const flags = scope ? ["--capability", scope] : [];
    const report = { status: "ready", toolkit_version: VERSION, tool_root: toolRoot, python, diagnostics: [] };
    if (!state.dependencies) report.diagnostics.push({ code: "DEPENDENCY_UNAVAILABLE", message: "missing locked dependency" });
    if (scope && !state.documents) report.diagnostics.push({ code: "DEPENDENCY_UNAVAILABLE", message: "missing Docling" });
    if (!state.pip && report.diagnostics.length) report.diagnostics.push({ code: "DEPENDENCY_PIP_MISSING", message: "missing pip" });
    if (scope === "libreoffice" && state.libreOfficeGap) report.diagnostics.push({ code: state.libreOfficeGap, message: "LibreOffice unavailable" });
    if (report.diagnostics.length) report.status = "needs_install";
    if (args[0] === "--version") return respond("knowledge " + VERSION);
    if (args[0] === "setup") {
      assert.deepEqual(args, ["setup", "--dependencies-only", ...flags, "--json"]);
      state.dependencies = true;
      if (scope) state.documents = true;
      if (scope === "libreoffice") state.libreOfficeGap = null;
      return respond({ ...report, status: "ready", python: state.setupPython, diagnostics: [] });
    }
    if (args.includes("--environment-only")) {
      assert.deepEqual(args, ["doctor", "--environment-only", "--dependencies-only", ...flags, "--json"]);
      return respond(report);
    }
    assert.deepEqual(args, ["doctor", "--knowledge-root", root, ...flags, "--json"]);
    const valid = report.status === "ready" && !state.brokenConfig;
    return respond({
      status: valid ? "ok" : "blocked", phase: valid ? "ready" : "blocked",
      data: { knowledge_root: state.reportedRoot, tool_root: toolRoot, python, runtime_version: VERSION },
      diagnostics: state.brokenConfig ? [{ code: "CONFIG_INVALID", message: "invalid config" }] : report.diagnostics,
    }, valid ? 0 : 3);
  };
  const context = { toolRoot, execute, find: (name) => name.startsWith("npm") ? npm : name.startsWith("python") ? python : null };
  const setup = (action, scope) => runSetup([action, "--knowledge-root", root,
    ...(scope ? ["--capability", scope] : []), "--json"], context);
  const changes = () => probes.filter(([action]) => action === "install" || action === "setup");
  return { setup, root, toolRoot, context, state, installCli, installModels, changes, dispatcher, probes };
}

test("cold check is read-only, install verifies the same root, and another run makes no changes", (t) => {
  const f = fixture(t);
  assert.equal(f.setup("check").status, "needs_setup");
  assert.equal(fs.existsSync(f.toolRoot), false);
  assert.deepEqual(f.changes(), []);
  const ready = f.setup("install");
  assert.equal(ready.status, "ready", JSON.stringify(ready));
  assert.deepEqual(ready.performed, ["install_cli", "setup_python"]);
  assert.equal(ready.models.status, "not_requested");
  assert.equal(ready.knowledge_root, f.root);
  assert.equal(ready.knowledge.version, VERSION);
  assert.deepEqual(ready.knowledge.argv, [process.execPath, f.dispatcher]);
  assert.deepEqual(f.setup("install").performed, []);
  assert.equal(f.changes().length, 2);
});

test("Python dependencies alone use existing canonical CLI and do not invoke npm", (t) => {
  const f = fixture(t);
  f.installCli();
  f.installModels();
  assert.deepEqual(f.setup("check").planned, ["setup_python"]);
  const ready = f.setup("install");
  assert.equal(ready.status, "ready");
  assert.deepEqual(ready.performed, ["setup_python"]);
  assert.deepEqual(f.changes(), [["setup", "--dependencies-only", "--json"]]);
});

test("rooted doctor can report LibreOffice as the only missing dependency", (t) => {
  const f = fixture(t);
  f.installCli();
  f.state.dependencies = true;
  f.state.documents = true;
  f.state.libreOfficeGap = "LIBREOFFICE_MISSING";
  assert.equal(f.setup("check").status, "ready");
  const check = f.setup("check", "libreoffice");
  assert.equal(check.status, "needs_setup");
  assert.deepEqual(check.diagnostics.map(({ code }) => code), ["LIBREOFFICE_MISSING"]);
  assert.deepEqual(check.planned, ["setup_python"]);
  assert.equal(f.setup("install", "libreoffice").status, "ready");
  assert.deepEqual(f.changes(), [["setup", "--dependencies-only", "--capability", "libreoffice", "--json"]]);
});

test("a broken LibreOffice command requires fixing its configuration", (t) => {
  const f = fixture(t);
  f.installCli();
  f.state.dependencies = true;
  f.state.documents = true;
  f.state.libreOfficeGap = "LIBREOFFICE_COMMAND_UNAVAILABLE";
  const result = f.setup("install", "libreoffice");
  assert.equal(result.status, "blocked");
  assert.deepEqual(result.diagnostics.map(({ code }) => code), ["LIBREOFFICE_COMMAND_UNAVAILABLE"]);
  assert.deepEqual(f.changes(), []);
});

test("documents install uses only the canonical CLI and checks the root once per inspection", (t) => {
  const f = fixture(t);
  f.installCli();
  f.state.dependencies = true;
  f.state.libreOfficeGap = "LIBREOFFICE_MISSING";
  const ready = f.setup("install", "documents");
  const flags = ["--capability", "documents", "--json"];
  const doctor = ["doctor", "--knowledge-root", f.root, ...flags];
  assert.equal(ready.status, "ready", JSON.stringify(ready));
  assert.equal(ready.models.status, "not_requested");
  assert.deepEqual(ready.performed, ["setup_python"]);
  assert.deepEqual(f.probes, [doctor, ["setup", "--dependencies-only", ...flags], doctor]);
});

test("missing model alone installs the model package for OCR", (t) => {
  const f = fixture(t);
  f.installCli();
  f.state.dependencies = true;
  f.state.documents = true;
  const check = f.setup("check", "ocr");
  assert.deepEqual(check.planned, ["install_models"]);
  assert.deepEqual(check.diagnostics.map(({ code }) => code), ["PARSER_MODELS_REQUIRED"]);
  const ready = f.setup("install", "ocr");
  assert.equal(ready.status, "ready");
  assert.equal(ready.models.status, "ready");
  assert.deepEqual(ready.performed, ["install_models"]);
  assert.deepEqual(f.probes[0], ["doctor", "--knowledge-root", f.root, "--capability", "documents", "--json"]);
});

test("explicit environment-only repair does not infer a knowledge root", (t) => {
  const f = fixture(t);
  f.installCli();
  const ready = runSetup(["install", "--environment-only", "--json"], f.context);
  assert.equal(ready.status, "ready");
  assert.equal(ready.knowledge_root, null);
  assert.deepEqual(ready.performed, ["setup_python"]);
});

test("unknown, dangling, and repeated capability flags cannot start Setup", (t) => {
  const f = fixture(t);
  for (const flag of [["--capability", "remote"], ["--capability"],
    ["--capability", "documents", "--capability", "ocr"]]) {
    const result = runSetup(["install", "--environment-only", ...flag, "--json"], f.context);
    assert.equal(result.status, "blocked");
    assert.equal(result.diagnostics[0].code, "INVALID_ARGUMENT");
  }
  assert.deepEqual(f.probes, []);
});

test("Windows share paths never reach local installers", { skip: process.platform !== "win32" }, (t) => {
  const f = fixture(t);
  const blocked = runSetup(["install", "--knowledge-root", "\\\\invalid.invalid\\share\\knowledge", "--json"], f.context);
  assert.equal(blocked.status, "blocked");
  assert.equal(blocked.diagnostics[0].code, "REMOTE_EXECUTION_REQUIRED");
  assert.deepEqual(f.changes(), []);
});

test("retry uses models already installed before an npm CLI failure", (t) => {
  const f = fixture(t);
  f.state.cliInstallError = true;
  const failed = f.setup("install", "ocr");
  assert.equal(failed.status, "blocked");
  assert.equal(failed.diagnostics.at(-1).code, "NPM_INSTALL_FAILED");
  assert.deepEqual(failed.performed, ["install_models"]);
  f.state.cliInstallError = false;
  const ready = f.setup("install", "ocr");
  assert.equal(ready.status, "ready");
  assert.deepEqual(ready.performed, ["install_cli", "setup_python"]);
});

test("invalid roots, nondependency diagnostics, absent pip and conflicting npm registry block writes", async (t) => {
  await t.test("missing root", (child) => {
    const f = fixture(child);
    const blocked = runSetup(["install", "--knowledge-root", path.join(f.root, "missing"), "--json"], f.context);
    assert.equal(blocked.status, "blocked");
    assert.equal(blocked.diagnostics[0].code, "KNOWLEDGE_ROOT_UNAVAILABLE");
    assert.deepEqual(f.changes(), []);
  });
  await t.test("installed CLI reports invalid configuration", (child) => {
    const f = fixture(child);
    f.installCli();
    f.state.brokenConfig = true;
    const blocked = f.setup("install");
    assert.equal(blocked.status, "blocked");
    assert.ok(blocked.diagnostics.some(({ code }) => code === "CONFIG_INVALID"));
    assert.deepEqual(f.changes(), []);
  });
  await t.test("installed CLI reports a different root", (child) => {
    const f = fixture(child);
    f.installCli();
    f.state.reportedRoot = path.join(f.root, "wrong root");
    const blocked = f.setup("install", "documents");
    assert.equal(blocked.status, "blocked");
    assert.equal(blocked.diagnostics.at(-1).code, "KNOWLEDGE_ROOT_CHECK_FAILED");
    assert.deepEqual(f.changes(), []);
  });
  await t.test("supported Python has no pip", (child) => {
    const f = fixture(child);
    f.state.pip = false;
    const blocked = f.setup("install");
    assert.equal(blocked.status, "blocked");
    assert.ok(blocked.diagnostics.some(({ code }) => code === "DEPENDENCY_PIP_MISSING"));
    assert.deepEqual(f.changes(), []);
  });
  await t.test("installed CLI reports missing pip from rooted diagnostics", (child) => {
    const f = fixture(child);
    f.installCli();
    f.state.pip = false;
    const blocked = f.setup("install", "documents");
    assert.equal(blocked.status, "blocked");
    assert.ok(blocked.diagnostics.some(({ code }) => code === "DEPENDENCY_PIP_MISSING"));
    assert.deepEqual(f.changes(), []);
  });
  await t.test("scoped registry overrides the approved registry", (child) => {
    const f = fixture(child);
    f.state.registry = "https://wrong.example.invalid";
    const blocked = f.setup("install");
    assert.equal(blocked.status, "blocked");
    assert.equal(blocked.diagnostics.at(-1).code, "NPM_REGISTRY_CONFLICT");
    assert.deepEqual(f.changes(), []);
  });
});

test("does not report ready when Python changed during capability setup", (t) => {
  const f = fixture(t);
  f.installCli();
  f.state.setupPython = path.join(f.root, "different python");
  const blocked = f.setup("install", "documents");
  assert.equal(blocked.status, "blocked");
  assert.equal(blocked.diagnostics.at(-1).code, "DEPENDENCY_INSTALL_FAILED");
  assert.deepEqual(blocked.performed, []);
});
