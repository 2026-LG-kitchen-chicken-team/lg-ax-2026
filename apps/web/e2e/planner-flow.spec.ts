import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Download, Page } from '@playwright/test';

async function readDownload(download: Download): Promise<string> {
  const path = await download.path();
  return readFileSync(path, 'utf8');
}

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}

test('fixture: request questions → candidate review → corrected rerun → export and measured modification time', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '계약 fixture' }).click();
  await expect(page.getByRole('note').filter({ hasText: '모의 데이터 모드' })).toBeVisible();

  // R02: missing information is asked, not guessed, and nothing is sent.
  await openArea(page, '기획 요청');
  const customer = page.getByLabel('대상 고객');
  await customer.fill('');
  await expect(page.locator('.question-list')).toContainText('누구의 불편을 다루나요?');
  await page.getByRole('button', { name: '요청 규격 검사' }).click();
  await expect(page.locator('.request-form .inline-message')).toContainText('확인이 필요한 정보가 있습니다');
  await customer.fill('1인 가구');
  await page.getByRole('button', { name: '요청 규격 검사' }).click();
  await expect(page.locator('.request-form .inline-message')).toContainText('FIXTURE_ONLY');

  // R14/R21: compare candidates and read sources, judgments, assumptions and held items together.
  await openArea(page, '콘셉트 검토');
  await expect(page.locator('.candidate-matrix')).toContainText('CONCEPT-FX-002');
  await page.getByRole('button', { name: '원문·판단 함께 보기' }).nth(1).click();
  const review = page.getByRole('region', { name: '후보 상세 검토' });
  await expect(review).toContainText('청소 전 식품 이동 범위 안내');
  // The separate trace panel also quotes evidence; assert the candidate's own source list.
  await expect(review.getByRole('list', { name: '후보 인용 원문' })).toContainText('선반 분리 방법이 설명서 어디 있는지 모르겠어요.');
  await expect(review.locator('.held-list')).toContainText('GAP-FX-002');

  // R27: the export carries every cited source and its own completeness check.
  await expect(page.locator('.export-check').first()).toHaveText('내보내기 점검: 누락 없음');
  const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: 'JSON' }).click()]);
  expect(jsonDownload.suggestedFilename()).toBe('RUN-FX-002-fixture.json');
  const exported = JSON.parse(await readDownload(jsonDownload));
  expect(exported.meta.mode).toBe('fixture');
  expect(exported.completeness.complete).toBe(true);
  expect(exported.lineage.map((item: { run_id: string }) => item.run_id)).toEqual(['RUN-FX-001', 'RUN-FX-002']);
  expect(exported.held[0].id).toBe('GAP-FX-002');

  // E03 + R21: measure a defined modification goal from start until the rerun is saved.
  await openArea(page, '수정 이력');
  await page.locator('.timeline').getByRole('button', { name: /RUN-FX-002/ }).click();
  await page.getByLabel('수정 목표').fill('트레이 후보 제외하고 1인 가구 조건 추가');
  await page.getByRole('button', { name: '수정 시간 측정 시작' }).click();
  await expect(page.locator('.measure-bar.running')).toContainText('수정 시간 측정 중');
  const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
  await rerun.getByRole('radiogroup', { name: '오염 구획만 꺼내는 분리 청소 트레이 처리' }).getByText('제외').click();
  await rerun.getByLabel('추가 조건').fill('1인 가구 소형 모델만');
  await rerun.getByRole('button', { name: '조건 추가' }).click();
  await expect(rerun.locator('.change-table')).toContainText('후보 제외: 오염 구획만 꺼내는 분리 청소 트레이 (CONCEPT-FX-001)');
  await expect(rerun.getByText('요청 회차 2')).toBeVisible();
  await rerun.getByRole('button', { name: '새 실행 초안' }).click();

  await expect(page.locator('.timeline')).toContainText('RUN-DRAFT-3');
  await expect(page.locator('.planning-stack h3').first()).toHaveText('RUN-DRAFT-3 변경 전후');
  await expect(page.locator('.measurement-log li').first()).toContainText('초');
  await expect(page.locator('.measurement-log li').first()).toContainText('후보 1 · 조건 +1/−0');

  const [measureDownload] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: '수정 시간 기록 내보내기(JSON)' }).click()]);
  const measured = JSON.parse(await readDownload(measureDownload));
  expect(measured.rules.unmeasured).toBe('null');
  expect(measured.records).toHaveLength(1);
  expect(measured.records[0]).toMatchObject({ status: 'completed', base_run_id: 'RUN-FX-002', result_run_id: 'RUN-DRAFT-3', goal: '트레이 후보 제외하고 1인 가구 조건 추가' });
  expect(typeof measured.records[0].modification_seconds).toBe('number');
  expect(measured.records[0].modification_seconds).toBeGreaterThanOrEqual(0);

  // The new draft has no Agent output; its export says so instead of inventing results.
  const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: '문서(Markdown)' }).click()]);
  const markdown = await readDownload(mdDownload);
  expect(markdown).toContain('생성된 콘셉트가 없습니다.');
  expect(markdown).toContain('not_implemented');
  expect(markdown).toContain('RUN-FX-002 · 요청 회차 1');
});

test('fixture: a cancelled measurement stays unmeasured (null)', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '계약 fixture' }).click();
  await openArea(page, '수정 이력');
  await page.getByRole('button', { name: '수정 시간 측정 시작' }).click();
  await expect(page.locator('.measure-bar [role=alert]')).toContainText('수정 목표');
  await page.getByLabel('수정 목표').fill('조건만 교정');
  await page.getByRole('button', { name: '수정 시간 측정 시작' }).click();
  await page.getByRole('button', { name: '측정 취소' }).click();
  await expect(page.locator('.measurement-log li').first()).toContainText('미측정(취소)');
});

// Opt-in: start the APIs (18867, 18869) and set LGAX_E2E_TOKEN_FILE to an editor credential file from scripts/init_workspace.py.
const tokenFile = process.env.LGAX_E2E_TOKEN_FILE;
test('live: connect, save a request, rerun with a corrected condition on the real server', async ({ page }) => {
  test.skip(!tokenFile, 'LGAX_E2E_TOKEN_FILE not set; live workspace flow is opt-in');
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  await page.goto('/');
  await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);

  await openArea(page, '기획 요청');
  await page.getByRole('checkbox', { name: /FRIDGE-C/ }).check();
  await page.getByLabel('사용 상황').fill(`E2E ${Date.now()} 우유를 흘린 구역만 청소`);
  // Review fix #7: a save that starts a new project is shown as revision 0, matching what the server stores.
  if (await page.getByRole('button', { name: '새 프로젝트로 저장' }).isVisible()) {
    await expect(page.locator('.request-insights')).toContainText('요청 회차 0');
  }
  await page.getByRole('button', { name: /새 프로젝트로 저장|변경 요청 저장/ }).click();
  await expect(page.locator('.request-form .inline-message')).toContainText('요청 저장 완료 · 분석 결과 아님');

  await openArea(page, '수정 이력');
  const before = await page.locator('.timeline > li').count();
  const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
  await rerun.getByLabel('추가 조건').fill(`E2E 조건 ${Date.now()}`);
  await rerun.getByRole('button', { name: '조건 추가' }).click();
  await rerun.getByRole('button', { name: '다시 실행 요청' }).click();
  await expect(page.locator('.timeline > li')).toHaveCount(before + 1);
  await expect(page.locator('.timeline > li').last()).toContainText('요청만 저장됨');
});
