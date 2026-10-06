import { describe, expect, it, vi } from 'vitest';
import fixture from '../../../packages/contracts/fixtures/review-trends.v1.json';
import { WorkspaceClient, type ReviewTrendFilters } from './workspace';

// Contract/transport fixtures are not a working DATA collector or a real chart.
const filters = fixture.templates.request as ReviewTrendFilters;
const aggregate = fixture.templates.aggregate;
const token = 't'.repeat(48);

describe('private trend workspace client', () => {
  it('encodes repeat source/topic keys and uses the common authenticated read boundary', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true, data: { aggregate, contract_version: '0.1.0' },
    })));
    const result = await new WorkspaceClient('', () => token, transport).reviewTrends(filters);
    expect(result.aggregate.aggregate_id).toBe(aggregate.aggregate_id);
    const [url, options] = transport.mock.calls[0];
    const query = new URL(String(url), 'http://localhost').searchParams;
    expect(query.getAll('source_ids')).toEqual(filters.source_ids);
    expect(query.getAll('topic_ids')).toEqual(filters.topic_ids);
    expect(options).toMatchObject({ method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store' });
    expect(options.headers.Authorization).toBe(`Bearer ${token}`);
    expect(options.body).toBeUndefined();
  });

  it('preserves NOT_IMPLEMENTED and never substitutes fixture counts for a missing collector', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false, error: { code: 'NOT_IMPLEMENTED', message: '자료 집계기 미연결', details: {} },
    }), { status: 501 }));
    await expect(new WorkspaceClient('', () => token, transport).reviewTrends(filters))
      .rejects.toMatchObject({ code: 'NOT_IMPLEMENTED' });
  });

  it('rejects impossible dates before sending source filters or credentials', () => {
    const transport = vi.fn();
    expect(() => new WorkspaceClient('', () => token, transport)
      .reviewTrends({ ...filters, start_date: '2026-02-30' })).toThrow();
    expect(transport).not.toHaveBeenCalled();
  });

  it('loads an exact saved aggregate without recomputing a model result', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true, data: { aggregate, contract_version: '0.1.0' },
    })));
    await new WorkspaceClient('', () => token, transport).getReviewTrends(filters.project_id, aggregate.aggregate_id);
    expect(String(transport.mock.calls[0][0]).endsWith(`/review-trends/${aggregate.aggregate_id}`)).toBe(true);
    expect(transport.mock.calls[0][1].method).toBe('GET');
  });

  it('validates paging and identifiers before transport', () => {
    const transport = vi.fn();
    const client = new WorkspaceClient('', () => token, transport);
    expect(() => client.trendEvidence(filters.project_id, aggregate.aggregate_id, '2026-12', 'cleaning', 0, 51))
      .toThrow();
    expect(() => client.getReviewTrends('../other', aggregate.aggregate_id)).toThrow();
    expect(transport).not.toHaveBeenCalled();
  });
});
