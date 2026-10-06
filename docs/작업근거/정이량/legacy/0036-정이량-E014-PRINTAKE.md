<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 103611..106815 · 원문 행: 395..407

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 정이량-E014-PRINTAKE — 고정 PR 인수·실제 판단 저장·의미 검수

- 기록: 정이량-20261005-001-PRINTAKE / 확인일 2026-10-05 KST / actual GitHub PM·live_model·real HTTP/TypeScript·MCP SDK·fixture/규칙 검사를 구분한다.
- PR 및 merge: #51 c7adfbdb, #48 e5d4a099, #52 cd3044f7. GitHub 직접 조회 및 원본 owner head/해시를 인수했다. CORE001 원본 individual은 SHA256 `e3a02a3efcfd556bbf2cd22dbc491b0b8120e2e01878d434f6bf9d8becc089b0`, PM 수신증과 계약/6+6 실제 통합 근거는 `harness/phase2/runs/pm-core001-intake-20261005/`다.
- 실제 모델 입력: `evals/core-planning/examples/{dataset,fridge.input,fridge-changed.input}.json`의 합성 개발 예시. 모델 qwen3:8b/Q4_K_M digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`. 서버 기존 모델만 사용했고 GPU/디스크/서비스를 읽기 조회했다. 비밀·자격증명은 private에만 있다.
- 원본 실패/성공 인덱스: [model-runs.json](../../../../evals/pm-integration/20261005/model-runs.json). 초기 실패 bd82744, prompt2 f6e9c4a(0후보), prompt3 40bb51f(실패9호출), prompt4-thinking 4c7d0c5(출력잘림). 모든 원본 응답/trace/metadata를 그대로 남겼다. 모델 digest·예산·thinking 조건 차이는 동일 조건 성능 비교가 아니다.
- 실연결: [workspace-live.json](../../../../evals/pm-integration/20261005/workspace-live.json), [summary](../../../../evals/pm-integration/20261005/workspace-live-summary.json), web-live-test.txt. 실행 코드56cfcb1, `npm exec -- vitest run src/livePlanning.test.ts`(opt-in true) 실제 client→API18879→모델→새 snapshot 두 개. 정상 run-743b67de262246df95314b4017dd1684 / 변경 run-2c4925b9660b410ebea335276a7b177a. MCP 7도구 발견·각 snapshot 동일·원 실행 불변 확인.
- 반대 근거: [semantic-review.json](../../../../evals/pm-integration/20261005/semantic-review.json)의 raw hash·원 제외 조건·CON-002·독립 검사. 실제 변경 응답은 자동 세척을 제안했는데 deterministic contract가 accept했다. 입력 전달 누락이 아니라 의미 검사의 공백이다. 기획 작동 방식·실현성·에너지/효과 목표도 검증 전이다. 이 증거는 연결 성공을 지지하나 조건 준수·Agent 전체 성공·수상 우위/사용자효용·31요구 완료를 지지하지 않는다.
- 자동 검사: checks.json(56cfcb1, Python372/계약/하네스/두 지침/서버6/MCP/모델manifest); 이후 blanktrace/web adapter 변경은 final-checks/checks.json의 별도 tested_commit과 결과를 따른다. fixture 통과/웹 표시 검사는 실제 판단 품질과 다르다.
- 코드/원본 해시·검사 로그는 파일의 외부 JSON 인덱스로 연결하며 자기 문서 해시를 자기 문서에 쓰지 않는다. PR head→CI→actual squash main→검사/승인 sync 상태는 후속 종료 checkpoint에서 대조한다.
- 재개: docs/pm/pr-intake-20261005.md와 workspace-planning.md, PM 현재배정, CORE002/003·WEB003·DATA001 Issue를 읽는다. 새 배정 이메일은 실제 Gmail SENT 대조 뒤에만 발송 완료로 기록한다. 참가작 Agent 핵심 요구 완료·최종 제출은 미완료다.



<!-- member-log:body:end -->
