'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { loadConfig, environment } = require('./openflow_host.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'factum-host-config-'));
  t.after(() => fs.rmSync(root, { recursive: true }));
  const config = { schemaVersion: 1, site: path.join(root, 'site'), home: path.join(root, 'hosts/cold'), data: path.join(root, 'hosts/cold/data'), executionHome: path.join(root, 'account'), python: path.join(root, 'python.exe'), toolkit: path.join(root, 'account/.himate/knowledge'), npmBin: path.join(root, 'npm-prefix'), codexLauncher: path.join(root, 'codex.js'), host: '127.0.0.1', port: 58880, stateFile: path.join(root, 'hosts/process.json'), stopFile: path.join(root, 'hosts/stop') };
  for (const file of [path.join(config.site, 'src/master/master.js'), config.python, config.codexLauncher, path.join(config.toolkit, 'knowledge.py')]) {
    fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, '');
  }
  const filename = path.join(root, 'launch.json');
  const write = () => fs.writeFileSync(filename, JSON.stringify(config));
  write();
  return { config, filename, write };
}

test('public check validates resources without creating or resetting host data', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [__dirname+'/openflow_host.cjs', f.filename, '--check'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).status, 'valid');
  assert.equal(fs.existsSync(f.config.home), false);
  assert.equal(fs.existsSync(f.config.stateFile), false);
});

test('shared runtime retains independent OpenFlow data and removes inherited instance tokens', t => {
  const f = fixture(t);
  const config = loadConfig(f.filename);
  const inherited = { PATH: 'original', CODEX_HOME: path.join(path.dirname(f.filename), 'oauth'), OPENFLOW_DB_PATH: 'wrong-db', OPENFLOW_ASK_INTERNAL_TOKEN: 'wrong-token' };
  const first = environment(config, inherited);
  const second = environment({ ...config, home: config.home+'2', data: config.data+'2', port: 58881 }, inherited);
  assert.equal(first.HOME, second.HOME);
  assert.notEqual(first.DATA_DIR, second.DATA_DIR);
  assert.notEqual(first.LOCALAPPDATA, second.LOCALAPPDATA);
  assert.notEqual(first.APPDATA, second.APPDATA);
  assert.notEqual(first.XDG_STATE_HOME, second.XDG_STATE_HOME);
  assert.equal(path.relative(config.home, first.LOCALAPPDATA).startsWith('..'), false);
  assert.equal(first.CODEX_HOME, inherited.CODEX_HOME);
  assert.equal(first.OPENFLOW_DB_PATH, undefined);
  assert.equal(first.OPENFLOW_ASK_INTERNAL_TOKEN, undefined);
});

test('rejects data outside the host and an overlapping program directory', t => {
  const f = fixture(t);
  f.config.data = path.join(path.dirname(f.filename), 'outside'); f.write();
  assert.throws(() => loadConfig(f.filename), /data must be inside/);
  f.config.data = path.join(f.config.home, 'data'); f.config.home = f.config.site; f.config.data = path.join(f.config.home, 'data'); f.write();
  assert.throws(() => loadConfig(f.filename), /must be separate/);
});

test('rejects unexpected network exposure and relative resources', t => {
  const f = fixture(t);
  f.config.host = '0.0.0.0'; f.write(); assert.throws(() => loadConfig(f.filename), /127.0.0.1/);
  f.config.host = '127.0.0.1'; f.config.python = 'python'; f.write(); assert.throws(() => loadConfig(f.filename), /python must be an absolute/);
});

test('control files cannot overwrite existing host data or runtime configuration', t => {
  const f = fixture(t);
  f.config.stateFile = path.join(f.config.data, 'settings.json'); f.write();
  assert.throws(() => loadConfig(f.filename), /Control files must be separate/);
  f.config.stateFile = f.filename; f.write();
  assert.throws(() => loadConfig(f.filename), /Control files must be separate/);
});

for (const location of ['home', 'data', 'control', 'platform']) {
  test(`rejects a linked ${location} path without changing its target`, t => {
    const f = fixture(t);
    const target = path.join(path.dirname(f.filename), 'other-host');
    fs.mkdirSync(target);
    fs.writeFileSync(path.join(target, 'preserve.txt'), 'existing user state');
    const alias = location === 'control' ? path.join(path.dirname(f.filename), 'controls')
      : location === 'platform' ? path.join(f.config.home, 'platform-data') : f.config[location];
    fs.mkdirSync(path.dirname(alias), { recursive: true });
    try { fs.symlinkSync(target, alias, process.platform === 'win32' ? 'junction' : 'dir'); }
    catch (error) { if (error.code === 'EPERM') { t.skip('Directory link permission unavailable'); return; } throw error; }
    if (location === 'control') f.config.stateFile = path.join(alias, 'process.json');
    f.write();
    assert.throws(() => loadConfig(f.filename), /cannot use directory links/);
    assert.equal(fs.readFileSync(path.join(target, 'preserve.txt'), 'utf8'), 'existing user state');
  });
}
