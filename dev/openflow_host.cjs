'use strict';

// The program and execution account are reusable. Every host owns its own
// OpenFlow state; this launcher never resets a binding or conversation store.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function inside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === '' || (!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${path.sep}`));
}

function rejectLinkedAncestors(filename) {
  for (let current = filename; ; current = path.dirname(current)) {
    try {
      if (fs.lstatSync(current).isSymbolicLink()) throw new Error(`Writable host paths cannot use directory links: ${current}`);
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (path.dirname(current) === current) break;
  }
}

function loadConfig(filename) {
  const config = JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, ''));
  if (config.schemaVersion !== 1) throw new Error('Expected host config schemaVersion 1');
  for (const name of ['site', 'home', 'data', 'executionHome', 'python', 'toolkit', 'npmBin', 'codexLauncher', 'stateFile', 'stopFile']) {
    if (typeof config[name] !== 'string' || !path.isAbsolute(config[name])) throw new Error(`${name} must be an absolute path`);
    config[name] = path.resolve(config[name]);
  }
  if (config.host !== '127.0.0.1') throw new Error('Local development hosts must bind 127.0.0.1');
  if (!Number.isInteger(config.port) || config.port < 1024 || config.port > 65535) throw new Error('Expected an explicit local port from 1024 to 65535');
  if (!inside(config.data, config.home) || config.data === config.home) throw new Error('data must be inside its host home');
  if (inside(config.home, config.site) || inside(config.site, config.home) || inside(config.home, config.executionHome) || inside(config.executionHome, config.home)) {
    throw new Error('Program, OpenFlow home and execution account must be separate');
  }
  if (!inside(config.toolkit, config.executionHome)) throw new Error('toolkit must belong to the selected execution account');
  const controlRoot = path.dirname(path.resolve(filename));
  for (const file of [config.stateFile, config.stopFile]) {
    if (!inside(file, controlRoot) || inside(file, config.home) || inside(file, config.executionHome) || inside(file, config.site) || file === path.resolve(filename)) {
      throw new Error('Control files must be separate from program, account and host data');
    }
  }
  if (config.stateFile === config.stopFile) throw new Error('State and stop files must be different');
  for (const writable of [config.home, config.data, config.stateFile, config.stopFile,
    ...['local', 'roaming', 'state'].map(name => path.join(config.home, 'platform-data', name))]) rejectLinkedAncestors(writable);
  for (const file of [path.join(config.site, 'src/master/master.js'), config.python, config.codexLauncher, path.join(config.toolkit, 'knowledge.py')]) {
    if (!fs.statSync(file).isFile()) throw new Error(`Required file is missing: ${file}`);
  }
  if (config.codexHome && !path.isAbsolute(config.codexHome)) throw new Error('codexHome must be absolute');
  return config;
}

function environment(config, inherited = process.env) {
  const env = { ...inherited };
  const codexHome = config.codexHome || inherited.CODEX_HOME || path.join(os.homedir(), '.codex');
  for (const key of Object.keys(env)) if (key.startsWith('OPENFLOW_')) delete env[key];
  Object.assign(env, {
    NODE_ENV: 'production', HOST: config.host, PORT: String(config.port),
    OPENFLOW_HOME: config.home, DATA_DIR: config.data, OPENFLOW_LEGACY_SOURCE: 'none',
    USERPROFILE: config.executionHome, HOME: config.executionHome,
    LOCALAPPDATA: path.join(config.home, 'platform-data', 'local'),
    APPDATA: path.join(config.home, 'platform-data', 'roaming'),
    XDG_STATE_HOME: path.join(config.home, 'platform-data', 'state'),
    CODEX_HOME: codexHome, CODEX_CLI_PATH: config.codexLauncher,
    OPENFLOW_KNOWLEDGE_TOOLKIT_ROOT: config.toolkit,
    OPENFLOW_KNOWLEDGE_PYTHON: config.python, HIMATE_KNOWLEDGE_PYTHON: config.python,
    PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
    PATH: [config.npmBin, path.dirname(config.python), path.dirname(process.execPath), inherited.PATH || inherited.Path || ''].join(path.delimiter)
  });
  return env;
}

function start(config, filename) {
  if (fs.existsSync(config.stopFile)) throw new Error('Host has a stop marker; inspect it before restarting');
  if (fs.existsSync(config.stateFile)) {
    const previous = JSON.parse(fs.readFileSync(config.stateFile, 'utf8'));
    if (Number.isInteger(previous.pid) && previous.pid > 0) {
      try { process.kill(previous.pid, 0); throw new Error('Recorded host PID is still alive; verify the existing instance'); }
      catch (error) { if (error.code !== 'ESRCH') throw error; }
    }
  }
  const resolved = environment(config);
  for (const key of Object.keys(process.env)) if (key.startsWith('OPENFLOW_')) delete process.env[key];
  Object.assign(process.env, resolved);
  for (const directory of [config.home, config.data, config.executionHome, process.env.LOCALAPPDATA, process.env.APPDATA, process.env.XDG_STATE_HOME, path.dirname(config.stateFile)]) fs.mkdirSync(directory, { recursive: true });
  process.chdir(config.site);
  const state = { schemaVersion: 1, pid: process.pid, status: 'starting', config: path.resolve(filename), url: `http://${config.host}:${config.port}`, home: config.home, startedAt: new Date().toISOString() };
  const save = () => fs.writeFileSync(config.stateFile, JSON.stringify(state, null, 2));
  save();
  const application = require(path.join(config.site, 'src/master/master.js'));
  const timer = setInterval(() => {
    if (!fs.existsSync(config.stopFile)) return;
    clearInterval(timer);
    state.status = 'stopping'; save();
    if (typeof application.shutdown !== 'function') throw new Error('OpenFlow has no graceful shutdown entry');
    void application.shutdown(0);
  }, 500);
  timer.unref();
  void Promise.resolve(application).then(() => { state.status = 'running'; save(); });
  process.once('exit', () => { state.status = 'stopped'; state.stoppedAt = new Date().toISOString(); save(); });
}

if (require.main === module) {
  const [filename, option, ...extra] = process.argv.slice(2);
  if (!filename || extra.length || (option && option !== '--check')) {
    console.error('Usage: node dev/openflow_host.cjs <config.json> [--check]');
    process.exitCode = 2;
  } else {
    try {
      const config = loadConfig(filename);
      if (option === '--check') console.log(JSON.stringify({ status: 'valid', site: config.site, home: config.home, data: config.data, executionHome: config.executionHome, port: config.port }));
      else start(config, filename);
    } catch (error) { console.error(error.message); process.exitCode = 2; }
  }
}

module.exports = { loadConfig, environment };
