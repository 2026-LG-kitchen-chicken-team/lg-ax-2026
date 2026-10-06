// Record 020: a live qwen3:8b run (evals/web/20261005/p2-web-003-live-model) stored the core's violation code
// "REVIEW_CONFLICT" as the hold / no-candidate reason, and the web showed the bare code. These tests pin the display
// mapping against the core's own code list and the stored live runs. No model is called; stored data is not changed.
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { planningExecutionView, reasonText, runSources } from './judgement';
import { buildExport, exportMarkdown } from './planning';
import type { RunSnapshot } from './planning';

const root = (path: string) => resolve(process.cwd(), '../..', path);
const read = (path: string) => JSON.parse(readFileSync(root(path), 'utf-8'));
const LIVE = 'evals/web/20261005/p2-web-003-live-model';
const FIRST: RunSnapshot = read(`${LIVE}/stored-run-first.json`);
const SECOND: RunSnapshot = read(`${LIVE}/stored-run-second.json`);
const UNREGISTERED = '(설명이 등록되지 않은 검사 코드)';

// Record 027: PR #159 moved the checks out of judgement_contract.py (errors.append in feature_support.py, residual_matrix.py,
// code dicts in planning_agent.py), so the codes are collected from every core module and from each way the core emits one:
// flag(...), errors.append(...) and {"code": ...}, including both branches of a conditional expression.
const CORE = root('packages/core/src/lgax_core');
const EMIT = [/\bflag\(\s*([^,)]*)/g, /\berrors\.append\(\s*([^,)]*)/g, /"code":\s*([^,}]*)/g];
const CODE_LITERAL = /"([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)"/g;
// no_candidate_review.py builds "NO_CANDIDATE_" + verdict.upper(); "consistent" is not fed back (황대겸, record 027).
const BUILT_CODES = ['NO_CANDIDATE_VIOLATION', 'NO_CANDIDATE_UNCERTAIN'];
// HTTP/argument error codes that never reach hold_reasons / violations.
const NOT_REASONS = new Set(['INVALID_ORIGIN']);

function pythonFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return pythonFiles(path);
    return entry.name.endsWith('.py') ? [path] : [];
  });
}

function coreReasonCodes(): string[] {
  const codes = new Set<string>(BUILT_CODES);
  for (const file of pythonFiles(CORE)) {
    const source = readFileSync(file, 'utf-8');
    for (const pattern of EMIT) {
      for (const emitted of source.matchAll(pattern)) {
        for (const literal of emitted[1].matchAll(CODE_LITERAL)) {
          if (!NOT_REASONS.has(literal[1])) codes.add(literal[1]);
        }
      }
    }
  }
  return [...codes].sort();
}

describe('reasonText: core violation codes used as reasons', () => {
  it('has a label for every code the core can emit as a violation or reason', () => {
    const codes = coreReasonCodes();
    expect(codes.length).toBeGreaterThan(40);
    expect(codes).toEqual(expect.arrayContaining(['REVIEW_CONFLICT', 'GAP_NEED_MISMATCH', 'SEMANTIC_QUESTION', ...BUILT_CODES]));
    for (const code of codes) {
      const text = reasonText(code);
      expect(text, code).not.toContain(UNREGISTERED);
      expect(text, code).toMatch(new RegExp(`^[^A-Z].* \\(${code}\\)$`));
    }
  });

  it('builds the two no-candidate codes the way the core does', () => {
    const source = readFileSync(join(CORE, 'no_candidate_review.py'), 'utf-8');
    expect(source).toContain('"NO_CANDIDATE_" + row["verdict"].upper()');
    expect(reasonText('NO_CANDIDATE_VIOLATION')).toBe('후보 없음 판단이 원자료와 맞지 않습니다 (NO_CANDIDATE_VIOLATION)');
  });

  it('keeps free text unchanged and marks an unknown bare code instead of hiding it', () => {
    expect(reasonText('선반 분리 방법을 쉽게 확인할 수 있도록 안내 표시를 제공해 주세요.')).toBe('선반 분리 방법을 쉽게 확인할 수 있도록 안내 표시를 제공해 주세요.');
    expect(reasonText('NEW_CORE_CODE')).toBe(`NEW_CORE_CODE ${UNREGISTERED}`);
    expect(reasonText('FRIDGE-A')).toBe('FRIDGE-A');
    expect(reasonText('REVIEW_CONFLICT')).toBe('리뷰가 서로 상충합니다 (REVIEW_CONFLICT)');
  });
});

describe('live qwen3:8b runs (record 020) read with labelled reasons', () => {
  it('stores the bare code as the held run reason, unchanged by the web', () => {
    const view = planningExecutionView(SECOND);
    expect(view.kind).toBe('ok');
    const output = (SECOND.output as unknown as { planning_execution: { output: { hold_reasons: string[]; no_candidate_reasons: string[] } } }).planning_execution.output;
    expect(output.hold_reasons).toEqual(['REVIEW_CONFLICT']);
    expect(output.no_candidate_reasons).toEqual(['REVIEW_CONFLICT']);
  });

  it('exports Markdown with the label while the JSON keeps the stored code', () => {
    for (const snapshot of [FIRST, SECOND]) {
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-05T08:00:00.000Z', [FIRST, SECOND]);
      const markdown = exportMarkdown(doc);
      expect(markdown).not.toMatch(/^- [A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/m);
      expect(markdown).not.toContain(UNREGISTERED);
      if (snapshot === SECOND) {
        expect(markdown).toContain('- 리뷰가 서로 상충합니다 (REVIEW_CONFLICT)');
        expect(JSON.stringify(doc)).toContain('"REVIEW_CONFLICT"');
      }
    }
  });
});
