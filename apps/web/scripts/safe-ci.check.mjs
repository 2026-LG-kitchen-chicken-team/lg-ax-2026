import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { listening, main } from './safe-ci.mjs';

function socketFactory(event, code) {
  return () => {
    const socket = new EventEmitter();
    socket.destroy = () => {};
    socket.setTimeout = (_ms, callback) => { if (event === 'timeout') queueMicrotask(callback); };
    if (event !== 'timeout') queueMicrotask(() => socket.emit(event, Object.assign(new Error('probe'), { code })));
    return socket;
  };
}

test('only a refused connection means free; a connected server is busy', async () => {
  assert.equal(await listening(5173, '127.0.0.1', 10, socketFactory('error', 'ECONNREFUSED')), false);
  assert.equal(await listening(5173, '127.0.0.1', 10, socketFactory('connect')), true);
});

test('permissions, network errors and timeout are unknown rather than free', async () => {
  for (const code of ['EACCES', 'EPERM', 'ETIMEDOUT']) {
    await assert.rejects(listening(5173, '127.0.0.1', 10, socketFactory('error', code)));
  }
  await assert.rejects(listening(5173, '127.0.0.1', 10, socketFactory('timeout')));
});

test('unknown observation and busy port never invoke installation', async () => {
  let installs = 0;
  const options = { ports: [5173], install: () => { installs++; return { status: 0 }; }, log: () => {} };
  assert.equal(await main({ ...options, probe: async () => { throw new Error('unknown'); } }), 2);
  assert.equal(await main({ ...options, probe: async () => true }), 2);
  assert.equal(installs, 0);
});

test('all observed ports free permits exactly one install and propagates its result', async () => {
  let installs = 0;
  assert.equal(await main({ ports: [5173, 5174], probe: async () => false,
    install: () => { installs++; return { status: 7 }; }, log: () => {} }), 7);
  assert.equal(installs, 1);
});
