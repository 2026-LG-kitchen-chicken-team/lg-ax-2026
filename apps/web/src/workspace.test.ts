import { describe, expect, it, vi } from 'vitest';
import { readFileSync, writeFileSync } from 'node:fs';
import { WorkspaceClient } from './workspace';

const token = 't'.repeat(48);
const request = { product_group: 'fridge', target_customer: '1인 가구', use_situation: '음료를 쏟은 뒤 청소',
  improvement_task: '선반 청소 부담 감소', exclusions: [], model_ids: ['FRIDGE-A'], dataset_version: '0.1.0' };

describe('shared workspace client boundaries', () => {
  it('rejects missing credentials before HTTP and does not store credentials in state', async () => {
    const network = vi.fn();
    const client = new WorkspaceClient('', () => '', network);
    await expect(client.listProjects()).rejects.toMatchObject({ code: 'UNAUTHORIZED' });
    expect(network).not.toHaveBeenCalled();
  });
  it('does not send credentials to remote origins or credential-bearing URLs', () => {
    for (const url of ['https://foreign.example', 'http://user:pass@127.0.0.1:18869', 'http://127.0.0.1:18869/other']) {
      expect(() => new WorkspaceClient(url, () => token)).toThrow();
    }
  });
  it('validates project input and path before sending any write', async () => {
    const network = vi.fn();
    const client = new WorkspaceClient('', () => token, network);
    expect(() => client.createProject('x', { wrong: 'x' }, { 'FRIDGE-A': '1.0' })).toThrow();
    expect(() => client.getRun('../projects')).toThrow();
    expect(network).not.toHaveBeenCalled();
  });
  it('preserves server authorization errors without credential leakage', async () => {
    const network = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: false, error: { code: 'FORBIDDEN', message: '읽기 권한', details: {} } }), { status: 403 }));
    const client = new WorkspaceClient('', () => token, network);
    await expect(client.listProjects()).rejects.toMatchObject({ code: 'FORBIDDEN', message: '읽기 권한' });
    const options = network.mock.calls[0][1];
    expect(options.credentials).toBe('omit');
    expect(options.redirect).toBe('error');
    expect(options.headers['X-LGAX-Client']).toBe('web');
  });
  it('rejects a successful HTTP response with the wrong shared contract', async () => {
    const network = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, data: { projects: 'bad' } })));
    await expect(new WorkspaceClient('', () => token, network).listProjects()).rejects.toMatchObject({ code: 'CONTRACT_MISMATCH' });
  });
  it('does not automatically retry failed writes', async () => {
    const network = vi.fn().mockRejectedValue(new Error('connection lost'));
    await expect(new WorkspaceClient('', () => token, network).createProject('청소', request, { 'FRIDGE-A': '1.0' })).rejects.toMatchObject({ code: 'CONNECTION_FAILED' });
    expect(network).toHaveBeenCalledTimes(1);
  });
});

describe.skipIf(!process.env.LGAX_WORKSPACE_CREDENTIAL_FILE || !process.env.LGAX_WORKSPACE_URL)('actual shared workspace HTTP (explicit opt-in)', () => {
  it('persists a web-created project/run for the MCP verification script', async () => {
    const credential = JSON.parse(readFileSync(process.env.LGAX_WORKSPACE_CREDENTIAL_FILE!, 'utf-8')) as { token: string };
    const client = new WorkspaceClient(process.env.LGAX_WORKSPACE_URL!, () => credential.token);
    const sourceRequests = JSON.parse(readFileSync(new URL('../../../data/demo/planning_requests.json', import.meta.url), 'utf-8'));
    const input = sourceRequests[0] as Record<string, unknown>;
    const selected = input.model_ids as string[];
    const project = await client.createProject('PM 웹·MCP 공통 실행 검증', input, Object.fromEntries(selected.map(id => [id, '1.0'])));
    const run = await client.createRun(project.project.id, input, null, ['트레이 수납 용량 확인 필요']);
    expect(run.client).toBe('web');
    expect(run.run.status).toBe('not_implemented');
    expect(run.run.concepts).toEqual([]);
    expect(await client.getRun(run.run.id)).toEqual(run);
    expect(await client.getProject(project.project.id)).toEqual(project);
    if (process.env.LGAX_WORKSPACE_PROOF_FILE) writeFileSync(process.env.LGAX_WORKSPACE_PROOF_FILE, JSON.stringify({ project, run, input }, null, 2) + '\n');
  });
});
