// @vitest-environment jsdom
// Input is emitted by test_public_validation_projection after real HTTP POST/GET/history + stdio MCP.
import { readFileSync } from 'node:fs';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { ExecutionPanel } from './JudgementViews';
import { exportJudgement, planningExecutionView, reasonText } from './judgement';
import { buildExport, exportMarkdown } from './planning';
import type { RunSnapshot } from './planning';

const proof = process.env.LGAX_PUBLIC_VALIDATION_PROOF_FILE;
test.skipIf(!proof)('public HTTP/MCP validation facts reach the actual web panel and both exports', async () => {
  const receipt = JSON.parse(readFileSync(proof!, 'utf8'));
  expect([receipt.http_post_get_history_same, receipt.normal_hold_readback_same, receipt.stdio_mcp_same, receipt.model_calls]).toEqual([true, true, true, 0]);
  const snapshot = receipt.snapshot as RunSnapshot;
  const view = planningExecutionView(snapshot);
  expect(view.kind).toBe('ok');
  if (view.kind !== 'ok') throw new Error('Public execution record invalid');
  const source = view.execution.errors[0];
  const details = source.details as { violations: { evidence_id: string }[] };
  const evidenceId = details.violations[0].evidence_id;
  const judgement = exportJudgement(snapshot);
  expect(judgement?.record_valid).toBe(true);
  if (!judgement?.record_valid) throw new Error('Public export record invalid');
  expect(judgement.errors[0].details[0]).toEqual({ code: 'UNCERTAINTY_CONTEXT_MISSING', evidence_id: evidenceId, path: 'uncertainty_assessments/0/questions' });
  expect(judgement.errors[0].notes).toContain('서로 다른 두 선언: review_assessments ↔ result/review_assessments');
  const markdown = exportMarkdown(buildExport('live', snapshot, [], [], '2026-10-07T00:00:00Z', [snapshot]));
  expect(markdown).toContain(reasonText('UNCERTAINTY_CONTEXT_MISSING'));
  expect(markdown).toContain(`리뷰 ${evidenceId}`);
  expect(markdown).toContain('uncertainty_assessments/0/questions');
  expect(markdown).not.toContain('private-fixture-diagnostic-value');
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  try {
    await act(async () => root.render(createElement(ExecutionPanel, { snapshot })));
    expect(host.textContent).toContain(reasonText('UNCERTAINTY_CONTEXT_MISSING'));
    expect(host.textContent).toContain(evidenceId);
    expect(host.textContent).toContain('서로 다른 두 선언');
    expect(host.textContent).not.toContain('private-fixture-diagnostic-value');
  } finally {
    await act(async () => root.unmount()); host.remove();
  }
});
