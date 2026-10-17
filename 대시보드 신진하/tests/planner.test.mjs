import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { Planner, KEY } from '../src/planner.js';
import { NODE_DEFS } from '../src/engine.js';
import { SAMPLE_MODELS, SAMPLE_REVIEWS } from '../src/sample-data.js';

const storage = new Map();
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key),
} });
if (!globalThis.crypto?.randomUUID) Object.defineProperty(globalThis, 'crypto', { configurable: true, value: webcrypto });
globalThis.requestAnimationFrame = callback => setImmediate(() => callback(performance.now()));
const tick = () => new Promise(resolve => setImmediate(resolve));
beforeEach(() => storage.clear());

async function until(predicate, description = 'condition') {
  const deadline = Date.now() + 3000;
  while (!predicate()) {
    if (Date.now() > deadline) throw Error(`Timed out waiting for ${description}`);
    await tick();
  }
}

async function completeWithAnswers(planner, promise, answer = 'hold') {
  let finished = false;
  promise.finally(() => { finished = true; });
  let answered = 0;
  await until(() => {
    if (planner.state.status === 'awaiting') { planner.answer(answer); answered++; }
    return finished;
  }, 'run completion');
  await promise;
  return answered;
}

function compact() {
  const planner = new Planner();
  planner.changeData([SAMPLE_REVIEWS[0]], [SAMPLE_MODELS[0]]);
  return planner;
}

test('complete run waits for each clarification and records both include and hold choices', async () => {
  const planner = new Planner();
  const run = planner.start();
  const questions = [];
  await until(() => planner.state.status === 'awaiting', 'first clarification');
  assert.equal(planner.state.active, 'compare');
  assert.equal(planner.state.results.compare, undefined);
  assert.equal(planner.state.steps.compare.status, 'awaiting');
  const first = planner.state.question;
  questions.push(first.id);
  planner.answer('unexpected');
  assert.equal(planner.state.question.id, first.id);
  assert.equal(planner.state.status, 'awaiting');
  planner.answer('include');
  let finished = false;
  run.finally(() => { finished = true; });
  await until(() => {
    if (planner.state.status === 'awaiting') { questions.push(planner.state.question.id); planner.answer('hold'); }
    return finished;
  }, 'all clarification answers');
  await run;
  assert.equal(planner.state.status, 'completed');
  assert.ok(questions.length >= 2, 'sample exercises multiple clarification questions');
  assert.equal(new Set(questions).size, questions.length);
  assert.equal(planner.state.decisions[questions[0]], 'include');
  assert.ok(questions.slice(1).every(id => planner.state.decisions[id] === 'hold'));
  assert.equal(planner.state.results.compare.comparisons.find(row => row.needId === first.needId).classification, 'assumption');
  assert.ok(NODE_DEFS.every(node => planner.state.steps[node.id].status === 'completed'));
});

test('pause holds at work boundary then resume finishes same run', async () => {
  const planner = compact();
  const run = planner.start();
  await until(() => planner.state.active === 'retrieve' && planner.state.steps.retrieve.status === 'running');
  const runId = planner.state.runId;
  planner.pause();
  await tick(); await tick(); await tick();
  assert.equal(planner.state.status, 'paused');
  assert.equal(planner.state.results.retrieve, undefined);
  planner.resume();
  await run;
  assert.equal(planner.state.status, 'completed');
  assert.equal(planner.state.runId, runId);
});

test('stop ignores a late async result and preserves only completed stages', async () => {
  const planner = compact();
  const original = planner.execute.bind(planner);
  let release;
  planner.execute = async id => {
    if (id !== 'structure') return original(id);
    return new Promise(resolve => { release = () => original(id).then(resolve); });
  };
  const run = planner.start();
  await until(() => Boolean(release), 'pending async stage');
  assert.ok(planner.state.results.retrieve);
  planner.stop();
  assert.equal(planner.state.status, 'stopped');
  release();
  await run;
  assert.ok(planner.state.results.retrieve);
  assert.equal(planner.state.results.structure, undefined);
  assert.equal(planner.state.steps.structure.status, 'stopped');
});

test('data mutation invalidates pending old output, all downstream results and prior decisions', async () => {
  const planner = compact();
  let release;
  planner.execute = () => new Promise(resolve => { release = resolve; });
  const run = planner.start();
  await until(() => Boolean(release));
  planner.state.decisions = { obsolete: 'include' };
  planner.changeData([{ ...SAMPLE_REVIEWS[0], id: 'NEW-R', text: '새로운 자료' }], SAMPLE_MODELS);
  release({ reviews: [SAMPLE_REVIEWS[0]], summary: 'late old result' });
  await run;
  assert.equal(planner.state.status, 'idle');
  assert.deepEqual(planner.state.results, {});
  assert.deepEqual(planner.state.decisions, {});
  assert.equal(planner.state.reviews[0].id, 'NEW-R');
  assert.ok(NODE_DEFS.every(node => planner.state.steps[node.id].status === 'idle'));
});

test('partial rerun reuses prior stages, immediately invalidates later stages and records old run', async () => {
  const planner = compact();
  await planner.start();
  const oldRetrieve = planner.state.results.retrieve;
  const oldStructure = planner.state.results.structure;
  const oldRunId = planner.state.runId;
  const run = planner.start('compare');
  assert.equal(planner.state.results.retrieve, oldRetrieve);
  assert.equal(planner.state.results.structure, oldStructure);
  assert.equal(planner.state.results.compare, undefined);
  assert.equal(planner.state.results.concept, undefined);
  assert.equal(planner.state.results.validate, undefined);
  await run;
  assert.equal(planner.state.status, 'completed');
  assert.notEqual(planner.state.runId, oldRunId);
  assert.equal(planner.state.history[0].runId, oldRunId);
  assert.ok(planner.state.history[0].results.concept);
});

test('partial rerun with missing prerequisite falls back to first missing stage', async () => {
  const planner = compact();
  const run = planner.start('concept');
  assert.equal(planner.state.active, 'retrieve');
  await run;
  assert.ok(planner.state.results.retrieve);
  assert.equal(planner.state.status, 'completed');
});

test('reload preserves completed results but restores interrupted Python run as stopped browser mode', async () => {
  const planner = compact();
  await planner.start();
  const saved = JSON.parse(storage.get(KEY));
  saved.status = 'awaiting';
  saved.active = 'compare';
  saved.steps.compare.status = 'awaiting';
  saved.mode = 'python'; saved.backend = 'http://127.0.0.1:8799';
  saved.question = { id: 'abandoned-question' };
  localStorage.setItem(KEY, JSON.stringify(saved));
  const restored = new Planner();
  assert.equal(restored.state.restored, true);
  assert.equal(restored.state.status, 'stopped');
  assert.equal(restored.state.steps.compare.status, 'stopped');
  assert.equal(restored.state.question, null);
  assert.equal(restored.state.backend, '');
  assert.equal(restored.state.mode, 'browser');
  assert.deepEqual(restored.state.results, saved.results);
});

test('automatic revisions preserve each round before/after snapshots and cap repairs at two', async () => {
  const planner = compact();
  const original = planner.execute.bind(planner);
  let validations = 0, concepts = 0;
  planner.execute = async id => {
    const result = await original(id);
    if (id === 'concept') return { ...result, testIteration: ++concepts };
    if (id === 'validate') return { ...result, needsRepair: ++validations < 3, repairTargets: ['concept'], issues: [{ message: `validation ${validations}` }] };
    return result;
  };
  await planner.start();
  assert.equal(planner.state.status, 'completed');
  assert.equal(validations, 3);
  assert.equal(planner.state.revisions.length, 2);
  const [first, second] = planner.state.revisions;
  assert.equal(first.before.concept.testIteration, 1);
  assert.equal(first.after.concept.testIteration, 2);
  assert.equal(second.before.concept.testIteration, 2);
  assert.equal(second.after.concept.testIteration, 3);
  assert.notDeepEqual(first.after, second.after);
});

test('unresolved third validation stops in review state; empty repair target falls back safely', async () => {
  const planner = compact();
  const original = planner.execute.bind(planner);
  let validations = 0;
  planner.execute = async id => {
    const result = await original(id);
    if (id === 'validate') { validations++; return { ...result, needsRepair: true, repairTargets: [], issues: [{ message: 'unresolved' }] }; }
    return result;
  };
  await planner.start();
  assert.equal(validations, 3);
  assert.equal(planner.state.status, 'review');
  assert.equal(planner.state.revisions.length, 2);
  assert.ok(planner.state.revisions.every(round => round.before && round.after));
});

test('stopping at clarification resolves waiting promise and cannot be resumed by obsolete answer', async () => {
  const planner = new Planner();
  const run = planner.start();
  await until(() => planner.state.status === 'awaiting');
  planner.stop();
  await run;
  planner.answer('include');
  assert.equal(planner.state.status, 'stopped');
  assert.equal(planner.state.question, null);
  assert.deepEqual(planner.state.decisions, {});
});

test('a failed execution clears prior error when starting successfully again', async () => {
  const planner = compact();
  const original = planner.execute.bind(planner);
  planner.execute = async () => { throw Error('test backend unavailable'); };
  await planner.start();
  assert.equal(planner.state.status, 'failed');
  assert.match(planner.state.error, /unavailable/);
  planner.execute = original;
  await planner.start();
  assert.equal(planner.state.status, 'completed');
  assert.equal(planner.state.error, null);
});

test('result persistence survives normal reload without restarting any work', async () => {
  const planner = compact();
  await planner.start();
  const restored = new Planner();
  assert.equal(restored.state.status, 'completed');
  assert.equal(restored.state.runId, planner.state.runId);
  assert.equal(restored.state.results.concept.concepts[0].id, planner.state.results.concept.concepts[0].id);
  assert.equal(restored.state.runCount, 1);
});
