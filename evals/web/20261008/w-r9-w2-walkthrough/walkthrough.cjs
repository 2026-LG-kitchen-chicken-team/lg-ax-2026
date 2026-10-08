// W2 walkthrough on the real test server (18969, model off) through the test web (5175), in headed Chrome.
// Token is read from the private credential file and never printed. Downloads are saved under private/ (git-ignored).
const { readFileSync, mkdirSync, writeFileSync } = require('node:fs');
const { join } = require('node:path');
const { chromium } = require(join(process.env.LGAX_ROOT, 'apps/web/node_modules/@playwright/test'));

const ROOT = process.env.LGAX_ROOT; // repository root
const BUNDLES = process.env.LGAX_E2E_RESEARCH_BUNDLE_DIR; // served bundle JSON copies (same SHA as data/research)
const OUT = join(ROOT, 'private/r9-review/w2-downloads');
mkdirSync(OUT, { recursive: true });
const token = JSON.parse(readFileSync(process.env.LGAX_E2E_RESEARCH_TOKEN_FILE, 'utf8')).token;
const dish = JSON.parse(readFileSync(join(BUNDLES, 'dishwasher.research-bundle.json'), 'utf8'));
const manual = JSON.parse(readFileSync(join(BUNDLES, 'microwave.manual-reference.research-bundle.json'), 'utf8'));
// Same independent predicate as the public guide contract (e2e officialGuideSource).
const guideEligible = s => s.source_kind === 'public' && ['manual', 'faq', 'installation', 'qa'].includes(s.source_type)
  && ['official_document', 'official_answer'].includes(s.source_role)
  && (() => { try { const h = new URL(s.url).hostname.toLowerCase(); return ['lge.com', 'lge.co.kr', 'samsung.com', 'samsungsvc.co.kr'].some(d => h === d || h.endsWith(`.${d}`)); } catch { return false; } })();

(async () => {
  const log = { steps: [] };
  const browser = await chromium.launch({ channel: 'chrome', headless: false, slowMo: 250 });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  let guideRequests = 0;
  page.on('request', r => { if (r.url().endsWith('/api/research/guides')) guideRequests += 1; });
  const panel = page.getByRole('region', { name: '실제 자료 원문' });
  const choose = async b => { await page.locator('#research-bundle').selectOption(b.bundle_id); await panel.locator('.research-source-row').nth(b.sources.length - 1).waitFor(); };
  const save = async (label, name) => {
    const [d] = await Promise.all([page.waitForEvent('download', { timeout: 30000 }), panel.getByRole('button', { name: label, exact: true }).click()]);
    const file = join(OUT, name); await d.saveAs(file);
    log.steps.push({ button: label, suggested: d.suggestedFilename(), saved: name });
  };

  await page.goto('http://127.0.0.1:5175/');
  await page.locator('#research-token').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await page.getByText('실제 자료 작업실 연결됨').waitFor();

  // 2. selected-source export: 1st, 2nd and 4th rows of the R9 dishwasher bundle
  await choose(dish);
  const checks = panel.locator('.research-source-check input');
  for (const i of [3, 0, 1]) await checks.nth(i).check();
  log.selected = [0, 1, 3].map(i => dish.sources[i].source_id);
  await save('선택 자료 JSON', 'selected-dishwasher.json');
  await save('선택 자료 Markdown', 'selected-dishwasher.md');

  // 3. official guide from the manual-reference bundle (all sources)
  await choose(manual);
  await panel.getByRole('button', { name: '표시 자료 모두 선택' }).click();
  await save('선택 공식자료 안내서 Markdown', 'guide-microwave-manual.md');
  await save('선택 공식자료 안내서 HTML', 'guide-microwave-manual.html');
  log.guide_requests_after_guides = guideRequests;

  // 4. refusal: one review + one guide-eligible official source in the dishwasher bundle
  await choose(dish);
  const review = dish.sources.findIndex(s => s.source_type === 'review');
  const official = dish.sources.findIndex(guideEligible);
  log.refusal_pair = { review: dish.sources[review].source_id, official: official >= 0 ? dish.sources[official].source_id : null };
  if (official >= 0) {
    await checks.nth(review).check(); await checks.nth(official).check();
    const before = guideRequests; let downloaded = false;
    page.once('download', () => { downloaded = true; });
    await panel.getByRole('button', { name: '선택 공식자료 안내서 Markdown', exact: true }).click();
    const alert = panel.getByRole('alert'); await alert.waitFor();
    await page.waitForTimeout(3000);
    log.refusal = { alert: await alert.innerText(), guide_requests_added: guideRequests - before, downloaded };
    await alert.scrollIntoViewIfNeeded();
    await page.locator('.research-source-selection').screenshot({ path: join(OUT, 'refusal.png') });
  }
  writeFileSync(join(OUT, 'walk-log.json'), JSON.stringify(log, null, 2));
  console.log(JSON.stringify(log, null, 2));
  await page.waitForTimeout(1500);
  await browser.close();
})().catch(e => { console.error('FAILED', e.message); process.exit(1); });
