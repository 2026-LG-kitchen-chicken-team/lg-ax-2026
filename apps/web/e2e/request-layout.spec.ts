import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

// Record 최길웅-20261007-046: PM's #188 browser check (1280px) showed the "원 요청" column squeezed to one character by
// a long trend ID in "변경", and the model checkbox stretched to full width so "FRIDGE-A · 가상 냉장고 A" wrapped.
// Fixture mode only; no workspace server or model. LGAX_E2E_LAYOUT_PROOF_DIR keeps a screenshot.
const proofDir = process.env.LGAX_E2E_LAYOUT_PROOF_DIR;
const HANDOFF = '청소 불편과 기존 기능을 대조하고 기회 후보를 검토\n[리뷰 동향 근거 · TREND-c3c9634d35bb92f63031b115ff335e5132f8d164d675546b03a852a8074aba62 · FRIDGE-A · 2026년 10월 · 청소 (cleaning) 1/3건(33.3%) · 작은 표본 · 근거 DEMO-TREND-REVIEW-EVIDENCE-001 · 리뷰 수는 판매량·수요 증가를 뜻하지 않음]';

test('request form at 1280px: a long hand-off ID does not squeeze the original column; model labels stay on one line', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto('/');
  await page.getByRole('button', { name: '계약 fixture' }).click();
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '기획 요청' }).click();
  await page.locator('#planning-prompt').fill(HANDOFF);
  const table = page.locator('[aria-label="변경 요청"] .change-table');
  await expect(table).toBeVisible();
  const widths = await table.locator('tbody tr').first().locator('> *').evaluateAll(cells => cells.map(cell => cell.getBoundingClientRect().width));
  expect(widths).toHaveLength(3);
  expect(widths[1], 'original request column').toBeGreaterThanOrEqual(100);
  expect(Math.abs(widths[1] - widths[2]), 'original and changed columns share the width').toBeLessThanOrEqual(2);
  for (const label of await page.locator('.model-picker label').all()) {
    const box = (await label.boundingBox())!;
    expect(box.height, 'model label on one line').toBeLessThan(40);
    expect((await label.locator('input').boundingBox())!.width, 'checkbox keeps its own size').toBeLessThan(24);
  }
  if (proofDir) { mkdirSync(proofDir, { recursive: true }); await page.locator('.request-form').first().screenshot({ path: join(proofDir, 'request-layout-1280.png') }); }
});
