# 세션 작업기록 — 최길웅-20261006-028 (배정 PM-20261006-WEB-REBALANCE-R2, P2-WEB-003)

- 기록 ID: 최길웅-20261006-028 / 시작 2026-10-06 14:2x KST / 담당자 최길웅(choigilung) / 수행 AI: Claude Code(PC 데스크톱 Code 탭, 수동 세션)
- 브랜치 `codex/web-rebalance-r2`, 기준 main `d0b8e3e`(PR #159 병합 포함). 작업 공간: 시험 worktree `Desktop/lgax-wt-live`.
- 연결 근거: [최길웅-E023](../../../작업근거/세션/최길웅/rebalance-r2-20261006.md). 개인 기록 파일은 열린 #158이 수정 중이라, 충돌을 피하려고 세션 파일에 쓴다.
- 자동화: 팀·개인 OFF, Worker 예약 `LGAX-Worker-choigilung` Disabled를 유지한다. 이 세션은 사람 지시를 받은 수동 진행이다.

## 1. 지시 출처와 원문

- PM 배정: [Issue #25 댓글](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/25) `LGAX-ASSIGNMENT PM-20261006-WEB-REBALANCE-R2`(정이량, 2026-10-06 14:13 KST). 같은 배정 메일은 이 기록을 쓸 때 아직 수신 전이다.
- 발췌:
  - "정상코어accept가확인되기전에도중복클릭·질문/보류/실패·조건중복·회차분리·근거원문·이력재조회·JSON/Markdown내보내기를검증한다. failed/held처리성공을정상상품기획완주로표현하지않는다."
  - "INVALID_NO_CANDIDATE_REVIEW는원문/hash·규격/검토완전성확인실패이며후보없음자체를오류로설명하지않는다. … 실제새출력으로메시지/다음행동을재확인한다."
  - "황대겸/신진하가독립대조한실제정상run을받은뒤후보선택→조건변경→변경전후/원문/내보내기를같은프로젝트·run으로검증한다. 코어실패시웹에서가짜accept를만들지않고실행ID/막힘을보고한다."
  - "편집은apps/web·웹검사/사용안내와자기기록이다. 동향은별도WEB-TRENDS-REBALANCE-R2의WEB005/#27·149로보고한다."
  - 다음 행동: "WEB003/#25보고와157인수상태확인. 코어실행대기에는승인된WEB005158결함수정을진행한다."
  - 기한: "2026-10-06 18:00 KST 부분 PR/검증 근거 또는 구체 막힘 보고"
- 사용자 지시: "다음 할거 파악해" → AI 정리 → "진행해".
- 같은 시각 PR #158에 PM 검수 CHANGES_REQUESTED(05:03Z)가 있었다. 리뷰 동향 패널에서 구간이 바뀔 때 이전 원문이 남고, 늦은 응답을 받아들이는 결함이다. 이 수정은 #158 브랜치에서 하고 별도 기록(029)으로 남긴다.

## 2. 해석과 계획(AI 해석)

1. 착수 보고(이 기록)와 #157 인수 상태 확인. #157은 main `1a50dbe`에 병합됐다(14:07 KST). PM 정식 인수 표시는 아직 확인하지 않았다.
2. 코어 정상 run을 기다리는 동안 #158 결함을 수정한다(웹만).
3. 정상 accept 전 부분 검증: 고정 main 코드로 띄운 실서버(시험 DB)와 실제 qwen3:8b run에서 다음을 확인하고 근거를 남긴다.
   - 중복 클릭
   - 질문·보류·실패
   - 조건 중복
   - 회차 분리
   - 근거 원문
   - 이력 재조회
   - JSON·Markdown 내보내기
   - `INVALID_NO_CANDIDATE_REVIEW` 등 새 코어(#159) 출력의 메시지와 다음 행동
4. 독립 대조된 정상 run을 받으면 후보 선택 → 조건 변경 → 변경 전후·원문·내보내기를 같은 프로젝트·run으로 검증한다. 받기 전에는 막힘으로 보고한다.
- 가정: "고정 main"은 이 브랜치의 기준 commit `d0b8e3e`(이후 main이 바뀌면 다시 기록)로 해석했다. 사용자의 개발 서버(5173)와 API(18867·18869)는 `Desktop/lgax`의 사용자 것이라, 시험 서버를 띄우려면 5173을 PID로만 잠시 내리고 끝나면 다시 켠다.

## 3. 진행 기록

### 3-1. 착수·#158 수정(14:2x~14:5x KST)
- 착수 보고 ACCEPTED(Project 반영 확인).
- #158 결함 수정은 [기록 029](trends-drilldown-fix-20261006.md)에 따로 남겼다. head `e431089`, 연결 중단 검사 추가 `62a70a1`, CI 4/4.
- 14:15 KST 배정 메일 PM-20261006-WEB-TRENDS-REBALANCE-R2도 같은 결함 수정을 요구했다. 연결 중단 검사로 보완했다.

### 3-2. 실서버 준비와 막힘(14:3x~14:4x KST)
- 모델 프록시를 띄웠다: `python -m services.automation.model_proxy --config C:/LGAX-state/choigilung/client.json`, loopback 18873. `/api/tags`에서 qwen3:8b digest `500a1f067a9f…b41`을 확인했다.
- 새 시험 DB(`private/workspace-rebalance-r2`, `scripts/init_workspace.py`)로 판단 서버 18879를 띄웠다(`--enable-planning`, 출력 8192 / 문맥 16384 / 240초 / think false).
- 사용자 개발 서버 5173(PID 4820) 종료를 AI가 시도했으나 Claude Code 자동 모드 권한 검사(Interfere With Workloads)가 거부했다. 우회하지 않았다.
  - 판단 서버 허용 출처가 `workspace_server.py:25`에 5173으로 고정이라 다른 포트는 쓸 수 없다.
  - 사용자가 cmd 창에서 직접 종료했다.
- 시험 웹을 5173에 띄웠다(`LGAX_WORKSPACE_PROXY=http://127.0.0.1:18879 npm run dev`, 이 worktree).
- 첫 E2E는 공통 API 18867이 응답하지 않아 연결 단계에서 실패했다(모델 호출 0, `e2e-fridge-attempt0-api-unresponsive/`).
  - 원인: 18867을 띄운 cmd 창 제목이 "선택"이었다. Windows 빠른 편집 선택 모드라 출력이 막혀 있었다.
  - 사용자가 Esc로 풀었고, 응답 200을 확인했다.

### 3-3. 세 제품 엄격 실모델 E2E(14:4x~14:5x KST, `e2e/real-planning.spec.ts`)
- FRIDGE-A `run-4ccf79bd…`: held, 수정 0회.
  - need_extract(프롬프트 5,516자)와 product_compare(9,756자)는 실제 생성됐다.
  - **concept_draft는 프롬프트 23,300자로 ollama 어댑터 상한 16,000자(`model_client.py:212,449`)를 넘었다.** `prompt_too_large` → `INVALID_ARGUMENT`가 나서 생성하지 않았다.
  - 저장된 두 단계 출력으로 `build_quality_context`를 재생하면 오류가 없다(길이 문제로 판단).
  - #159가 콘셉트 단계에 `quality_context`를 더해 길어진 것으로 추정한다(AI 추정, 코어 확인 필요).
  - E2E는 생성되지 않은 호출을 "Generation metadata missing"으로 거절했다(의도된 엄격 검사).
- DISHWASHER-A:
  - 1회차 `run-066d8289…`: held. need_extract → no_candidate_review, `NO_CANDIDATE_VIOLATION`·`NO_CANDIDATE_UNCERTAIN`.
  - 조건 교정 `run-63ab7bf8…`: failed/unresolved. 수정 2/2 후 `NON_COMPLAINT_AS_NEED`.
  - **E2E flow_completed**: 저장, 같은 run ID, JSON·Markdown 내보내기 완전, 이전 run 불변.
- MICROWAVE-A:
  - 1회차 `run-a4176848…`: held(`NO_CANDIDATE_*`).
  - 조건 교정 `run-0180fefa…`: 첫 호출에서 `MODEL_UNAVAILABLE`(1.2초, 상세 가림). E2E 실패.
- accept 0. 웹은 가짜 accept나 후보를 만들지 않았다.
- 막힘 보고: [Issue #25 댓글](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/25#issuecomment-6010292189), 황대겸·PM 멘션.

### 3-4. accept 전 부분 검증(`e2e/rebalance-manual-check.spec.ts`, 새 opt-in 점검)
- 토큰을 화면에 직접 치지 않도록 토큰 파일을 읽는 Playwright 점검으로 실제 화면을 조작했다.
- 결과(`manual/manual-checks.json`, 9개 ok):
  - **보류·실패 표시:** 세 제품 최신 run 모두 등록되지 않은 원 코드 노출 없음.
  - **회차 분리:** 요청 회차 0 "원 요청" / 1 "사용자 조건 변경", "Agent 내부 수정 n/2회(실행 내부 회차이며 사용자 변경이 아님)".
  - **조건 중복:** "이미 같은 조건이 있습니다", 새 POST 0.
  - **근거 원문:** 후보가 없는 run은 후보별 근거 추적 대신 판단 실행 기록의 입력 원문 4건·기능 1개를 표시한다.
  - **이력 재조회:** 새로고침 후 다시 연결해도 run 순서가 같다.
  - **세 번 클릭 저장:** POST 1회(`…/runs`), 새 실행 `run-b5886243…`.
- 1차 점검(`manual-checks-attempt1.json`)의 "세 번 클릭 실패"는 판정 기준 오류였다. 선택된 프로젝트에서는 버튼이 "변경 요청 저장"이라 프로젝트 POST가 없다. 실제 요청은 그때도 1회였다. 근거 추적 미표시도 후보 없음 때문이라 판정을 고쳤다.
- 1차에서 실행된 새 run `run-77dd3b80…`(failed)은 그대로 둔다.
- 첫 run 화면(`manual-first-run/`, 모델 호출 없음)에서 새 코어 문구를 확인했다.
  - "후보 없음 판단이 원자료와 맞지 않습니다 (NO_CANDIDATE_VIOLATION · compare 단계)"
  - "후보 없음 판단을 확인할 자료가 부족합니다 (NO_CANDIDATE_UNCERTAIN · concepts 단계)"
  - 다음 행동: "자료 범위나 근거를 확인한 뒤 새 입력으로 다시 실행해야 합니다. 이 결과의 후보는 선택할 수 없습니다."
- 발견(웹 밖): `prompt_too_large`가 화면에 "INVALID_ARGUMENT 작업실 입력 값을 확인해 주세요."로 보인다. 기획자 입력 문제처럼 읽히지만, 서버가 상세를 가리므로 웹은 구분할 수 없다. 코어·API 쪽 코드나 문구 분리를 요청했다.
- `INVALID_NO_CANDIDATE_REVIEW` 문구 보정(웹):
  - PM 지적("후보없음자체를오류로설명하지않는다")에 맞춰 바꿨다.
  - 이전: "후보 없음 검토 응답이 규격에 맞지 않습니다"
  - 변경: "후보 없음 판단을 검토한 응답이 원문·범위·완전성 확인을 통과하지 못했습니다(후보 없음 자체의 오류가 아님)"
  - 근거: `planning_agent.py`에서 no_candidate_review의 VALIDATION_FAILED일 때 이 코드를 낸다.
  - 이번 실제 run들에서는 이 코드가 나오지 않아 실제 화면 확인은 하지 못했다.

### 3-5. 전자레인지 재시도(PR #163 게시 뒤, 같은 서버, `e2e-microwave-retry/`)
- `MODEL_UNAVAILABLE`은 일시 오류였다.
- 재시도 1회차 `run-53c5eb69…`(기존 프로젝트의 요청 회차 2): 8회 모두 실제 생성, concept_draft 9,792 / 10,027자. 2회 수정 뒤 held(`NO_CANDIDATE_*`).
- 조건 교정 `run-2202ca45…`: need_extract → product_compare → concept_draft(10,000자, 생성) → **semantic_review 프롬프트 16,730자 > 16,000** → `INVALID_ARGUMENT`(생성 없음). held, 수정 0회.
- 결론: 냉장고는 concept_draft, 전자레인지는 semantic_review(accept 직전)에서 **같은 프롬프트 길이 상한**에 막힌다. E2E는 "Generation metadata missing"으로 실패했다(생성 없는 호출 거절).

## 4. 검사
- 웹 `npm run test`: 26 files / 441 passed / 5 skipped, safe-ci 4/4.
- typecheck·build 통과.
- `playwright test --list`: 새 점검 포함 7개. 새 점검은 토큰 환경변수가 없으면 skip한다.
- 증빙 폴더 비밀 검사: 시험 DB 토큰 문자열 0건(5.6MB).

## 5. 완료/미완료·다음
- 완료(개별 검증, 부분): accept 전 웹 흐름 9개 항목, 세 제품 실제 run 저장·표시·내보내기·이전 불변(식기세척기 E2E 완주), 새 코어 문구 확인, 코어 막힘의 원인 특정.
- 미완료:
  - 정상 accept run 수신 뒤 후보 선택 → 조건 변경 → 변경 전후·원문·내보내기 검증
  - (해결) 전자레인지 `MODEL_UNAVAILABLE`은 재시도에서 일시 오류로 확인. 대신 semantic_review 길이 초과를 새로 발견
  - PM 검수·병합. P2-WEB-003 전체 Done이 아니다.
- 대기 의존: 황대겸 concept_draft·semantic_review 프롬프트 길이(또는 어댑터 상한) 해결, 독립 대조된 정상 run.
- 다음: PR 게시 → P2-WEB-003 검수 요청 보고 → 시험 서버 종료·개발 서버 재시작.
