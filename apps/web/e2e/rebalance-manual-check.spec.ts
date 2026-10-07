import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

// WEB-REBALANCE-R2 (record 028): partial checks before a normal accept exists, against the real planning server
// (18879, fresh test DB) and the live runs the strict E2E stored there. Opt-in: needs LGAX_E2E_PLANNING_TOKEN_FILE.
// It reads stored runs and drives the screen; only the duplicate-click check starts one new (live) judgement.
// It asserts web behaviour only, never judgement quality.
const tokenFile = process.env.LGAX_E2E_PLANNING_TOKEN_FILE;
const proofDir = process.env.LGAX_E2E_PLANNING_PROOF_DIR;
const UNREGISTERED = '설명이 등록되지 않은 검사 코드';

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}

test('rebalance manual checks on stored live runs', async ({ page }) => {
  test.skip(!tokenFile, 'LGAX_E2E_PLANNING_TOKEN_FILE not set');
  test.setTimeout(20 * 60_000);
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  const auth = { authorization: `Bearer ${token}` };
  const checks: Record<string, unknown>[] = [];
  const posts: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/workspace/')) posts.push(new URL(request.url()).pathname); });
  const record = (flow: string, result: 'ok' | 'finding' | 'fail', observed: unknown) => checks.push({ flow, result, observed });

  const projects = ((await (await page.request.get('/api/workspace/projects', { headers: auth })).json()).data?.projects ?? []) as
    { project: { id: string; name: string; request: { model_ids: string[] } } }[];
  const byModel = (model: string) => projects.filter(item => item.project.request.model_ids.includes(model)).map(item => item.project);

  const connect = async () => {
    await page.goto('/');
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '근거 대조' }).click();
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    await page.getByLabel('작업실 토큰').fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');
  };
  const choose = async (projectId: string) => {
    await page.getByRole('combobox', { name: '프로젝트' }).selectOption(projectId);
    await expect(page.getByRole('combobox', { name: '프로젝트' })).toHaveValue(projectId);
  };
  const timelineRuns = async () => (await page.locator('.timeline > li').allTextContents()).map(text => text.match(/run-[0-9a-f]+/)?.[0]);

  try {
    await connect();
    record('connect', 'ok', { projects: projects.length });

    // 1. Stored hold/failed/unresolved runs: Korean reasons for the new core codes, no raw unregistered code.
    for (const model of ['DISHWASHER-A', 'MICROWAVE-A', 'FRIDGE-A']) {
      const project = byModel(model)[0];
      if (!project) { record(`stored runs ${model}`, 'fail', 'no project'); continue; }
      await choose(project.id);
      await openArea(page, '콘셉트 검토');
      const execution = page.getByRole('region', { name: '판단 실행 기록' });
      await expect(execution).toBeVisible();
      const text = (await execution.textContent()) ?? '';
      const codes = [...new Set(text.match(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g) ?? [])];
      record(`hold/failure display ${model}`, text.includes(UNREGISTERED) ? 'fail' : 'ok', {
        project: project.id, codes_on_screen: codes, unregistered_shown: text.includes(UNREGISTERED),
        excerpt: text.replace(/\s+/g, ' ').slice(0, 600),
        mentions_input_error: text.includes('작업실 입력 값을 확인해 주세요'),
      });
      if (proofDir) await page.screenshot({ path: join(proofDir, `review-${model}.png`), fullPage: true });
    }

    // 2. History: user change (request revision) vs Agent internal revisions, then refetch after reload.
    const dish = byModel('DISHWASHER-A')[0];
    await choose(dish.id);
    await openArea(page, '수정 이력');
    const before = await timelineRuns();
    const history = (await page.getByRole('region', { name: '수정 이력' }).textContent()) ?? '';
    record('revision separation DISHWASHER-A', 'ok', { timeline_runs: before, excerpt: history.replace(/\s+/g, ' ').slice(0, 700) });
    if (proofDir) await page.screenshot({ path: join(proofDir, 'history-DISHWASHER-A.png'), fullPage: true });

    // 3. Duplicate condition is refused locally with no new run request.
    const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
    const existing = await rerun.locator('.condition-list input').first().inputValue().catch(() => '');
    const postsBefore = posts.length;
    if (existing) {
      await rerun.getByLabel('추가 조건').fill(existing);
      await rerun.getByRole('button', { name: '조건 추가' }).click();
      const shown = (await rerun.textContent()) ?? '';
      const listed = await rerun.locator('.condition-list input').evaluateAll(nodes => nodes.map(node => (node as HTMLInputElement).value));
      record('duplicate condition', listed.filter(value => value === existing).length === 1 && posts.length === postsBefore ? 'ok' : 'fail', {
        condition: existing, occurrences_after: listed.filter(value => value === existing).length, new_posts: posts.length - postsBefore,
        message: shown.match(/(이미[^.。]*|중복[^.。]*)/)?.[0] ?? null,
      });
    } else record('duplicate condition', 'fail', 'no existing condition in the form');

    // 4. Evidence: per-candidate traces only exist when a run has candidates; a held/failed run shows the judged input
    // sources inside its execution record instead.
    await openArea(page, '콘셉트 검토');
    const traces = await page.getByRole('region', { name: '근거 추적' }).count();
    const execution = (await page.getByRole('region', { name: '판단 실행 기록' }).textContent()) ?? '';
    const inputSources = execution.match(/입력 원문·기능\s*([0-9]+)건\s*·\s*([0-9]+)개/);
    record('evidence on a run without candidates DISHWASHER-A', inputSources ? 'ok' : 'fail', {
      candidate_traces: traces, input_sources: inputSources ? Number(inputSources[1]) : null, input_features: inputSources ? Number(inputSources[2]) : null,
    });

    // 5. Reload, reconnect, same project: same runs in the same order.
    await connect();
    await choose(dish.id);
    await openArea(page, '수정 이력');
    const after = await timelineRuns();
    record('history refetch after reload', JSON.stringify(after) === JSON.stringify(before) ? 'ok' : 'fail', { before, after });

    // 5b. The first DISHWASHER-A run (no-candidate review codes from the new core) read through the run picker.
    await openArea(page, '콘셉트 검토');
    const firstRun = before[0]!;
    await page.getByRole('combobox', { name: '실행 기록' }).first().selectOption(firstRun);
    const firstText = ((await page.getByRole('region', { name: '판단 실행 기록' }).textContent()) ?? '').replace(/\s+/g, ' ');
    const labelled = ['NO_CANDIDATE_VIOLATION', 'NO_CANDIDATE_UNCERTAIN'].map(code => ({ code, on_screen: firstText.includes(code),
      label: firstText.match(new RegExp(`([^()]{0,60}) \(${code}\)`))?.[1]?.trim() ?? null }));
    record('no-candidate codes on the first run', firstText.includes(UNREGISTERED) ? 'fail' : 'ok', { run: firstRun, labelled, excerpt: firstText.slice(0, 900) });
    if (proofDir) await page.screenshot({ path: join(proofDir, 'review-DISHWASHER-A-first-run.png'), fullPage: true });
    // Skip only the save/live judgement; all stored-run checks still reach the final failure assertion.
    if (process.env.LGAX_MANUAL_SKIP_SAVE !== '1') {
      // 6. Triple click on save: one project + one run request (starts one live judgement for DISHWASHER-A).
      const card = page.getByRole('region', { name: '제품군 선택' }).getByRole('button', { name: /식기세척기/ });
      await card.click();
      await openArea(page, '기획 요청');
      await page.getByRole('checkbox', { name: /DISHWASHER-A/ }).check();
      await page.getByLabel('사용 상황').fill(`수동 점검 ${new Date().toISOString()} 큰 접시와 냄비를 함께 넣을 때 어디에 둘지 몰라 다시 꺼내 배치함`);
      const saveButton = page.getByRole('button', { name: /새 프로젝트로 저장|변경 요청 저장/ });
      const startPosts = posts.length;
      await saveButton.click({ clickCount: 3 });
      const message = page.locator('.request-form .inline-message');
      await expect(message).toContainText(/실행 run-[0-9a-f]+ · 요청 회차/, { timeout: 15 * 60_000 });
      const created = posts.slice(startPosts);
      const projectPosts = created.filter(path => /\/projects$/.test(path)).length;
      const runPosts = created.filter(path => /\/runs$/.test(path)).length;
      // A selected project turns the button into "변경 요청 저장" (one POST …/runs); a new project is one POST /projects.
      record('triple click save', created.length === 1 && projectPosts + runPosts === 1 ? 'ok' : 'fail', { posts: created, heading: await message.locator('strong').textContent(), message: (await message.textContent())?.replace(/\s+/g, ' ').slice(0, 300) });
    }
  } finally {
    if (proofDir) {
      mkdirSync(proofDir, { recursive: true });
      writeFileSync(join(proofDir, 'manual-checks.json'), `${JSON.stringify({ kind: 'rebalance_manual_checks', observed_at: new Date().toISOString(), checks }, null, 2)}\n`);
    }
  }
  expect(checks.filter(item => item.result === 'fail')).toEqual([]);
});
