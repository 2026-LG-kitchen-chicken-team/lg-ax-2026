# CORE003 공유 수정 예산의 연결 준비

PM 배정 [PM-20261005-CORE-002-ACTUAL-REVIEW-FOLLOWUP](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/8#issuecomment-5982755886)에 따른 최소 독립 구현입니다. **새 판단 코드의 실제 LLM 실행·검증은 미완료이며, 사용자 지정에 따라 PM 정이량이 이 Draft PR을 이어받아 진행합니다.**

현재 원격 main `07be0aa3fe42eb023b05b3b69016ef8f57777ca2`에는 round2 인수 문서/실제 실행 원본/RevisionSession이 없습니다. 이 부분 PR은 원본 게시를 기다리는 동안 한 실행의 두 수정 경로가 공유할 예산 객체와 연결 설계를 준비합니다. PlanningAgent/RevisionSession에 자동 연결하거나 실제 의미 문제를 해결한 상태는 아닙니다. PM이 인수 중인 원본 해시/이전 결정 잔류 수정을 재작성하지 않습니다.

`CorrectionBudget`은 한 run의 코드 소유자가 한 번 생성합니다. 단계 재실행과 수정 Skill 세션에 **같은 객체**를 넘깁니다. claim은 모델 호출 전에 회차를 한 번 소비하고 실패 시에도 반환하지 않습니다. 이전 회차 재전송·허용되지 않은 경로·종료 후 호출·동시 요청은 새로운 수정 권한을 만들지 못합니다. 정상 생성과 semantic_review는 수정 시도가 아니며 예산을 소비하지 않습니다. 이 객체는 모델/도구를 호출하거나 Skill을 설치하지 않습니다.

후속 연결에서 지킬 순서는 다음과 같습니다.

1. 최신 PM main/인수 기록/원 실행을 반영한 뒤 run 시작에 budget을 만들고 session을 한 번 설치합니다. model/pin/store/context는 기존 세션 경계를 유지합니다.
2. 재검토할 수 있는 유효한 이전 분석이 없는 초기 생성 오류는 기존 해당 단계 재실행을 사용합니다. 이 경로도 budget.claim(stage_retry)로 회차를 소비합니다.
3. 유효한 이전 분석의 수정은 review_revision callback을 사용합니다. Session의 별도 `_count += 1`과 Agent의 별도 `payload += 1`을 두지 않고 budget.claim(review_revision)의 반환값을 유일한 실제 회차로 사용합니다. Session을 수정마다 재생성하지 않습니다.
4. 실패한 수정 응답도 같은 budget의 회차를 사용합니다. Session snapshot·Agent input/output/decision·모든 모델 호출/trace를 같은 실제 회차로 기록합니다. 다음 시도는 원문/Scope/설정과 가장 최근 유효한 이전 분석을 재검사합니다.
5. 수정이 성공해도 CORE001 검사를 거쳐 별도 semantic_review로 다시 검토합니다. 위반이 남고 회차2이면 후보 없이 미해결 종료합니다. 질문/근거 불확실 보류·pin/연결/실행 정책 실패는 전체 budget을 닫고 이전 accept 결정을 현재 결과로 남기지 않습니다. 이미 소비된2회에서 마지막 검토·종료 처리는 실행할 수 있지만 추가 claim은 불가능합니다.

현재 예산 객체만으로 두 수정 경로에 자동 연결되는 것은 아닙니다. 아래 항목은 후속 코드/검수 조건입니다.

- 초기 오류 stage retry→유효한 분석의 revision callback 합계2, 반대 순서, callback 실패→재시도2/추가 호출0, 같은 session 객체/동시 재전송.
- 수정 전후 original_input 보존·현재 input/output hash, 이전 accept 잔류 없음, callback의 원 응답/정확한 회차/semantic 재검토/거절 후보 보존.
- 지시문이 섞인 자료·잘못된 모델/버전·상충·모호한 제외 조건의 원 입력/원 출력. 충분한 정상 입력과 가설의 후속 검증을 의미 불확실 보류와 구분하되 근거 없는 accept나 사례별 정답을 하드코딩하지 않음.

독립 재현:

```text
uv run python -m unittest discover -s tests -p test_correction_budget.py -v
```

8개 검사는 실제 예산 객체의 혼합 경로/실패 소비/동시 재전송/원 회차 재개/종료/사본 변경/잘못된 입력을 검사합니다. 새 모델 호출은 없으며 실제 Agent/Session 통합·의미 품질·CORE002/003 Done 근거는 아닙니다. 다음 구현은 게시된 PM round2 기반에서 연결하고 PM이 실제 모델 재실행·검수·병합·통합을 이어받습니다.
