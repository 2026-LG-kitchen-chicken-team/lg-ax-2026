# 신진하 Worker 시작 근거 — 2026-10-05 09:22 KST

- 관련 작업기록: [worker-start-r1-20261005](../../../../docs/작업기록/세션/신진하/worker-start-r1-20261005.md). 담당 신진하.
- 출처: 사용자 직접 시작 승인, PM 인증 배정 댓글, 실제 Limited task/PID, 고정 원본 Docker readiness. 모의 응답이나 다른 PC 결과를 사용하지 않았다.
- 고정 source main `a0141b60678916986f84c0965c3e4846ee9a7a80`, runtime `12f5a920d2170113f08f2f806fada5070d3acb4d`. 해시 일치와 관측 요약은 [manifest](../../../../evals/team-automation/20261005/ginaginaring-start-r1.json).
- [원본 readiness JSON](../../../../evals/pm-preparation/20261005/ginaginaring-readiness.json) SHA256 `3331968c11930ba0567a9a9148ffe55a2603b47927e44124c2305796b8796a1b`. 원본 bytes 그대로이며 secret/contact scan PASS. 검증 시각(UTC epoch): `1791156360.221763`.
- image `sha256:1bdbf6c2dd816f852d816d12e219ee1326febfa11d3f0f52d5eb1f6cc598bde3`, 모델과 validator 관측 image 모두 일치. login 실제 selected Linux CLI ChatGPT 구독 PASS. publisher canary 거부/validator network none PASS. 실토큰을 canary로 사용하지 않았다.
- 실제 제한 권한 사전 점검: exit0, selected container auth·GitHub own identity·controller connected, model_executed=false/job_claimed=false.
- 실제 Worker: task `LGAX-Worker-ginaginaring` Running/Enabled/RunLevelLimited, PID `27432`, 현재 team `on`, own flag `True`. 실제 controller claim 관측 7회, 마지막 UTC `2026-10-05T00:21:50.340839+00:00`.
- 로그/토큰/private 원문은 Git에 포함하지 않았다. 개인 Windows 실제 경로는 실행 설정에서만 관리한다.
- 실패도 보존: 배터리 Queued·래퍼 치환 SyntaxError·probe log sharing·지원하지 않는 ScheduledTask Description 옵션. 복구 뒤 실제 사전 점검/시작으로 확인했다.
- 주장 범위: 이 PC의 설치·인증·Docker 경계·실제 Worker 가동/폴링. 지원하지 않는 주장: 유료 모델 생성·자동 제품 PR 게시·Project 보고 수신·PM readiness 인수·부모 Done·전체 구현. 해당 결과는 후속 실제 근거가 있어야 한다.

## 새 PM 안내 대조

[운영 Issue28의 후속 안내](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-5986026645)를 메일로 읽었다. 신진하는 기존 원 readiness를 PR 또는 비공개 메일로 넘겨 PM이 data 인수를 열도록 요청받았다. 새 로그인/canary 재실행 요청은 아니다. 해당 요청에 따라 원 bytes와 시작 근거를 자기 인계 PR로 공개하고 부모 Done으로 표시하지 않는다.

Git의 JSON 기본 LF 정규화 때문에 첫 로컬 commit의 원파일 hash 대조가 실패해 push를 중단했다. 기존 `evals/pm-preparation/** -text` 규칙이 적용되는 불변 근거 경로에 원본 bytes를 그대로 보존했으며, 별도의 공통 Git 속성/정책을 변경하지 않았다. 이전 unpublished commit은 이력으로 남겼다. 최신 조회 main `d95b225029171fec71fe50fcbcd66a65d849914d`와 runtime 파일이 동일함을 대조했다.
