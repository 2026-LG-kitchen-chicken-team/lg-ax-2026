// Text colour contrast on the real-source research screen (record 최길웅-20261008-062). Copied into apps/web/e2e/__tmp only
// to run; not a product test. Real workspace server, three committed R8 bundles, planning OFF. For every visible element
// that owns text, the computed text colour is compared with the first opaque background behind it (WCAG 2.x formula):
// AA needs 4.5:1, or 3:1 for large text (>=24px, or >=18.66px and bold). Env: CON_OUT, CON_TOKEN_FILE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const measure = (page: Page) => page.evaluate(() => {
  const parse = (value: string) => { const m = value.match(/rgba?\(([^)]+)\)/); if (!m) return null; const [r, g, b, a = '1'] = m[1].split(/[ ,/]+/).filter(Boolean); return [Number(r), Number(g), Number(b), Number(a)]; };
  const lum = ([r, g, b]: number[]) => { const c = [r, g, b].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const background = (el: Element | null): number[] => {
    for (let node = el; node; node = node.parentElement) { const bg = parse(getComputedStyle(node).backgroundColor); if (bg && bg[3] >= 0.99) return bg; }
    return [255, 255, 255, 1];
  };
  const rows: { text: string; cls: string; ratio: number; need: number; color: string; bg: string; size: number }[] = [];
  for (const el of document.querySelectorAll<HTMLElement>('main *')) {
    const own = [...el.childNodes].filter(node => node.nodeType === 3).map(node => node.textContent ?? '').join('').trim();
    if (!own) continue;
    const style = getComputedStyle(el); const box = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none' || box.width < 2 || box.height < 2 || el.closest('.sr-only')) continue;
    const fg = parse(style.color); if (!fg) continue;
    const bg = background(el);
    const mixed = fg[3] < 1 ? fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3])) : fg;
    const [hi, lo] = [lum(mixed), lum(bg)].sort((a, b) => b - a);
    const size = parseFloat(style.fontSize); const bold = Number(style.fontWeight) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    rows.push({ text: own.slice(0, 50), cls: `${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]}`, ratio: Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100, need, color: style.color, bg: `rgb(${bg.slice(0, 3).join(',')})`, size });
  }
  return rows;
});

test('research screen text contrast against WCAG AA', async ({ page }) => {
  test.setTimeout(180_000);
  const token = (JSON.parse(readFileSync(process.env.CON_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = process.env.CON_OUT!; mkdirSync(out, { recursive: true });
  await page.goto('/');
  const before = await measure(page);
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
  await page.locator('#research-bundle').selectOption({ index: 2 });
  const panel = page.getByRole('region', { name: '실제 자료 원문' });
  await expect(panel).toBeVisible();
  await panel.locator('.research-source-row').first().getByRole('button').first().click();
  await expect(page.getByRole('article', { name: '인용 원문 상세' })).toBeVisible();
  const after = await measure(page);
  const all = [...before, ...after];
  const failing = all.filter(row => row.ratio < row.need);
  const groups = Object.values(failing.reduce((acc: Record<string, { cls: string; color: string; bg: string; ratio: number; need: number; size: number; count: number; example: string }>, row) => {
    const key = `${row.cls}|${row.color}|${row.bg}`;
    acc[key] ??= { cls: row.cls, color: row.color, bg: row.bg, ratio: row.ratio, need: row.need, size: row.size, count: 0, example: row.text };
    acc[key].count++; return acc;
  }, {})).sort((a, b) => a.ratio - b.ratio);
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify({ measured: all.length, failing: failing.length, groups }, null, 1)}\n`);
});
