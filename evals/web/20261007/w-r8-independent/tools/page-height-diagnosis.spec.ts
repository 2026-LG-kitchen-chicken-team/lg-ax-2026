// R8 independent check diagnostics (record 최길웅-20261007-057). Copied into apps/web/e2e/__tmp only to run; not a product test. Env: OUT, R8_TOKEN_FILE.
import { readFileSync, writeFileSync } from 'node:fs';
import { test } from '@playwright/test';
test('mid diagnosis', async ({ page }) => {
  const token = (JSON.parse(readFileSync(process.env.R8_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await page.getByText('실제 자료 작업실 연결됨').waitFor();
  await page.locator('#research-bundle').selectOption({ index: 1 });
  await page.getByRole('region', { name: '실제 자료 원문' }).waitFor();
  await page.evaluate(() => scrollTo(0, 8000));
  await page.waitForTimeout(500);
  const info = await page.evaluate(() => {
    const listEl = document.querySelector('.research-source-list');
    const outside = [...document.querySelectorAll('body *')].filter(el => !listEl?.contains(el)).map(el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { el: `${el.tagName.toLowerCase()}.${(el.className || '').toString().slice(0, 40)}#${el.id}`, bottom: Math.round(r.bottom + scrollY), h: Math.round(r.height), pos: cs.position, ov: cs.overflow }; }).sort((a, b) => b.bottom - a.bottom).slice(0, 6);
    const docH = document.documentElement.scrollHeight; const bodyH = document.body.scrollHeight;
    const rows = [...document.querySelectorAll('.research-source-row')];
    const mid = rows[Math.floor(rows.length / 2)] as HTMLElement;
    const s = getComputedStyle(mid); const r = mid.getBoundingClientRect();
    const at = document.elementFromPoint(700, 450) as HTMLElement | null;
    const chain: string[] = []; let el: HTMLElement | null = mid;
    while (el && chain.length < 12) { const cs = getComputedStyle(el); chain.push(`${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]} h=${Math.round(el.getBoundingClientRect().height)} ov=${cs.overflow} op=${cs.opacity} vis=${cs.visibility} cv=${(cs as any).contentVisibility} pos=${cs.position} disp=${cs.display}`); el = el.parentElement; }
    const absInside = [...(listEl?.querySelectorAll('*') ?? [])].filter(el => ['absolute', 'fixed'].includes(getComputedStyle(el).position)).slice(0, 5).map(el => ({ el: `${el.tagName.toLowerCase()}.${(el.className || '').toString()}`, bottom: Math.round(el.getBoundingClientRect().bottom + scrollY), html: el.outerHTML.slice(0, 160) }));
    const absCount = [...(listEl?.querySelectorAll('*') ?? [])].filter(el => ['absolute', 'fixed'].includes(getComputedStyle(el).position)).length;
    return { absCount, absInside, outside, docH, bodyH, rows: rows.length, scrollY, midRect: { top: Math.round(r.top), h: Math.round(r.height) }, midStyle: { color: s.color, opacity: s.opacity, visibility: s.visibility, cv: (s as any).contentVisibility, display: s.display }, elementAtCenter: at ? `${at.tagName.toLowerCase()}.${at.className}` : null, chain };
  });
  await page.addStyleTag({ content: '.research-source-list{position:relative}' });
  const fixedDocH = await page.evaluate(() => document.documentElement.scrollHeight);
  const fixedBodyH = await page.evaluate(() => document.body.scrollHeight);
  writeFileSync(process.env.OUT!, JSON.stringify({ ...info, with_position_relative: { docH: fixedDocH, bodyH: fixedBodyH } }, null, 1));
});
