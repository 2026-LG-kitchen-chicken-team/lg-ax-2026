# 최길웅-E023 — WEB-REBALANCE-R2(P2-WEB-003) 근거

- 연결 기록: [최길웅-20261006-028](../../../작업기록/세션/최길웅/rebalance-r2-20261006.md). 확인일 2026-10-06 KST.

## 시작 상태(직접 조회)

- main `d0b8e3e`(2026-10-06 14:12:43 KST, PR #159 병합). 그 사이 병합: #160 `69c545f`(14:01), #157 `1a50dbe`(14:07).
- Project 조회(`project_report.py status --member 최길웅`, observed 2026-10-06T05:13:09Z, published main `d0b8e3e`):
  - P2-WEB-003: doing / In Progress / Review requested
  - P2-WEB-004·005: pending, P2-WEB-003 대기
- PR #158: head `700cac9`, CI 4/4 통과, PM 검수 CHANGES_REQUESTED(2026-10-06T05:03:20Z).
- 배정 메일(Gmail 커넥터 읽기 전용 검색 `("LG AX" OR LGAX) newer_than:1d`): 최신은 MANUAL-FLOW-R1(01:34Z). REBALANCE-R2 메일은 아직 없다.
- `docs/pm/rebalance-20261006.md`: 배정이 읽으라고 한 문서인데, main `d0b8e3e`에는 아직 없다(`git ls-tree` 결과 없음).

## 검증 결과

- 코드: 웹·코어는 main `d0b8e3e`와 같다(이 브랜치는 기록·검사 스크립트·`judgement.ts` 문구 1줄만 추가). E2E proof의 `web_commit` `74471e8`은 착수 기록 commit이다.
- 환경:
  - 웹 5173(이 worktree), 판단 서버 18879(`--enable-planning`, 새 DB `private/workspace-rebalance-r2`), 공통 API 18867(사용자 프로세스, 읽기)
  - 모델 프록시 18873, qwen3:8b digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
  - 출력 8192 / 문맥 16384 / 240초 / think false, 합성 자료
- 모든 산출물: `evals/web/20261006/web-rebalance-r2/`

| 폴더 | 내용 | 결과 |
|---|---|---|
| `e2e-fridge-attempt0-api-unresponsive/` | 첫 시도. 공통 API 18867 무응답 | 연결 단계 실패, 모델 호출 0 |
| `e2e-fridge/` | FRIDGE-A, `stored-run-first.json` | held. concept_draft 프롬프트 23,300자 > 16,000 → `INVALID_ARGUMENT`(생성 없음). E2E 실패(Generation metadata missing) |
| `e2e-dishwasher/` | 1회차·조건 교정, 내보내기, 화면 | held(`NO_CANDIDATE_*`) → failed/unresolved(`NON_COMPLAINT_AS_NEED`, 2/2). **flow_completed**, 내보내기 완전, 이전 불변 |
| `e2e-microwave/` | 1회차·조건 교정 | held(`NO_CANDIDATE_*`) → `MODEL_UNAVAILABLE`(1.2초). E2E 실패 |
| `manual/` | 수동 점검 9개 + 1차 시도 기록 | 9 ok(1차의 판정 기준 오류 2건은 기록 028에 설명) |
| `manual-first-run/` | 첫 run 화면, 모델 호출 없음 | NO_CANDIDATE 두 코드의 한글 설명과 다음 행동 확인 |

- 프롬프트 길이 근거: 각 `stored-run-*.json`의 `planning_execution.model_calls[].prompt` 길이를 셌다.
  - FRIDGE-A: need_extract 5,516 / product_compare 9,756 / concept_draft 23,300
  - DISHWASHER-A: need_extract 3,629 / no_candidate_review 5,528
  - MICROWAVE-A: need_extract 3,572 / product_compare 5,510 / no_candidate_review 9,997
  - 상한: `model_client.py` `_ModelAdapter.max_prompt_characters = 16000`. 형식화 후 검사(449행).
- 재생: 저장된 FRIDGE-A need_extract·product_compare 출력으로 `concept_lineage.build_quality_context`를 호출하면 예외가 없다. `feature_support`의 support_basis 값 9개는 모두 `explicit_supported`(허용 값)였다.
- 웹 검사: vitest 26 files / 441 passed / 5 skipped, node 4/4, `tsc -b`·`vite build` 통과.
- 비밀 검사: 증빙 폴더(5,570,756 bytes)에서 시험 DB의 client·server 토큰 문자열 0건.

## 지지하는 주장 / 지지하지 않는 주장
- 지지:
  - 최신 main 웹이 실제 서버·실제 모델의 보류·실패·미해결 run을 성공처럼 보이지 않게 저장·표시·이력화·내보낸다.
  - 새 코어의 후보 없음 코드를 한글 설명과 다음 행동으로 보여 준다.
  - 중복 클릭·조건 중복·새로고침 재조회가 안전하다.
  - 현재 main 코어에서 FRIDGE-A는 콘셉트 단계 프롬프트 길이 초과로 후보 단계에 갈 수 없다.
- 지지하지 않음:
  - accept·후보 선택 흐름(실제 정상 run 없음)
  - 판단 품질
  - 전자레인지 `MODEL_UNAVAILABLE`의 원인(상세 가림, 재시도 안 함)
  - `INVALID_NO_CANDIDATE_REVIEW`의 실제 화면(이번 run에서 발생 안 함)
  - P2-WEB-003 완료
