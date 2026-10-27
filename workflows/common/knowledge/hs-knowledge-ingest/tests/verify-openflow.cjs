/* Offline engine-contract checks. No OpenFlow server or knowledge writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

function option(name) {
  const index = process.argv.indexOf(name);
  return index < 0 ? null : process.argv[index + 1];
}

const openflowArgument = option('--openflow-root');
if (!openflowArgument) throw new Error('--openflow-root must identify a local OpenFlow checkout');
const openflow = path.resolve(openflowArgument);
const load = relative => require(path.join(openflow, relative));
const YAML = require(require.resolve('yaml', { paths: [openflow, __dirname] }));
const packageRoot = path.resolve(__dirname, '..');
const repo = path.resolve(packageRoot, '../../../..');
const output = path.resolve(option('--output-dir') || path.join(repo, '.scratch/ingest-workflow-checks'));
fs.mkdirSync(output, { recursive: true });
const fixture = fs.mkdtempSync(path.join(output, 'engine-'));
const sourceSkills = path.join(repo, 'skills/common/knowledge');
for (const item of fs.readdirSync(sourceSkills, { withFileTypes: true })) {
  const source = path.join(sourceSkills, item.name);
  if (!item.isDirectory() || !fs.existsSync(path.join(source, 'SKILL.md'))) continue;
  const target = path.join(fixture, 'config/skills', item.name);
  fs.mkdirSync(target, { recursive: true });
  fs.copyFileSync(path.join(source, 'SKILL.md'), path.join(target, 'SKILL.md'));
  if (fs.existsSync(path.join(source, 'artifacts'))) {
    fs.cpSync(path.join(source, 'artifacts'), path.join(target, 'artifacts'), { recursive: true });
  }
}
const installed = path.join(fixture, 'config/workflow-templates/hs-knowledge-ingest/workflow.yaml');
fs.mkdirSync(path.dirname(installed), { recursive: true });
fs.copyFileSync(path.join(packageRoot, 'workflow.yaml'), installed);
fs.copyFileSync(path.join(packageRoot, 'layouts.yaml'), path.join(path.dirname(installed), 'layouts.yaml'));
const template = YAML.parse(fs.readFileSync(installed, 'utf8'));
const nodes = new Map(template.nodes.map(node => [node.id, node]));
const { loadSkillRegistry } = load('src/config/skill-registry.js');
const { loadSkillArtifactContracts } = load('src/config/skill-artifact-loader.js');
const { validateWorkflowTemplate } = load('src/config/workflow-template-validator.js');
const { loadWorkflowTemplateRecordById } = load('src/config/workflow-template-loader.js');
const { compileWorkflowTemplateForConversation } = load('src/orchestration/workflow-template-compiler.js');
const { createWorkflowRuntimeService } = load('src/orchestration/workflow-runtime-service.js');
const { guardAgentWorkflowRuntimePatch, normalizeUnifiedWorkflowPayload, normalizeAgentWorkflowCallback }
  = load('src/orchestration/workflow-runtime-protocol-guard.js');
const { validateWorkflowHandoffToolInput } = load('src/orchestration/workflow-handoff-tool.js');
const { validateArtifactLocation } = load('src/orchestration/workflow-artifact-location.js');
const { resolveArtifactDuties } = load('src/orchestration/workflow-artifact-resolver.js');
const { createWorkflowArtifactRegistry } = load('src/orchestration/workflow-artifact-registry.js');
const contracts = loadSkillArtifactContracts(fixture);
const evidence = { openflow, fixture, validation: null, stops: [], paths: [], artifactLocations: [] };
process.on('exit', () => fs.writeFileSync(path.join(fixture, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n'));

async function start(entry = template.entry_node, serviceOptions = {}) {
  const records = new Map();
  const conversation = {
    id: `check-${entry}`, aiMembers: ['coder', 'reviewer'],
    workflowBinding: { id: `binding-${entry}`, type: 'workflow' },
    workflowTemplate: { ...template, entry_node: entry, entryNode: entry }
  };
  const service = createWorkflowRuntimeService({
    projectRoot: fixture,
    store: { get: id => records.get(id) || null, upsert: (id, record) => {
      records.set(id, record); return record;
    } }, ...serviceOptions
  });
  return { conversation, service, runtime: await service.getForConversation(conversation) };
}

async function advance(state, exitId) {
  const node = nodes.get(state.runtime.currentNode);
  const exit = node.exits.find(item => item.id === exitId);
  assert.ok(exit, `${node.id} must expose ${exitId}`);
  state.runtime = await state.service.patchForConversation(state.conversation, {
    currentNode: exit.target, _transitionExitId: exit.id
  }, node.owner, state.runtime.version);
  return state.runtime;
}

async function walk(label, exits) {
  const state = await start();
  const visited = [state.runtime.currentNode];
  for (const exit of exits) { await advance(state, exit); visited.push(state.runtime.currentNode); }
  evidence.paths.push({ label, visited, flowState: state.runtime.flowState });
  return { ...state, visited };
}

test('official registry, artifact loader, validator, layout and compiler accept the installed package', () => {
  assert.equal(loadSkillRegistry({ projectRoot: fixture }).skillIds.length, 19);
  assert.equal(contracts.length, 22);
  const validation = validateWorkflowTemplate(template, { projectRoot: fixture });
  evidence.validation = { valid: validation.valid, errors: validation.errors };
  assert.deepEqual(validation.errors, []);
  const record = loadWorkflowTemplateRecordById(template.id, fixture);
  assert.equal(record.health.canRun, true);
  assert.equal(record.health.canSave, true);
  assert.deepEqual(Object.keys(record.layout.canvas.nodes).sort(), [...nodes.keys()].sort());
  const compiled = compileWorkflowTemplateForConversation({
    template: record.template, conversationId: 'compiler-check', aiMembers: ['coder', 'reviewer']
  });
  assert.equal(compiled.workflowRuntimePatch.currentNode, 'scan_sources');
  assert.equal(compiled.workflowRuntimePatch.batonHolder, 'coder');
});

test('every business node can retain a blocked stop without ending, advancing or adding a user gate', async t => {
  for (const node of nodes.values()) await t.test(node.id, async () => {
    assert.equal(node.type, 'skill');
    assert.ok(!node.exits.some(exit => exit.id === 'blocked'));
    // OpenFlow auto-completes executable nodes whose only target is __end__.
    assert.ok(node.exits.some(exit => exit.target !== '__end__'));
    assert.match(node.prompt, /Do not call workflow_handoff/);
    assert.match(node.prompt, /resumeCapsule/);
    const state = await start(node.id);
    const patch = guardAgentWorkflowRuntimePatch({ resumeCapsule: {
      goal: 'Finish this ingest', done: ['Saved actual inputs and diagnostics'],
      currentFocus: 'Blocked: missing original; preserve this node and stop this turn'
    } }, { workflowBound: true });
    const stopped = await state.service.patchForConversation(state.conversation, patch, node.owner, state.runtime.version);
    assert.equal(stopped.currentNode, node.id);
    assert.equal(stopped.batonHolder, node.owner);
    assert.equal(stopped.flowState, 'active');
    assert.equal(stopped.pathHistory.length, state.runtime.pathHistory.length);
    assert.match(stopped.resumeCapsule.currentFocus, /Blocked/);
    evidence.stops.push({ node: node.id, currentNode: stopped.currentNode, flowState: stopped.flowState });
  });
});

test('host ToolHandoff and legacy protocols preserve a capsule-only stop without inventing waiting state', () => {
  const capsule = { goal: 'Finish ingest', done: ['Saved the actual stop'], currentFocus: 'Missing original' };
  const unified = normalizeUnifiedWorkflowPayload(capsule, { workflowBound: true });
  assert.equal(unified.kind, 'resume_patch');
  assert.ok(!unified.transition);
  const legacy = normalizeAgentWorkflowCallback({ type: 'workflow_runtime_patch', patch: {
    resumeCapsule: capsule
  } }, { workflowBound: true });
  assert.equal(legacy.kind, 'runtime_patch');
  assert.deepEqual(legacy.workflowRuntimePatch, { resumeCapsule: capsule });
  assert.throws(() => guardAgentWorkflowRuntimePatch({ flowState: 'waiting' }, { workflowBound: true }),
    { code: 'patch_field_forbidden' });
});

test('resuming a document view reaches the independent reviewer before any apply', async () => {
  const state = await walk('unreviewed-view-resume', [
    'resume', 'reviewed', 'passed', 'manual_ready', 'passed', 'recorded', 'applied', 'built', 'checked'
  ]);
  assert.equal(state.visited[1], 'review_content');
  assert.equal(nodes.get('review_content').owner, 'reviewer');
  assert.ok(state.visited.indexOf('review_content') < state.visited.indexOf('apply_view'));
  assert.equal(state.runtime.flowState, 'completed');
});

test('normal mixed content still requires the code check before final lint', async () => {
  const state = await walk('mixed-content', [
    'scanned', 'prepared', 'planned', 'reviewed', 'ready', 'reviewed', 'passed', 'mixed_ready',
    'code_passed', 'passed', 'recorded', 'applied', 'built', 'checked'
  ]);
  assert.ok(state.visited.includes('local_check'));
  assert.equal(state.runtime.flowState, 'completed');
});

test('committed content resumes indexing without inspecting or applying the old view', async () => {
  const state = await walk('committed-index-resume', ['resume_index', 'built', 'checked']);
  assert.ok(!state.visited.includes('apply_view'));
  assert.ok(!state.visited.includes('inspect_candidate'));
  assert.equal(state.runtime.flowState, 'completed');
});

test('a verified candidate generation resumes query/activation without rebuilding or reapplying', async () => {
  const state = await walk('candidate-query-resume', ['resume_queries', 'checked']);
  assert.ok(!state.visited.includes('apply_view'));
  assert.ok(!state.visited.includes('rebuild_index'));
  assert.equal(state.runtime.flowState, 'completed');
  assert.match(nodes.get('query_regression').prompt, /--action verify/);
  assert.match(nodes.get('query_regression').prompt, /expected_active/);
  assert.match(nodes.get('query_regression').prompt, /Never rebase/);
});

test('unchanged completed input ends without creating or applying another record', async () => {
  const state = await walk('unchanged-no-op', ['unchanged']);
  assert.deepEqual(state.visited, ['scan_sources', '__end__']);
  assert.equal(state.runtime.flowState, 'completed');
});

test('first record-only outcomes and interrupted transactions keep their existing completion routes', async () => {
  const records = await walk('new-record-only', ['scanned', 'prepared', 'planned', 'record_only', 'recorded', 'record_only']);
  assert.equal(records.runtime.flowState, 'completed');
  const recovered = await walk('interrupted-content', ['recover', 'recovered', 'built', 'checked']);
  assert.equal(recovered.runtime.flowState, 'completed');
  assert.ok(!recovered.visited.includes('apply_view'));
});

test('returning a candidate requires fresh v3 business inputs and renews content review', async () => {
  const prompt = nodes.get('revise_candidate').prompt;
  const scan = prompt.indexOf('--action scan');
  const prepare = prompt.indexOf('--action prepare', scan);
  const plan = prompt.indexOf('--action plan', prepare);
  const revise = prompt.indexOf('Invoke hs-knowledge-candidate-revise', plan);
  assert.ok(scan >= 0 && prepare > scan && plan > prepare && revise > plan);
  assert.match(prompt, /semantic_plan_ref/);
  assert.match(prompt, /previous_view_ref/);
  assert.match(prompt, /explicit context_ref/);
  assert.match(prompt, /not inherit.*previous view/);
  assert.match(nodes.get('materialize_view').prompt, /explicit context_ref/);
  const state = await start('revise_candidate');
  await advance(state, 'ready');
  assert.equal(state.runtime.currentNode, 'review_content');
});

test('strict official completion validation accepts explicit pointers and rejects an incompatible host root', async () => {
  const produced = new Map();
  let nextId = 0;
  const registry = createWorkflowArtifactRegistry({
    idFactory: () => `artifact-${++nextId}`,
    store: {
      listWorkflowArtifactInstances: async filter => [...produced.values()].filter(item =>
        (!filter.conversationId || item.conversationId === filter.conversationId)
        && (!filter.fromNode || item.fromNode === filter.fromNode)
        && (!filter.artifactId || item.artifactId === filter.artifactId)),
      insertWorkflowArtifactInstance: async record => { produced.set(record.id, record); return record; },
      getWorkflowArtifactInstance: async id => produced.get(id) || null,
      updateWorkflowArtifactInstanceStatus: async (id, status, updatedAt) => {
        const record = { ...produced.get(id), status, updatedAt };
        produced.set(id, record); return record;
      }
    }
  });
  const relative = '.build/operations/completion-check/handoffs/scan_sources/attempt-1/scan.md';
  fs.mkdirSync(path.dirname(path.join(fixture, relative)), { recursive: true });
  fs.writeFileSync(path.join(fixture, relative), '# Synthetic CLI summary\n');
  const completion = { nodeId: 'scan_sources', exitId: 'scanned', artifacts: [{
    id: 'hs-knowledge-source-scan-result', location: { kind: 'markdown_file', path: relative }
  }] };
  const handoff = { exitId: 'scanned', goal: 'Ingest', done: ['Scanned originals'],
    currentFocus: 'Prepare materials', workflowCompletion: completion };
  assert.equal(validateWorkflowHandoffToolInput(handoff, {
    validExitIds: nodes.get('scan_sources').exits.map(exit => exit.id), actorId: 'coder',
    workflowRuntimeSlices: { flowState: 'active', batonHolder: 'coder' }
  }).success, true);
  const normalized = normalizeUnifiedWorkflowPayload(handoff, { workflowBound: true });
  assert.equal(normalized.kind, 'handoff');
  assert.deepEqual(normalized.workflowCompletion, completion);
  const compatible = await start('scan_sources', {
    artifactRegistry: registry, artifactContracts: contracts,
    workflowArtifacts: { enforcementEnabled: true, projectRoot: fixture }
  });
  const payload = state => ({ conversation: state.conversation, currentRuntime: state.runtime,
    patch: { currentNode: 'prepare_material', _transitionExitId: 'scanned' }, completion, updatedBy: 'coder' });
  const accepted = await compatible.service.validateWorkflowTransitionArtifacts(payload(compatible));
  assert.equal(accepted.ok, true);
  assert.ok(produced.size > 0);
  const installRoot = fs.mkdtempSync(path.join(output, 'separate-host-'));
  const incompatible = await start('scan_sources', {
    artifactRegistry: registry, artifactContracts: contracts,
    workflowArtifacts: { enforcementEnabled: true, projectRoot: installRoot }
  });
  await assert.rejects(() => incompatible.service.validateWorkflowTransitionArtifacts(payload(incompatible)),
    { code: 'workflow_artifact_location_invalid' });
  assert.equal((await incompatible.service.getForConversation(incompatible.conversation)).currentNode, 'scan_sources');
  for (const node of nodes.values()) assert.match(node.prompt, /artifactLocationContext.projectRoot/);
  evidence.strictArtifactValidation = { explicitPointer: 'accepted', incompatibleHostRoot: 'rejected before advance' };
});

test('actual artifact duties accept distinct explicit instance paths despite unchanged Skill defaults', () => {
  for (const node of nodes.values()) {
    assert.match(node.prompt, /workflowCompletion/);
    assert.match(node.prompt, /location/);
    for (const exit of node.exits) {
      const duties = resolveArtifactDuties({ template, currentNodeId: node.id, exitId: exit.id, artifactContracts: contracts });
      for (const artifact of duties.artifacts) {
        const relative = `.build/operations/synthetic/handoffs/${node.id}/${exit.id}/${artifact.id}.md`;
        const target = path.join(fixture, relative);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.writeFileSync(target, '# Synthetic engine artifact pointer check\n');
        const check = validateArtifactLocation({ location: { kind: 'markdown_file', path: relative } }, { projectRoot: fixture });
        assert.equal(check.valid, true, JSON.stringify(check.errors));
        evidence.artifactLocations.push(relative);
      }
    }
  }
  assert.ok(evidence.artifactLocations.length > 0);
  assert.equal(new Set(evidence.artifactLocations).size, evidence.artifactLocations.length);
});
