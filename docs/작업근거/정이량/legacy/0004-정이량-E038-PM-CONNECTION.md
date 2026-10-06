<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 7153..9496 · 원문 행: 26..38

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 정이량-E038-PM-CONNECTION — 공통 연결 구현 착수

- 검사 수신증의 비밀 없는 투영은 `evals/pm-intake/20261006/trends/verification.json`이다. 새 제품 검사/SDK 실행은 인증 없는 Docker의 source byte 복사본에서 수행했다. 전체1345(3 skip)·관련87·웹433+4/빌드·계약/phase2/역사 하네스/지침·lint 통과와 독립 읽기 검수를 확인했다. 실제 PR156/main CI·병합·공식 수신은 운영 Issue28/PR156의 후속 checkpoint에서 확인한다.
- 초기 실패(오타·새 오류 안내·fixture/SDK 경로·기대 오류·격리 실행 문맥 부족)와 수정은 `private/runtime/pm-connection-20261006/` 원 로그/수신증에 보존한다. bundle 평문 Git 객체만 격리 이력 검사에 제공했고 PM Git config/hooks/인증·연락처·프로필을 복사하지 않았다. source_changed=[]·model_calls=0·실제 mount 경계를 확인했다.
- 최종 독립 읽기 검수는 `/root/pr_data_triage`이며 표본경고·annotation 순서 충돌 보완 뒤 차단 결함 없음이다. 외부 호스트 실호출·제조/수요·운영 집계·Agent 품질 완료를 지지하지 않는다. DATA/WEB 인수 방법은 `docs/pm/review-trends-implementation-20261006.md`다.

- 원 지시와 해석은 정이량-20261006-003-PM-CONNECTION에 별도 기록했다. 2026-10-06 실제 GitHub 계정/main/열린 PR 읽기 확인 뒤 시작했다.
- 기준 소스: b477860b2612f51b7e81f37b635c05ba02338bfb. 확정 규격은 docs/pm/review-trends-contract-v1.md, 기존 권한·자료 scope는 WorkspaceStore와 private API/MCP를 재사용한다.
- 일정 근거: 현재 사용자 “10월7일 15시 컨설팅임”. 2026-10-07 15:00 KST로 적용하며 공식 메일/접속 URL/소요시간 직접 확인은 미완료다.
- 검증 계획: 계약 형식과 의미/근거 검사를 구분하며, 미연결 collector는 501 NOT_IMPLEMENTED. 임의 정상 숫자·고정 Agent 성공을 반환하지 않는다. 기존 raw data·독립 평가·원 모델 실패/비용/자동 queue는 보존한다.
- 제품 코드/저장소 검사 실행은 PM 자격증명이 없는 승인 Docker 환경을 사용한다. host에서 브랜치 제품 코드를 PM 권한으로 실행하지 않는다. 검사 수신증·고정 commit·실제 CI·통합 결과는 후속으로 추가한다.



<!-- member-log:body:end -->
