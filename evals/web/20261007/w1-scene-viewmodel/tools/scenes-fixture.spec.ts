// W1 scenes check (record 최길웅-20261007-056). Copied into apps/web/e2e/__tmp only to run; not a product test.
// The labelled contract-fixture run has concepts but no recorded scenes, so the review panel must say 'not provided'.
// Env: SCENE_OUT (output folder). No server or model is needed.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

test('W1 scenes: labelled contract-fixture run shows "not provided", never drawn scenes', async ({ page }) => {
  const out = process.env.SCENE_OUT!;
  mkdirSync(out, { recursive: true });
  await page.goto('/');
  await page.getByRole('button', { name: '계약 fixture' }).click();
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '콘셉트 검토' }).click();
  const review = page.getByRole('region', { name: '후보 상세 검토' });
  await expect(review).toBeVisible();
  const seen = {
    fixture_banner: await page.locator('.fixture-banner, [data-fixture-banner]').allTextContents(),
    concept_cards: await page.locator('.concept-card').count(),
    not_provided: await review.locator('[data-scenes-not-provided]').allTextContents(),
    drawn_scenes: await review.locator('[data-concept-scenes]').count(),
  };
  await review.screenshot({ path: join(out, 'fixture-review-not-provided.png') });
  writeFileSync(join(out, 'fixture-observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
  expect(seen.not_provided).toHaveLength(1);
  expect(seen.drawn_scenes).toBe(0);
});
