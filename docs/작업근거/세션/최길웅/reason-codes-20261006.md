# 최길웅-E022 — 코어 검사 코드 설명·웹 검사 보강 근거

- 연결 기록: [최길웅-20261006-027](../../../작업기록/세션/최길웅/reason-codes-20261006.md). 확인일 2026-10-06 KST.
- 기준: main `d0cfbde3f1ac1054ae94a061b57fbd0a1dcc398c`. 비교 대상: PR #159 head `9ce5afbef7f2ff2decd26d9d0f317213cf6e0b29`(`git fetch origin pull/159/head:refs/remotes/pr/159`).

## 원인 근거

- PR #159 CI(2026-10-06 04:19 UTC) `web` job: `src/reasonText.test.ts > has a label for every code review_judgement can flag`, `AssertionError: expected 28 to be greater than 40`(`reasonText.test.ts:22`).
- 원인: 이전 검사는 `judgement_contract.py` 한 파일의 `flag("…")`만 찾았다. #159 diff에서 `judgement_contract.py`의 개별 `flag("GAP_…")`·`flag("CONCEPT_…")` 호출이 `flag(violation["code"], violation["stage"])`로 바뀌었고, 코드는 `feature_support.py`·`residual_matrix.py`의 `errors.append("…")`로 옮겨졌다.
- 같은 CI의 `python-and-harness` 실패(`AssertionError: 3 != 2`, `Lists differ: ['need_extract', 'no_candidate_review'] != ['need_extract']`)는 코어 회귀이며 이 작업 범위가 아니다.

## 코드 수집 대조(AI가 Python으로 미리 확인)

- 같은 수집 규칙(`flag(`·`errors.append(`·`"code":` 첫 인자식의 대문자 문자열)을 git 객체에서 직접 읽어 돌렸다. main과 #159 모두 50개를 찾았다.
- #159 기준 코드가 나오는 파일: concept_lineage, documents_server, feature_support, judgement_contract, planning_agent, residual_matrix, semantic_review.
- 수정 전 웹에 설명이 없던 코드: `COMPARE_CITATION_OMISSION`, `INVALID_NO_CANDIDATE_REVIEW`, `INVALID_ORIGIN`(제외 대상)과 동적 `NO_CANDIDATE_*`.
- `INVALID_ORIGIN` 위치: `documents_server.py:30`의 HTTP 403 `JSONResponse`, `source_ranges.py:161,164`의 `_fail`. 판단 사유가 아니라 제외했다.
- `INVALID_NO_CANDIDATE_REVIEW` 위치: `planning_agent.py:578` `"violations": [{"code": "INVALID_NO_CANDIDATE_REVIEW", "stage": "needs"}]`. 같은 형태의 `INVALID_SEMANTIC_REVIEW`는 `planning_agent.py:613`.
- 동적 코드: `no_candidate_review.py`의 `"NO_CANDIDATE_" + row["verdict"].upper()`(main 45행, #159 48행). verdict 값과 `consistent` 제외는 황대겸 답을 따랐다(사용자 전달, 직접 코드 경로를 모두 추적하지는 않음).

## 실행 결과

| 명령(작업 위치 `Desktop/lgax-wt-live/apps/web`) | 코어 | 결과 |
|---|---|---|
| `npx vitest run src/reasonText.test.ts` | main `d0cfbde` | 5 passed |
| 같은 명령 | #159 `9ce5afb`의 packages/core를 잠시 덮어씀 | 5 passed |
| `npm run test` | main | Test Files 25 passed / 3 skipped, Tests 434 passed / 5 skipped, safe-ci check pass 4 / fail 0 |
| `npm run build` | main | built 성공(기존 chunk 크기 경고) |

- 첫 실행 실패(기록): 치환 스크립트가 `\b`를 U+0008로 넣고 RegExp 템플릿의 `\\(`를 `\(`로 바꿨다. 그래서 `ASSESSMENT_COVERAGE: expected '평가 목록이 … (ASSESSMEN…' to match /^[^A-Z].* (ASSESSMENT_COVERAGE)$/`가 났다. 원래 이스케이프로 복구한 뒤 위 결과가 나왔다.
- 덮어쓴 #159 코어는 되돌렸고, 이후 `git status --short`에 `apps/web/src/judgement.ts`, `apps/web/src/reasonText.test.ts`만 남았다.
- 의존성: worktree의 기존 `node_modules`를 썼다. `apps/web/package.json`·`package-lock.json`이 이전 설치 기준 `b477860`과 main 사이에 바뀌지 않았음을 `git diff --quiet`로 확인했다.

## 지지하는 주장 / 지지하지 않는 주장

- 지지: 현재 main과 #159 코어 모두에서 웹이 아는 판단 사유 코드에 한글 설명이 있다. 코어가 코드를 다른 모듈의 `errors.append`·코드 딕셔너리로 옮겨도 검사가 찾는다. #159의 web 실패 원인이 이 검사의 수집 범위였다.
- 지지하지 않음: 문자열을 이어 붙이거나 변수로 만드는 새 방식의 코드를 자동으로 찾는다는 것(그런 경우 명시 목록에 더해야 함). #159 전체 CI 통과. 실제 모델 실행이나 판단 품질. PM 검수·병합.
