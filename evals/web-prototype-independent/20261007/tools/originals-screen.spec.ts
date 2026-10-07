// R5 independent web check (record 최길웅-20261007-051). Copied into apps/web/e2e/__tmp only to run; not a product test.
// Reads the three PM original 122B runs that serve_originals.py stored over real HTTP (one test server per case) and
// compares the screen and the JSON/Markdown exports with expected-originals.json (computed without web code).
// Env: R5_CASE (fridge-normal|fridge-changed|fridge-missing-manual), R5_DIR (evals folder), R5_TOKEN_FILE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Download } from '@playwright/test';

const name = process.env.R5_CASE!;
const dir = process.env.R5_DIR!;
const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const text = async (download: Download) => readFileSync(await download.path(), 'utf8');

test(`R5 original ${name}: screen and exports match the independent expectations`, async ({ page }) => {
  const want = read(join(dir, 'expected-originals.json')).cases[name];
  const ids = read(join(dir, 'http-replay/http-replay.json')).cases[name];
  const token = read(process.env.R5_TOKEN_FILE!).token as string;
  const seen: Record<string, unknown> = { case: name, run_id: ids.run_id };
  await page.goto('/');
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  await page.getByRole('combobox', { name: '프로젝트' }).selectOption(ids.project_id);
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '콘셉트 검토' }).click();
  const record = page.getByRole('region', { name: '판단 실행 기록' });
  await expect(record).toContainText(ids.run_id);
  const field = async (key: string) => (await record.locator(`[data-field="${key}"]`).first().textContent()) ?? '';
  seen.head = await record.locator('.planning-head .run-status').first().textContent();
  seen.head_class = await record.locator('.planning-head .run-status').first().getAttribute('class');
  seen.model_calls = await field('model-calls');
  seen.tokens = await field('tokens');
  seen.rounds_line = await field('rounds');
  seen.check_rounds = await record.locator('.check-rounds [data-round]').allTextContents();
  seen.scope = await record.getByRole('region', { name: '검증 범위' }).allTextContents();
  seen.errors = await record.locator('.unresolved li').allTextContents();
  seen.rejected = await record.locator('[data-rejected-concept]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-rejected-concept')));
  const body = (await page.locator('main').textContent()) ?? '';
  seen.accepted_claim = body.includes('계약 검사 통과 · 의미') && want.decision_action !== 'accept';
  seen.concept_cards = await page.locator('.concept-card').count();
  const checks: Record<string, boolean> = {
    head_not_success: !String(seen.head_class).includes('done'),
    head_status: want.status === 'held' ? String(seen.head).includes('보류') : String(seen.head).includes('실패'),
    calls: String(seen.model_calls).startsWith(`${want.model_calls}회`),
    tokens: String(seen.tokens) === `입력 ${want.prompt_tokens.toLocaleString('en-US')} · 출력 ${want.output_tokens.toLocaleString('en-US')} · 합 ${(want.prompt_tokens + want.output_tokens).toLocaleString('en-US')}`,
    internal_revisions: String(seen.rounds_line).includes(`Agent 내부 수정 ${want.revision_count}/${want.max_revisions}`),
    check_rounds: (seen.check_rounds as string[]).length === want.check_rounds.length,
    rejected: JSON.stringify(seen.rejected) === JSON.stringify(want.rejected_concepts),
    no_success_claim: !seen.accepted_claim && seen.concept_cards === 0,
    synthetic_shown: body.includes('합성자료'),
    lists_shown: [...want.questions, ...want.hold_reasons, ...want.unresolved].every((item: string) => body.includes(item.slice(0, 20))),
  };
  const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: 'JSON' }).click()]);
  const exported = JSON.parse(await text(jsonDownload));
  const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: '문서(Markdown)' }).click()]);
  const markdown = await text(mdDownload);
  const judgement = exported.judgement ?? {};
  checks.export_status = judgement.status === want.status && exported.meta?.run_id === ids.run_id;
  checks.export_tokens = judgement.metrics?.prompt_tokens === want.prompt_tokens && judgement.metrics?.output_tokens === want.output_tokens;
  checks.export_errors = JSON.stringify((judgement.errors ?? []).map((item: { code: string }) => item.code)) === JSON.stringify(want.errors.map((item: { code: string }) => item.code));
  checks.markdown_tokens = markdown.includes(`입력 ${want.prompt_tokens.toLocaleString('en-US')} · 출력 ${want.output_tokens.toLocaleString('en-US')}`);
  checks.markdown_internal = markdown.includes(`Agent 내부 수정: ${want.revision_count}/${want.max_revisions}회`);
  seen.checks = checks;
  const out = join(dir, 'web');
  mkdirSync(out, { recursive: true });
  await record.screenshot({ path: join(out, `${name}.record.png`) });
  writeFileSync(join(out, `${name}.observed.json`), `${JSON.stringify(seen, null, 1)}\n`);
  writeFileSync(join(out, `${name}.export.md`), markdown);
  expect(Object.entries(checks).filter(([, ok]) => !ok).map(([key]) => key)).toEqual([]);
});
