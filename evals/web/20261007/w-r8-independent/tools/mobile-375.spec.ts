// R8 independent check diagnostics (record 최길웅-20261007-057). Copied into apps/web/e2e/__tmp only to run; not a product test. Env: OUT, R8_TOKEN_FILE.
import { readFileSync, writeFileSync } from 'node:fs';
import { test } from '@playwright/test';
test.use({ viewport: { width: 375, height: 812 } });
test('mobile width', async ({ page }) => {
  const token = (JSON.parse(readFileSync(process.env.R8_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await page.getByText('실제 자료 작업실 연결됨').waitFor();
  await page.locator('#research-bundle').selectOption({ index: 2 });
  await page.getByRole('region', { name: '실제 자료 원문' }).waitFor();
  const m = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth,
    wide: [...document.querySelectorAll('main *')].filter(el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !el.closest('.research-source-list') && getComputedStyle(el).position !== 'absolute').slice(0, 5).map(el => `${el.tagName.toLowerCase()}.${(el.className || '').toString().slice(0, 40)} r=${Math.round(el.getBoundingClientRect().right)}`) }));
  await page.screenshot({ path: process.env.OUT!.replace('.json', '.png') });
  writeFileSync(process.env.OUT!, JSON.stringify(m, null, 1));
});
