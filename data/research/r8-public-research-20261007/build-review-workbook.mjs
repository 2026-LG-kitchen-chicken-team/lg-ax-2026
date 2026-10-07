import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const pack = process.argv[2] || path.dirname(fileURLToPath(import.meta.url));
const output = process.argv[3];
const scratch = process.argv[4] || process.cwd();
if (!output) throw new Error('Usage: node build-review-workbook.mjs PACK_DIR OUTPUT_DIR [SCRATCH_DIR]');
const read = async name => JSON.parse(await fs.readFile(path.join(pack, name), 'utf8'));
const [reviews, products, official] = await Promise.all([read('records.json'), read('products.json'), read('official-sources.json')]);
const labels = { fridge: '냉장고', microwave: '전자레인지', dishwasher: '식기세척기' };
const groups = Object.fromEntries(products.map(p => [p.model_id, labels[p.product_group]]));
const workbook = Workbook.create();
const overview = workbook.worksheets.add('자료 현황');
const registry = workbook.worksheets.add('제품 목록');
const raw = workbook.worksheets.add('후기 원문');
const docs = workbook.worksheets.add('공식 근거');
for (const sheet of [overview, registry, raw, docs]) {
  sheet.showGridLines = false;
  sheet.tabColor = '#334155';
}
const style = sheet => {
  const area = sheet.getUsedRange();
  area.format.font = { name: 'Arial', size: 10, color: '#202C3D' };
  area.format.verticalAlignment = 'center';
  area.format.rowHeight = 24;
};
const header = range => {
  range.format.fill = '#334155';
  range.format.font = { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' };
  range.format.horizontalAlignment = 'center';
  range.format.verticalAlignment = 'center';
  range.format.rowHeight = 30;
};
const date = value => value ? new Date(`${value}T00:00:00Z`) : null;
const fittedLines = (value, width) => String(value || '').split(/\r?\n/).reduce((lines, part) => {
  const units = [...part].reduce((n, c) => n + (c.codePointAt(0) > 255 ? 2 : 1), 0);
  return lines + Math.max(1, Math.ceil(units / width));
}, 0);

// One original review per row. Full text, hash, source locator and original holds remain separate columns.
const reviewHeaders = ['원 후기 ID', '제품군', '표시 페이지 모델', '구매 SKU', '별점', '원 분할', '구매일', '게시일', '날짜 기준', '후기 원문', '공개 본문 SHA256', '출처 URL', '원문 위치', '중복 그룹', '품질 표시', '원 정확모델 입력 보류 사유'];
const reviewRows = reviews.map(r => [r.original_review_id, groups[r.displayed_model_id], r.displayed_model_id,
  r.actual_purchased_model_id, r.rating, r.split, date(r.purchase_date), date(r.published_at),
  r.purchase_date ? '구매일만 확인' : '미상', r.text, r.text_sha256, r.source_url,
  r.source_locator, r.dedup_group_id, r.quality_flags.join(', '), r.input_hold_reasons.join(', ')]);
raw.getRange(`A1:P${reviews.length + 1}`).values = [reviewHeaders, ...reviewRows];
style(raw);
header(raw.getRange('A1:P1'));
raw.getRange('A:A').format.columnWidth = 15;
raw.getRange('B:B').format.columnWidth = 15;
raw.getRange('C:D').format.columnWidth = 22;
raw.getRange('E:E').format.columnWidth = 8;
raw.getRange('F:F').format.columnWidth = 28;
raw.getRange('G:I').format.columnWidth = 16;
raw.getRange('J:J').format.columnWidth = 120;
raw.getRange('K:K').format.columnWidth = 68;
raw.getRange('L:M').format.columnWidth = 100;
raw.getRange('N:N').format.columnWidth = 44;
raw.getRange('O:O').format.columnWidth = 50;
raw.getRange('P:P').format.columnWidth = 95;
raw.getRange(`G2:H${reviews.length + 1}`).setNumberFormat('yyyy-mm-dd');
raw.getRange(`E2:E${reviews.length + 1}`).setNumberFormat('0');
raw.getRange(`J2:J${reviews.length + 1}`).format.wrapText = true;
raw.getRange(`J2:J${reviews.length + 1}`).format.verticalAlignment = 'top';
raw.getRange(`J2:J${reviews.length + 1}`).format.autofitRows();
raw.tables.add(`A1:P${reviews.length + 1}`, true, 'PublicReviewRecords');
reviews.forEach((r, i) => { raw.getRange(`A${i + 2}:P${i + 2}`).format.rowHeight = Math.min(409, Math.max(30, fittedLines(r.text, 110) * 15 + 12)); });
raw.freezePanes.freezeRows(1);
raw.freezePanes.freezeColumns(2);
raw.getRange(`F2:F${reviews.length + 1}`).conditionalFormats.add('containsText', { text: 'quarantine', format: { fill: '#FFF1DC', font: { color: '#92400E' } } });

const officialHeaders = ['근거 ID', '제품군', '자료 종류', '브랜드', '표시 모델', '문서 버전', '원문 발췌', '페이지/위치', '게시일', '확인일', '적용 범위 및 한계', '출처 URL'];
const officialRows = official.map(s => [s.source_id, labels[s.product_group], s.source_type, s.brand, s.page_model,
  s.document_version, s.text, JSON.stringify(s.locator), date(s.published_at),
  date(s.metadata.verification_date || (s.collected_at || '').slice(0, 10)),
  [s.metadata.applicability, s.metadata.scope_caveat, ...(s.metadata.comparison_limits || []),
    ...Object.values(s.metadata.feature_conditions || {}).flat()].filter(Boolean).join('\n'), s.url]);
docs.getRange(`A1:L${official.length + 1}`).values = [officialHeaders, ...officialRows];
style(docs);
header(docs.getRange('A1:L1'));
docs.getRange('A:A').format.columnWidth = 51;
docs.getRange('B:D').format.columnWidth = 15;
docs.getRange('E:E').format.columnWidth = 23;
docs.getRange('F:F').format.columnWidth = 35;
docs.getRange('G:G').format.columnWidth = 95;
docs.getRange('H:H').format.columnWidth = 75;
docs.getRange('I:J').format.columnWidth = 15;
docs.getRange('K:K').format.columnWidth = 110;
docs.getRange('L:L').format.columnWidth = 110;
docs.getRange(`I2:J${official.length + 1}`).setNumberFormat('yyyy-mm-dd');
docs.getRange(`G2:K${official.length + 1}`).format.wrapText = true;
docs.getRange(`G2:K${official.length + 1}`).format.verticalAlignment = 'top';
docs.getRange(`G2:K${official.length + 1}`).format.autofitRows();
docs.tables.add(`A1:L${official.length + 1}`, true, 'OfficialEvidenceRecords');
officialRows.forEach((r, i) => { docs.getRange(`A${i + 2}:L${i + 2}`).format.rowHeight = Math.min(409, Math.max(40, Math.max(fittedLines(r[6], 85), fittedLines(r[7], 65), fittedLines(r[10], 100)) * 15 + 12)); });
docs.freezePanes.freezeRows(1);
docs.freezePanes.freezeColumns(1);

overview.getRange('A2').values = [['LG 실제 공개 자료 현황']];
overview.getRange('A4:F7').values = [
  ['제품군', '보관 후기', '개발 입력', '평가 후보', '시연 후보', '격리'],
  ['냉장고', null, null, null, null, null],
  ['전자레인지', null, null, null, null, null],
  ['식기세척기', null, null, null, null, null],
];
const last = reviews.length + 1;
for (let row = 5; row <= 7; row++) {
  overview.getRange(`B${row}`).formulas = [[`=COUNTIFS('후기 원문'!$B$2:$B$${last},$A${row})`]];
  const splits = ['development', 'independent_evaluation', 'demonstration', 'quarantine'];
  overview.getRange(`C${row}:F${row}`).formulas = [splits.map(split => `=COUNTIFS('후기 원문'!$B$2:$B$${last},$A${row},'후기 원문'!$F$2:$F$${last},"${split}")`)];
}
overview.getRange('A8').values = [['합계']];
overview.getRange('B8:F8').formulas = [['=SUM(B5:B7)', '=SUM(C5:C7)', '=SUM(D5:D7)', '=SUM(E5:E7)', '=SUM(F5:F7)']];
overview.getRange('A11:B17').values = [
  ['항목', '건수'], ['별점 1~3 후기', null], ['별점 5 후기', null],
  ['구매 SKU 미확인 후기', null], ['게시일 미확인 후기', null], ['설명서 발췌', null], ['설명서 확인 페이지 모델', null],
];
overview.getRange('B12').formulas = [[`=COUNTIFS('후기 원문'!$E$2:$E$${last},">=1",'후기 원문'!$E$2:$E$${last},"<=3")`]];
overview.getRange('B13').formulas = [[`=COUNTIFS('후기 원문'!$E$2:$E$${last},5)`]];
overview.getRange('B14').formulas = [[`=COUNTBLANK('후기 원문'!$D$2:$D$${last})`]];
overview.getRange('B15').formulas = [[`=COUNTBLANK('후기 원문'!$H$2:$H$${last})`]];
overview.getRange('B16').formulas = [[`=COUNTIFS('공식 근거'!$C$2:$C$${official.length + 1},"manual")`]];
overview.getRange('B17').formulas = [["=COUNTIFS('제품 목록'!$D$2:$D$19,\"확인\")"]];
overview.getRange('H11:H17').values = [
  ['현재 범위'], ['제품 페이지별 목적 표본이며 시장 발생률로 해석할 수 없음'],
  ['별점과 긍정·부정·혼합 감정 분류는 서로 다름'],
  ['구매 SKU·게시일 미상. 구매일을 게시일로 바꾸지 않음'],
  ['개발 입력만 CORE에 제공. 평가·시연 후보는 원 보류 유지'],
  ['FAQ·설치·경쟁 공식 근거 각 1개. Q&A 원문은 미확인'],
  ['설명서 존재는 고객이 쉽게 이해·실행했다는 증거가 아님'],
];
overview.getRange('H20:H21').values = [['독립 시연 보류 원 후기 ID: 776453, 842682'], ['표본 구성: 기존 179건(별점 5) + 최근·낮은 별점 표본 신규 59건']];
const manualModels = new Set(official.filter(s => s.source_type === 'manual').map(s => s.page_model));
registry.getRange('A1:E19').values = [['제품군', '페이지 모델', '제품명', '설명서 확인', '공식 페이지 URL'],
  ...products.map(p => [labels[p.product_group], p.model_id, p.name, manualModels.has(p.model_id) ? '확인' : '미확인', p.displayed_product_identity.canonical_url])];
style(registry);
header(registry.getRange('A1:E1'));
registry.getRange('A:A').format.columnWidth = 17;
registry.getRange('B:B').format.columnWidth = 22;
registry.getRange('C:C').format.columnWidth = 75;
registry.getRange('D:D').format.columnWidth = 18;
registry.getRange('E:E').format.columnWidth = 110;
registry.getRange('D2:D19').conditionalFormats.add('containsText', { text: '미확인', format: { fill: '#FFF1DC', font: { color: '#92400E' } } });
registry.tables.add('A1:E19', true, 'RegisteredProductPages');
registry.freezePanes.freezeRows(1);
style(overview);
overview.tabColor = '#142E4C';
overview.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true, color: '#142E4C' };
overview.getRange('A:A').format.columnWidth = 35;
overview.getRange('B:B').format.columnWidth = 22;
overview.getRange('C:E').format.columnWidth = 18;
overview.getRange('F:F').format.columnWidth = 18;
overview.getRange('G:G').format.columnWidth = 3;
overview.getRange('H:H').format.columnWidth = 102;
header(overview.getRange('A4:F4'));
header(overview.getRange('A11:B11'));
overview.getRange('B5:F8').setNumberFormat('#,##0');
overview.getRange('B12:B17').setNumberFormat('#,##0');
overview.getRange('A8:F8').format.font.bold = true;
overview.getRange('A8:F8').format.borders = { top: { style: 'thin', color: '#64748B' } };
overview.getRange('H11').format.font.bold = true;

// Final recalc, source-row parity, key formulas and export. No native Excel behavior is inferred.
const originalRating = raw.getRange('E2').values[0][0];
raw.getRange('E2').values = [[1]];
if (overview.getRange('B12').values[0][0] !== 31 || overview.getRange('B13').values[0][0] !== 207) throw new Error('Rating summary did not recalculate');
raw.getRange('E2').values = [[originalRating]];
workbook.recalculate();
for (let i = 0; i < reviews.length; i++) {
  const value = raw.getRange(`J${i + 2}`).values[0][0];
  if (value !== reviews[i].text) throw new Error(`Review body changed: ${reviews[i].original_review_id}`);
}
const totals = overview.getRange('B8:F8').values[0];
if (JSON.stringify(totals) !== JSON.stringify([238, 141, 36, 49, 12])) throw new Error(`Wrong summary totals: ${JSON.stringify(totals)}`);
const counts = overview.getRange('B12:B17').values.flat();
if (JSON.stringify(counts) !== JSON.stringify([30, 208, 238, 238, 15, 3])) throw new Error(`Wrong details: ${JSON.stringify(counts)}`);
const errors = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 20 }, maxChars: 1500 });
console.log(errors.ndjson);
const table = await workbook.inspect({ kind: 'table', range: "'자료 현황'!A4:F8", include: 'values,formulas', tableMaxRows: 5, tableMaxCols: 6, maxChars: 2200 });
console.log(table.ndjson);
await fs.mkdir(output, { recursive: true });
await fs.mkdir(scratch, { recursive: true });
for (const [name, range, file] of [['자료 현황', 'A2:H21', 'overview.png'], ['제품 목록', 'A1:D7', 'products.png'], ['후기 원문', 'A1:J5', 'reviews.png'], ['공식 근거', 'A1:G5', 'official.png']]) {
  const preview = await workbook.render({ sheetName: name, range, scale: 1, format: 'png' });
  await fs.writeFile(path.join(scratch, file), new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(output, 'LG-실제공개자료-238건-20261007.xlsx'));
console.log(JSON.stringify({ file: path.join(output, 'LG-실제공개자료-238건-20261007.xlsx'), reviews: reviews.length, officialSources: official.length, formulaTotals: totals, bodyParity: true, nativeExcelOpened: false }));
