import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

// Real-source research flow (#234 W1/W2, #26 web E2E; records 최길웅-20261007-057 … 20261008-061). A real workspace server
// started with `--research-bundle` for each file in LGAX_E2E_RESEARCH_BUNDLE_DIR sits behind LGAX_WORKSPACE_PROXY.
// Expectations are computed here from those same bundle files, not from web code. Opt-in: skipped unless
// LGAX_E2E_RESEARCH_TOKEN_FILE and LGAX_E2E_RESEARCH_BUNDLE_DIR are set. Run the test Vite on an origin the server allows
// for writes (LGAX_E2E_PORT=5175), never the user's 5173. No model is called; the planning-off check runs only when the
// server reports research planning disabled. Record 최길웅-20261008-068 added the selected-source planning request and the
// official-guide export checks for the R9 prototype (scripts/serve_research_prototype.py).
const tokenFile = process.env.LGAX_E2E_RESEARCH_TOKEN_FILE;
const bundleDir = process.env.LGAX_E2E_RESEARCH_BUNDLE_DIR;
const workspace = process.env.LGAX_WORKSPACE_PROXY;

interface Source {
  source_id: string; source_type: string; text: string; page_model: string | null; purchased_model: string | null;
  published_at: string | null; date_kind: string; document_version?: string | null; locator: Record<string, unknown>;
}
interface Bundle { bundle_id: string; sources: Source[] }

const bundles = (): Bundle[] => readdirSync(bundleDir!).filter(name => name.endsWith('.json')).sort()
  .map(name => JSON.parse(readFileSync(join(bundleDir!, name), 'utf8')) as Bundle);
const postingDay = (source: Source) => source.date_kind === 'posting' && source.published_at && /^\d{4}-\d{2}-\d{2}/.test(source.published_at);
const sourcesPanel = (page: Page) => page.getByRole('region', { name: '실제 자료 원문' });

async function connect(page: Page) {
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
}
async function choose(page: Page, bundle: Bundle) {
  await page.locator('#research-bundle').selectOption(bundle.bundle_id);
  await expect(sourcesPanel(page).locator('.research-source-row')).toHaveCount(bundle.sources.length);
}
async function openDetail(page: Page, sourceId: string) {
  await sourcesPanel(page).locator('.research-source-row').filter({ hasText: sourceId }).first().locator('.research-citations button').first().click();
  const detail = page.getByRole('article', { name: '인용 원문 상세' });
  await expect(detail.locator('h3')).toContainText(sourceId);
  return detail;
}

test.describe('real-source research flow', () => {
  test.skip(!tokenFile || !bundleDir, 'LGAX_E2E_RESEARCH_TOKEN_FILE / LGAX_E2E_RESEARCH_BUNDLE_DIR not set');
  test.setTimeout(4 * 60_000);

  test('every served bundle shows its own counts, unknowns and limits, without a blank page tail', async ({ page }) => {
    await connect(page);
    for (const bundle of bundles()) {
      await choose(page, bundle);
      const reviews = bundle.sources.filter(source => source.source_type === 'review');
      const confirmed = bundle.sources.filter(postingDay).length;
      await expect(page.locator('.research-setup .research-note').first()).toContainText(`실제 원문 ${bundle.sources.length}건 · 리뷰 ${reviews.length}건`);
      await expect(sourcesPanel(page).locator('.research-card-title span').first()).toHaveText(`${bundle.sources.length} / ${bundle.sources.length}건`);
      await expect(sourcesPanel(page).locator('select').nth(2).locator('option').nth(1)).toHaveText(`확인된 게시일만 · ${confirmed}건`);
      // A document-only bundle (e.g. the R9 manual reference, 0 reviews) has no review row to check.
      if (reviews.length) {
        const firstReview = sourcesPanel(page).locator('.research-source-row').filter({ hasText: reviews[0].source_id }).first();
        if (reviews[0].purchased_model === null) await expect(firstReview).toContainText('구매 모델 미확인');
        if (!postingDay(reviews[0])) await expect(firstReview).toContainText('게시일 미확인');
      }
      if (reviews.some(review => review.purchased_model === null)) {
        await expect(sourcesPanel(page).getByRole('region', { name: '자료의 핵심 한계' })).toContainText(`구매 모델이 미확인`);
      }
      // R8-F1: hidden screen-reader text inside the scrolling list must not stretch the page.
      const heights = await page.evaluate(() => ({ doc: document.documentElement.scrollHeight, body: document.body.scrollHeight }));
      expect(heights.doc - heights.body).toBeLessThanOrEqual(2);
    }
  });

  test('rows show readable positions and a review version reads as page-model reference material', async ({ page }) => {
    await connect(page);
    const bundle = bundles()[0];
    await choose(page, bundle);
    const rows = await sourcesPanel(page).locator('.research-source-row').evaluateAll(nodes => nodes.map(node =>
      [...node.querySelectorAll('p.research-muted')].map(p => p.textContent ?? '').join(' ')));
    expect(rows.every(text => text.includes(' · 위치 '))).toBe(true);
    for (const [index, source] of bundle.sources.entries()) {
      const keys = Object.keys(source.locator ?? {}).filter(key => key !== 'selector' && source.locator[key] !== null && source.locator[key] !== '');
      if (keys.length) expect(rows[index], source.source_id).not.toContain('위치 정보 없음');
    }
    const review = bundle.sources.find(source => source.source_type === 'review')!;
    let detail = await openDetail(page, review.source_id);
    await expect(detail.locator('[data-document-version]')).toHaveText(`페이지 모델의 연결 참고자료 버전: ${review.document_version ?? '미확인'}`);
    await expect(detail.locator('[data-document-version-note]')).toBeVisible();
    await detail.getByRole('button', { name: '상세 닫기' }).click();
    const other = bundle.sources.find(source => source.source_type !== 'review');
    if (other) {
      detail = await openDetail(page, other.source_id);
      await expect(detail.locator('[data-document-version]')).toHaveText(`문서판: ${other.document_version ?? '미확인'}`);
      await expect(detail.locator('[data-source-locator]')).not.toHaveText('원문 위치: 위치 정보 없음');
    }
  });

  test('keyboard users are taken into an opened source detail and back to the citation', async ({ page }) => {
    await connect(page);
    const bundle = bundles()[0];
    await choose(page, bundle);
    const cite = sourcesPanel(page).locator('.research-source-row').first().locator('.research-citations button').first();
    await cite.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('article', { name: '인용 원문 상세' }).locator('h3')).toBeFocused();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('article', { name: '인용 원문 상세' })).toHaveCount(0);
    await expect(cite).toBeFocused();
  });

  test('chosen sources are exported unchanged and marked as a selection, not a planning run', async ({ page }) => {
    await connect(page);
    const bundle = bundles()[0];
    await choose(page, bundle);
    const checks = sourcesPanel(page).locator('.research-source-check input');
    await checks.nth(0).check();
    await checks.nth(1).check();
    const [download] = await Promise.all([page.waitForEvent('download'), sourcesPanel(page).getByRole('button', { name: '선택 자료 JSON' }).click()]);
    const exported = JSON.parse(readFileSync((await download.path())!, 'utf8')) as Bundle & { collection_manifest: Record<string, any> };
    expect(exported.sources).toEqual(bundle.sources.slice(0, 2));
    expect(exported.collection_manifest.selection_only).toBe(true);
    expect(exported.collection_manifest.planning_executed).toBe(false);
  });

  test('with research planning off, a new plan request shows the server error and no result', async ({ page, request }) => {
    test.skip(!workspace, 'LGAX_WORKSPACE_PROXY not set');
    const health = await (await request.get(`${workspace}/health`)).json() as { research_planning_enabled?: boolean };
    test.skip(health.research_planning_enabled !== false, 'server has research planning enabled');
    await connect(page);
    await choose(page, bundles()[0]);
    const response = page.waitForResponse(item => item.url().endsWith('/api/research/planning-runs') && item.request().method() === 'POST');
    await page.getByRole('button', { name: '새 기획 생성', exact: true }).click();
    expect((await response).status()).toBe(501);
    await expect(page.locator('.research-error')).toContainText('요청을 완료하지 못했습니다');
    await expect(page.getByRole('region', { name: '실제 자료 기획 결과' })).toHaveCount(0);
  });

  test('a selected-source plan request sends only the chosen IDs, in bundle order, with the listed bundle hash', async ({ page, request }) => {
    test.skip(!workspace, 'LGAX_WORKSPACE_PROXY not set');
    const health = await (await request.get(`${workspace}/health`)).json() as { research_planning_enabled?: boolean };
    test.skip(health.research_planning_enabled !== false, 'server has research planning enabled');
    const listing = page.waitForResponse(item => item.url().endsWith('/api/research/bundles') && item.request().method() === 'GET');
    await connect(page);
    const listed = (await (await listing).json()) as { bundles: { bundle_id: string; bundle_sha256?: string }[] };
    const bundle = bundles().find(item => item.sources.filter(source => source.source_type === 'review').length >= 3)!;
    await choose(page, bundle);
    const checks = sourcesPanel(page).locator('.research-source-check input');
    // Check the third row before the first so the request must restore bundle order itself.
    await checks.nth(2).check();
    await checks.nth(0).check();
    const posted = page.waitForRequest(item => item.url().endsWith('/api/research/planning-runs') && item.method() === 'POST');
    await page.getByRole('button', { name: /^선택 근거로 새 기획 생성/ }).click();
    const body = (await posted).postDataJSON() as { bundle_id: string; selected_source_ids?: string[]; bundle_sha256?: string };
    expect(body.bundle_id).toBe(bundle.bundle_id);
    expect(body.selected_source_ids).toEqual([bundle.sources[0].source_id, bundle.sources[2].source_id]);
    expect(body.bundle_sha256).toBe(listed.bundles.find(item => item.bundle_id === bundle.bundle_id)?.bundle_sha256);
    await expect(page.locator('.research-error')).toContainText('요청을 완료하지 못했습니다');
    await expect(page.getByRole('region', { name: '실제 자료 기획 결과' })).toHaveCount(0);
  });

  test('the official-source guide exports only chosen official originals and refuses a review in the selection', async ({ page }) => {
    const official = bundles().find(item => item.sources.length && item.sources.every(source => source.source_type !== 'review' && source.source_type !== 'qa'));
    test.skip(!official, 'no document-only bundle in LGAX_E2E_RESEARCH_BUNDLE_DIR');
    await connect(page);
    await choose(page, official!);
    await sourcesPanel(page).getByRole('button', { name: '표시 자료 모두 선택' }).click();
    const [download] = await Promise.all([page.waitForEvent('download'), sourcesPanel(page).getByRole('button', { name: '선택 공식자료 안내서 Markdown' }).click()]);
    const markdown = readFileSync((await download.path())!, 'utf8');
    for (const source of official!.sources) expect(markdown, source.source_id).toContain(source.text.trim().split(/\r?\n/)[0].slice(0, 20));
    const mixed = bundles().find(item => item.sources.some(source => source.source_type === 'review') && item.sources.some(source => ['manual', 'faq', 'installation', 'spec'].includes(source.source_type)));
    if (!mixed) return;
    await choose(page, mixed);
    const review = mixed.sources.findIndex(source => source.source_type === 'review');
    const document = mixed.sources.findIndex(source => source.source_type !== 'review' && source.source_type !== 'qa');
    const checks = sourcesPanel(page).locator('.research-source-check input');
    await checks.nth(review).check();
    await checks.nth(document).check();
    let guideRequests = 0;
    page.on('request', item => { if (item.url().endsWith('/api/research/guides')) guideRequests += 1; });
    await sourcesPanel(page).getByRole('button', { name: '선택 공식자료 안내서 Markdown' }).click();
    await expect(sourcesPanel(page).getByRole('alert')).toBeVisible();
    expect(guideRequests).toBe(0);
  });
});
