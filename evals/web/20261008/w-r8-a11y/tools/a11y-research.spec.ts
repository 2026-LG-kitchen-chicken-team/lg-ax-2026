// Accessibility pass on the real-source research screen (record 최길웅-20261008-061). Copied into apps/web/e2e/__tmp only to
// run; not a product test. Real workspace server with the three committed R8 bundles (planning OFF). No axe-core is
// installed, so the page itself is measured: accessible names, duplicate ids, heading order, keyboard reach and focus ring.
// Env: A11Y_OUT, A11Y_TOKEN_FILE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const audit = (page: Page) => page.evaluate(() => {
  const text = (el: Element | null) => (el?.textContent ?? '').replace(/\s+/g, ' ').trim();
  const nameOf = (el: HTMLElement): string => {
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) return labelledby.split(/\s+/).map(id => text(document.getElementById(id))).join(' ').trim();
    if (el.getAttribute('aria-label')?.trim()) return el.getAttribute('aria-label')!.trim();
    if ((el as HTMLInputElement).labels?.length) return [...(el as HTMLInputElement).labels!].map(text).join(' ').trim();
    if (['BUTTON', 'A', 'SUMMARY'].includes(el.tagName)) return text(el) || el.getAttribute('title') || '';
    return el.getAttribute('title') ?? '';
  };
  const controls = [...document.querySelectorAll<HTMLElement>('main button, main a[href], main input, main select, main textarea, main summary')]
    .filter(el => !(el as HTMLInputElement).type || (el as HTMLInputElement).type !== 'hidden');
  const unnamed = controls.filter(el => !nameOf(el)).map(el => el.outerHTML.slice(0, 160));
  const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
  const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
  const headings = [...document.querySelectorAll('main h1, main h2, main h3, main h4, main h5')].map(el => Number(el.tagName[1]));
  const skips = headings.flatMap((level, index) => index && level > headings[index - 1] + 1 ? [`h${headings[index - 1]}→h${level}`] : []);
  return { controls: controls.length, unnamed, duplicateIds, headingSkips: [...new Set(skips)] };
});

async function tabWalk(page: Page, steps: number) {
  await page.locator('body').click({ position: { x: 1, y: 1 } });
  const seen: { name: string; ring: boolean }[] = [];
  for (let i = 0; i < steps; i++) {
    await page.keyboard.press('Tab');
    seen.push(await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return { name: 'body', ring: false };
      const style = getComputedStyle(el);
      const ring = (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none';
      const label = el.getAttribute('aria-label') || (el as HTMLInputElement).labels?.[0]?.textContent || el.textContent || el.id || el.tagName;
      return { name: `${el.tagName.toLowerCase()}:${label.replace(/\s+/g, ' ').trim().slice(0, 40)}`, ring };
    }));
  }
  return seen;
}

test('research screen: names, ids, headings, keyboard reach and focus ring', async ({ page }) => {
  test.setTimeout(240_000);
  const token = (JSON.parse(readFileSync(process.env.A11Y_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = process.env.A11Y_OUT!; mkdirSync(out, { recursive: true });
  const result: Record<string, unknown> = {};
  await page.goto('/');
  result.before_connect = await audit(page);
  // Keyboard only: type the token and submit with Enter.
  const walkBefore = await tabWalk(page, 12);
  result.walk_before = walkBefore;
  await page.locator('#research-token').focus();
  await page.keyboard.type(token);
  await page.keyboard.press('Enter');
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
  // Keyboard only: choose a bundle with the arrow keys.
  await page.locator('#research-bundle').focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('region', { name: '실제 자료 원문' })).toBeVisible();
  result.after_bundle = await audit(page);
  result.walk_after = await tabWalk(page, 70);
  // Open a source detail from the keyboard and close it again.
  const cite = page.getByRole('region', { name: '실제 자료 원문' }).locator('.research-source-row').first().getByRole('button').first();
  await cite.focus(); await page.keyboard.press('Enter');
  const detail = page.getByRole('article', { name: '인용 원문 상세' });
  await expect(detail).toBeVisible();
  result.detail_focus_after_open = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.closest('[aria-label="인용 원문 상세"]') ? 'inside detail' : `${document.activeElement?.tagName}:${(document.activeElement?.textContent ?? '').trim().slice(0, 30)}`);
  result.with_detail = await audit(page);
  // Close from the keyboard (Tab from the focused heading reaches the close button) and see where focus returns.
  await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
  await expect(detail).toHaveCount(0);
  result.focus_after_close = await page.evaluate(() => `${document.activeElement?.tagName}:${(document.activeElement?.textContent ?? '').trim().slice(0, 30)}`);
  await page.screenshot({ path: join(out, 'detail-open.png') });
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify(result, null, 1)}\n`);
});
