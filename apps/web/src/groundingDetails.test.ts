// @vitest-environment jsdom
// Stored-output replay plus synthetic R5 diagnostics: no model, service deployment or actual public-ID approval.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { ExecutionPanel } from './JudgementViews';
import { errorNotes, exportJudgement, groundingDetails, planningExecutionView } from './judgement';
import { buildExport, exportMarkdown } from './planning';
import type { RunSnapshot } from './planning';

const violation = { code: 'CONCEPT_GROUNDING_MISSING', concept_id: 'CONCEPT-TEST-001', missing_links: [{ gap_id: 'GAP-TEST-001',
  need_id: 'NEED-TEST-001', required_evidence_ids: ['MANUAL-TEST-001', 'REVIEW-TEST-001'], missing_evidence_ids: ['REVIEW-TEST-001'] }] };
const error = { code: 'VALIDATION_FAILED', message: '계약 시험의 후보 근거 누락', details: { grounding_violations: [violation], private_text: 'not-for-render-test' } };

it('reads both fixed R5 containers, removes duplicates and keeps only ID fields', () => {
  expect(groundingDetails(error)).toEqual([{ concept_id: violation.concept_id, missing_links: violation.missing_links }]);
  expect(groundingDetails({ details: { violations: [violation], grounding_violations: [violation] } })).toHaveLength(1);
  expect(errorNotes(error)).toEqual(['후보 CONCEPT-TEST-001 · 대조 GAP-TEST-001 → 불편 NEED-TEST-001 · 필요한 인용 MANUAL-TEST-001, REVIEW-TEST-001 · 누락 인용 REVIEW-TEST-001']);
  const copy = groundingDetails(error);
  copy[0].missing_links[0].missing_evidence_ids.push('COPY-ONLY');
  expect(violation.missing_links[0].missing_evidence_ids).toEqual(['REVIEW-TEST-001']);
});

it('does not invent links from malformed, unrelated or private-path values', () => {
  for (const row of [null, { ...violation, code: 'OTHER_CHECK' }, { ...violation, concept_id: 'C:/private/path' },
    { ...violation, missing_links: [{ ...violation.missing_links[0], missing_evidence_ids: ['NOT-REQUIRED'] }] },
    { ...violation, missing_links: [{ ...violation.missing_links[0], required_evidence_ids: 'not-an-array' }] }]) {
    expect(groundingDetails({ details: { grounding_violations: [row] } })).toEqual([]);
  }
});

it('keeps authorized gap/need/source links when the API omits an unconfirmed candidate ID', () => {
  const projected = { code: violation.code, missing_links: violation.missing_links };
  expect(groundingDetails({ details: { grounding_violations: [projected] } })).toEqual([{ concept_id: null, missing_links: violation.missing_links }]);
  expect(errorNotes({ details: { grounding_violations: [projected] } })[0]).toContain('후보 ID 미공개');
  expect(errorNotes({ details: { grounding_violations: [projected] } })[0]).toContain('REVIEW-TEST-001');
});

it('displays the same stored missing IDs in the execution panel and JSON/Markdown without changing the run', async () => {
  const record = JSON.parse(readFileSync(resolve(process.cwd(), '../../evals/pm-review/20261005-round2/api-live/workspace-live.json'), 'utf8'));
  const snapshot = structuredClone(record.first) as RunSnapshot;
  const execution = planningExecutionView(snapshot);
  expect(execution.kind).toBe('ok');
  if (execution.kind !== 'ok') throw new Error('Replay record invalid');
  execution.execution.errors.push(error);
  const before = JSON.stringify(snapshot);
  const exported = exportJudgement(snapshot);
  expect(exported?.record_valid).toBe(true);
  if (!exported?.record_valid) throw new Error('Replay export invalid');
  expect(exported.errors.at(-1)?.notes).toEqual(errorNotes(error));
  const markdown = exportMarkdown(buildExport('live', snapshot, [], [], '2026-10-07T00:00:00Z', [snapshot]));
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  try {
    await act(async () => root.render(createElement(ExecutionPanel, { snapshot })));
    for (const id of ['CONCEPT-TEST-001', 'GAP-TEST-001', 'NEED-TEST-001', 'MANUAL-TEST-001', 'REVIEW-TEST-001']) {
      expect(host.textContent).toContain(id);
      expect(markdown).toContain(id);
    }
    expect(host.textContent).not.toContain('not-for-render-test');
    expect(markdown).not.toContain('not-for-render-test');
    expect(JSON.stringify(snapshot)).toBe(before);
    expect(snapshot.run.status).toBe('held');
  } finally { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); }
});
