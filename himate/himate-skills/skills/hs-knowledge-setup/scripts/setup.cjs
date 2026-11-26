#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CLI = "@himate/knowledge-cli";
const MODELS = "@himate/knowledge-models";
const REGISTRY = "http://10.143.57.12:4873";
const DISPATCHER = "distribution/npm/knowledge.js";
const WINDOWS = process.platform === "win32";
const DEPENDENCY_GAPS = new Set(["DEPENDENCY_UNAVAILABLE", "YAML_PARSER_UNAVAILABLE"]);
const MODEL_FILES = [
  "docling-project--docling-layout-heron/config.json",
  "docling-project--docling-layout-heron/preprocessor_config.json",
  "docling-project--docling-layout-heron/model.safetensors",
  "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
  "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
  "RapidOcr/PP-OCRv6_det_small.onnx",
  "RapidOcr/PP-OCRv6_rec_small.onnx",
  "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
];

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  throw error;
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT" || error instanceof SyntaxError) return null;
    throw error;
  }
}

function ordinaryFile(file) {
  return fs.lstatSync(file, { throwIfNoEntry: false })?.isFile();
}

function ordinaryDirectory(file) {
  return fs.lstatSync(file, { throwIfNoEntry: false })?.isDirectory();
}

function parseArgs(args) {
  const [action] = args;
  const rootIndex = args.indexOf("--knowledge-root");
  const root = rootIndex > 0 ? args[rootIndex + 1] : null;
  const expected = rootIndex > 0 ? [action, "--knowledge-root", root, "--json"] : [action, "--environment-only", "--json"];
  if (!["check", "install"].includes(action) || args.length !== expected.length
      || expected.some((value) => !value || args.filter((arg) => arg === value).length !== 1)
      || (rootIndex > 0 && (!path.isAbsolute(root) || /[\r\n\0]/.test(root)))) {
    fail("INVALID_ARGUMENT", "用法：setup.cjs check|install (--knowledge-root <绝对路径> | --environment-only) --json");
  }
  return { action, root };
}

function samePath(a, b) {
  if (typeof a !== "string" || !path.isAbsolute(a)) return false;
  return WINDOWS ? path.normalize(a).toLowerCase() === path.normalize(b).toLowerCase() : path.normalize(a) === path.normalize(b);
}

function inside(parent, file) {
  const relative = path.relative(parent, file);
  return !relative || (!path.isAbsolute(relative) && relative !== ".." && !relative.startsWith(".." + path.sep));
}

function windowsShare(file) {
  return WINDOWS && (file.toLowerCase().startsWith("\\\\?\\unc\\") || /^\\\\[^?.]/.test(file));
}

function confirmRoot(root, toolRoot) {
  if (windowsShare(root)) fail("REMOTE_EXECUTION_REQUIRED", "请在已确认的 Linux 对端运行 Setup。");
  if (!ordinaryDirectory(root)) fail("KNOWLEDGE_ROOT_UNAVAILABLE", "指定知识根不是可用的普通目录。");
  const actual = fs.realpathSync.native(root);
  if (windowsShare(actual)) fail("REMOTE_EXECUTION_REQUIRED", "Windows 共享盘需要在已确认的 Linux 对端运行 Setup。");
  if (!ordinaryFile(path.join(actual, "config.yml")) || !ordinaryDirectory(path.join(actual, "docs-raw"))
      || !ordinaryDirectory(path.join(actual, "knowledge"))
      || inside(toolRoot, actual) || inside(actual, toolRoot)) {
    fail("KNOWLEDGE_ROOT_UNAVAILABLE", "请选择含 config.yml、docs-raw 和 knowledge 的独立知识根。");
  }
  return actual;
}

function pathExecutable(name, search = process.env.PATH) {
  for (const entry of (search || "").split(path.delimiter)) {
    const directory = entry.replace(/^"|"$/g, "");
    if (!path.isAbsolute(directory)) continue;
    const file = path.join(directory, name);
    try {
      if (!fs.statSync(file).isFile()) continue;
      fs.accessSync(file, fs.constants.X_OK);
      return file;
    } catch {
      // The entry contains no executable with this name.
    }
  }
  return null;
}

function npmCommand(find) {
  if (!WINDOWS) {
    const executable = find("npm");
    return executable ? [executable] : null;
  }
  const command = find("npm.cmd");
  if (!command) return null;
  const moduleRoot = path.join(path.dirname(command), "node_modules", "npm");
  const entry = path.join(moduleRoot, "bin", "npm-cli.js");
  // Launch the npm CLI itself so cmd.exe never interprets arguments or paths.
  return ordinaryFile(entry) && readJson(path.join(moduleRoot, "package.json"))?.name === "npm"
    ? [process.execPath, entry] : null;
}

function run(argv, args, timeout = 30000) {
  return spawnSync(argv[0], [...argv.slice(1), ...args], {
    cwd: os.tmpdir(), windowsHide: true, encoding: "utf8", timeout, maxBuffer: 1024 * 1024,
  });
}

function probePython(find, execute, needsPip) {
  // Match the npm launcher's interpreter selection, including its py.exe order.
  const configured = process.env.HIMATE_KNOWLEDGE_PYTHON;
  const candidates = path.isAbsolute(configured || "") ? [[configured]] : [];
  if (WINDOWS) {
    const systemRoot = process.env.SystemRoot || "";
    const py = find("py.exe") || (path.isAbsolute(systemRoot) && find("py.exe", systemRoot));
    if (py) for (const version of ["-3.11", "-3.12", "-3.10"]) candidates.push([py, version]);
  }
  const names = WINDOWS ? ["python.exe", "python3.exe"] : ["python3", "python", "python3.11", "python3.12", "python3.10"];
  for (const name of names) {
    const entry = find(name);
    if (entry) candidates.push([entry]);
  }
  for (const candidate of candidates) {
    const version = execute(candidate, ["-I", "-B", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]);
    if (version.status !== 0 || !/^3\.(10|11|12)$/.test(version.stdout.trim())) continue;
    if (!needsPip) return;
    const pip = execute(candidate, ["-E", "-B", "-c", "from importlib.util import find_spec; raise SystemExit(find_spec('pip') is None)"]);
    if (pip.status !== 0) fail("DEPENDENCY_PIP_MISSING", "所选 Python 缺少 pip，请选择带 pip 的 Python 3.10–3.12。");
    return;
  }
  fail("PYTHON_UNAVAILABLE", "执行端需要 Python 3.10–3.12，可通过 HIMATE_KNOWLEDGE_PYTHON 指定。");
}

function findKnowledge(toolRoot) {
  const marker = readJson(path.join(toolRoot, ".install.json"));
  if (!marker && ordinaryFile(path.join(toolRoot, "knowledge.py"))) {
    fail("KNOWLEDGE_INSTALL_UNVERIFIED", "发现未登记的知识工具目录，请先确认安装来源。");
  }
  const packageRoot = marker?.packageRoot;
  if (marker?.package !== CLI || typeof packageRoot !== "string" || !path.isAbsolute(packageRoot)
      || path.basename(packageRoot) !== "knowledge-cli" || path.basename(path.dirname(packageRoot)) !== "@himate"
      || path.basename(path.dirname(path.dirname(packageRoot))) !== "node_modules") return null;
  const pkg = readJson(path.join(packageRoot, "package.json"));
  const runtime = readJson(path.join(toolRoot, "runtime", "manifest.json"));
  if (pkg?.name !== CLI || typeof pkg.version !== "string" || pkg.version !== marker.version
      || pkg.bin?.knowledge !== DISPATCHER || runtime?.version !== marker.version
      || !ordinaryFile(path.join(toolRoot, "knowledge.py"))) return null;
  const dispatcher = path.join(packageRoot, DISPATCHER);
  if (!ordinaryFile(dispatcher) || createHash("sha256").update(fs.readFileSync(dispatcher)).digest("hex") !== marker.launcherSha256) return null;
  return { argv: [process.execPath, dispatcher], version: pkg.version, tool_root: toolRoot };
}

function modelsPresent(toolRoot) {
  const models = path.join(toolRoot, "tools", "deploy", "models");
  const manifest = readJson(path.join(models, "manifest.json"));
  if (manifest?.model_set !== "docling-cpu" || !Array.isArray(manifest.files)) return false;
  const sizes = new Map(manifest.files.map((file) => [file?.path, file?.bytes]));
  // The package's postinstall verifies the full model digests. Here we detect
  // missing or incomplete assets without hashing hundreds of MB on every run.
  return MODEL_FILES.every((name) => {
    let file = path.join(models, "docling-cpu");
    for (const segment of name.split("/")) {
      if (!ordinaryDirectory(file)) return false;
      file = path.join(file, segment);
    }
    const stat = fs.lstatSync(file, { throwIfNoEntry: false });
    return stat?.isFile() && stat.size > 0 && stat.size === sizes.get(name);
  });
}

function subprocessReport(result) {
  try {
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

function diagnostics(payload) {
  return Array.isArray(payload?.diagnostics)
    ? payload.diagnostics.filter((item) => typeof item?.code === "string" && typeof item.message === "string")
      .map(({ code, message }) => ({ code, message }))
    : [];
}

function checkInstalled(knowledge, root, find, execute, receipt) {
  const envRun = execute(knowledge.argv, ["doctor", "--environment-only", "--dependencies-only", "--json"]);
  const environment = subprocessReport(envRun);
  if (envRun.error || envRun.status !== 0 || !["ready", "needs_install"].includes(environment?.status)
      || environment.toolkit_version !== knowledge.version || !samePath(environment.tool_root, knowledge.tool_root)
      || !path.isAbsolute(environment.python || "")) {
    if (!environment) {
      probePython(find, execute, false);
      fail("KNOWLEDGE_START_FAILED", "已安装的 knowledge 无法运行，请确认执行端的 Python 和 CLI。");
    }
    receipt.diagnostics.push(...diagnostics(environment));
    fail("ENVIRONMENT_CHECK_FAILED", "无法核对已安装 CLI 的版本和执行端。");
  }
  receipt.knowledge = { ...knowledge, python: environment.python };
  receipt.diagnostics.push(...diagnostics(environment));
  if (receipt.diagnostics.some(({ code }) => code === "DEPENDENCY_PIP_MISSING")) return false;
  if (root) {
    const probe = execute(knowledge.argv, ["doctor", "--knowledge-root", root, "--json"]);
    const rooted = subprocessReport(probe);
    const gaps = diagnostics(rooted);
    const verifiedTarget = samePath(rooted?.data?.knowledge_root, root)
      && samePath(rooted.data.tool_root, knowledge.tool_root)
      && samePath(rooted.data.python, environment.python)
      && rooted.data.runtime_version === knowledge.version;
    if (verifiedTarget && probe.status === 3 && environment.status === "needs_install" && rooted.status === "blocked"
        && gaps.length > 0 && gaps.every(({ code }) => DEPENDENCY_GAPS.has(code))) {
      // The existing CLI classifies the only observed gaps as installable.
    } else if (!verifiedTarget || probe.status !== 0 || rooted?.status !== "ok" || rooted.phase !== "ready") {
      receipt.diagnostics.push(...gaps);
      if (!gaps.length) receipt.diagnostics.push({ code: "KNOWLEDGE_ROOT_CHECK_FAILED", message: "未能核对所选知识根和当前执行端。" });
      return false;
    }
  }
  if (environment.status === "needs_install") receipt.planned.push("setup_python");
  else {
    const version = execute(knowledge.argv, ["--version"]);
    if (version.status !== 0 || version.stdout.trim() !== "knowledge " + knowledge.version) {
      fail("KNOWLEDGE_VERSION_MISMATCH", "实际 knowledge 版本与 npm 安装标记不一致。");
    }
  }
  return true;
}

function verifyNpmSettings(npm, execute) {
  const get = (key) => {
    const result = execute(npm, ["config", "get", key, "--global"]);
    if (result.status !== 0) fail("NPM_CONFIG_UNAVAILABLE", "无法读取执行账户的 npm 配置。");
    return result.stdout.trim();
  };
  if (get("ignore-scripts") === "true") fail("NPM_SCRIPTS_DISABLED", "执行账户禁用了 npm 安装脚本，请先确认其策略。");
  const scoped = get("@himate:registry");
  if (scoped && scoped !== "undefined" && scoped !== "null" && scoped.replace(/\/$/, "") !== REGISTRY) {
    fail("NPM_REGISTRY_CONFLICT", "执行账户的 @himate 软件源与指定内网源不一致，请先确认配置。");
  }
}

function runSetup(args, { toolRoot = path.join(os.homedir(), ".himate", "knowledge"), find = pathExecutable, execute = run } = {}) {
  const receipt = { status: "blocked", knowledge_root: null, knowledge: null, models: { status: "missing" },
    hostname: os.hostname(), platform: process.platform, planned: [], performed: [], diagnostics: [] };
  try {
    const { action, root } = parseArgs(args);
    const actualRoot = root ? confirmRoot(root, toolRoot) : null;
    receipt.knowledge_root = actualRoot;
    const inspect = () => {
      receipt.planned = [];
      receipt.diagnostics = [];
      receipt.knowledge = null;
      receipt.models.status = modelsPresent(toolRoot) ? "ready" : "missing";
      const knowledge = findKnowledge(toolRoot);
      if (knowledge && !checkInstalled(knowledge, actualRoot, find, execute, receipt)) return null;
      if (receipt.models.status === "missing") {
        receipt.planned.unshift("install_models");
        receipt.diagnostics.push({ code: "PARSER_MODELS_REQUIRED", message: "执行端缺少完整的预置 OCR 模型。" });
      }
      if (!knowledge) {
        receipt.planned.push("install_cli");
        receipt.diagnostics.push({ code: "KNOWLEDGE_CLI_NOT_FOUND", message: "执行端缺少可核对的 npm Knowledge CLI。" });
        probePython(find, execute, true);
      }
      const needsNpm = receipt.planned.some((step) => step === "install_models" || step === "install_cli");
      const npm = needsNpm ? npmCommand(find) : null;
      if (needsNpm && !npm) fail("NPM_UNAVAILABLE", "执行端缺少可用的 npm。请先确认 Node.js 和 npm 安装。");
      return { npm, knowledge };
    };

    let state = inspect();
    if (!state) return receipt;
    if (action === "install" && receipt.planned.length) {
      if (state.npm) verifyNpmSettings(state.npm, execute);
      for (const [step, pkg] of [["install_models", MODELS], ["install_cli", CLI]]) {
        if (!receipt.planned.includes(step)) continue;
        const installed = execute(state.npm, ["install", "--global", pkg, "--registry", REGISTRY, "--allow-scripts=" + pkg], 30 * 60 * 1000);
        if (installed.error || installed.status !== 0) {
          fail("NPM_INSTALL_FAILED", "npm 安装 " + pkg + " 失败，请在实际执行端检查网络、权限和 npm 日志。");
        }
        receipt.performed.push(step);
      }
      state = inspect();
      if (!state) return receipt;
      if (state.npm) fail("NPM_INSTALL_INCOMPLETE", "npm 返回成功，但模型或 CLI 安装回执仍缺失。");
      if (receipt.planned.includes("setup_python")) {
        // The npm package owns its executable. A dependency-only setup never
        // enters the manual Windows launcher registration or modifies user PATH.
        const setup = execute(state.knowledge.argv, ["setup", "--dependencies-only", "--json"], 55 * 60 * 1000);
        const result = subprocessReport(setup);
        if (typeof result?.log_path === "string" && path.isAbsolute(result.log_path)
            && inside(path.join(toolRoot, "logs"), result.log_path)) receipt.log_path = result.log_path;
        if (setup.error || setup.status !== 0 || result?.status !== "ready"
            || result.toolkit_version !== state.knowledge.version
            || !samePath(result.tool_root, toolRoot) || !samePath(result.python, receipt.knowledge.python)) {
          receipt.diagnostics.push(...diagnostics(result));
          fail("DEPENDENCY_INSTALL_FAILED", "执行端依赖安装或复查失败，请检查 knowledge setup 的执行端日志。");
        }
        receipt.performed.push("setup_python");
        state = inspect();
        if (!state) return receipt;
      }
      if (receipt.planned.length) fail("SETUP_INCOMPLETE", "安装后复查仍有缺项。");
    }
    receipt.status = receipt.planned.length ? "needs_setup" : "ready";
    return receipt;
  } catch (error) {
    receipt.diagnostics.push({ code: error.code || "ENVIRONMENT_UNAVAILABLE", message: error.message });
    return receipt;
  }
}

if (require.main === module) {
  const receipt = runSetup(process.argv.slice(2));
  process.stdout.write(JSON.stringify(receipt) + "\n");
  process.exitCode = { ready: 0, needs_setup: 2, blocked: 1 }[receipt.status];
}

module.exports = { runSetup };
