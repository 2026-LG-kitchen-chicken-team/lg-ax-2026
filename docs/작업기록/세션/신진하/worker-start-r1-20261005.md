# 신진하 Worker 시작·원본 readiness 인계 — 2026-10-05 09:22 KST

- 담당: 신진하 / ginaginaring / Codex. Issue12, P2-DATA-001.
- 배정: [PM-20261005-DATA-START-R1](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5985706857).
- 상태: 실제 Worker 가동·중앙 ON 확인. 자기 승인 패킷 배정/첫 자동 제품 PR/PM 인수는 아직 미확인.
- 현재 사용자 직접 할 설정/로그인: 없음. 충전 연결을 유지한다.

## 사용자·PM 지시

사용자는 “메일 읽고 작업 진행해”라고 요청했고, Worker 시작 자동 승인 검토가 최초 OFF 요청과의 충돌을 이유로 거절한 뒤 “전체권한줬어”, “계속진행해 전체권한때문에 잠깐멈춘거야”로 이 배정의 실행을 승인했다. charging 질문에는 연결 완료를 직접 답했다. PM 작성자 jeongiryang과 원본 Issue 댓글5985706857을 인증된 GitHub API로 대조했다. GitHub 배정 알림 메일을 직접 읽었으며 다른 수신자의 메일 열람은 추정하지 않았다.

PM 지시 요약: 기존 로그인/state/등록을 보존하고 Worker를 시작한다. 기존 원본 readiness를 비밀 검사 후 자기 Issue에 인계한다. 중앙 팀/개인 ON은 PM이 담당한다. data-document-store-frozen-snapshot은 PM 고정 패킷 수신 후에만 실행한다. 임의 큐·policy·공통 계약을 만들지 않는다.

## AI 해석·실제 수행

최초 초기 설정/OFF 보고 이후 새 시작 배정을 적용했다. 최신 main `a0141b60678916986f84c0965c3e4846ee9a7a80`과 기존 runtime `12f5a920d2170113f08f2f806fada5070d3acb4d`의 Worker5개/report3개 파일은 동일하고 실제 배포 해시도 일치한다. 로그인·Docker image를 다시 만들지 않았다.

Windows 앱의 짧은 AppData 경로는 실제 Limited 예약 작업에서 읽히지 않았다. 동일 CPython3.11.17/hash의 물리 경로와 ssl/sqlite3 import는 exit0로 확인했다. 설정의 경로만 실제 동일 파일 경로로 보정했고 토큰/AI/GitHub 인증 원문은 복사하지 않았다. 원래 state/token/profile은 보존했다.

실패·복구: 배터리로 첫 임시 probe가 Queued라 중단·제거했다. 사용자 충전 연결 뒤 실제 AC를 확인했다. 새 래퍼의 CONFIG 치환 SyntaxError를 수정하고 compile 확인을 추가했다. probe가 쓰는 로그를 읽는 공유 모드 문제는 완료 뒤 읽도록 수정했다. 사전 점검은 실제 Limited/Interactive task에서 exit0, 본인 GitHub·컨테이너 인증·중앙 연결 PASS이며 모델/claim0이었다. 임시 task는 모두 제거했다. 설치 호환 선언만으로 성공 처리하지 않았다.

기존 `LGAX-Worker-ginaginaring`의 action 경로만 보정하고 Limited·Interactive·전원 조건을 유지하여 시작했다. 실제 PID `27432`, task Running, 중앙 claim 요청을 관찰했다. PM의 중앙 팀/본인 ON을 조회했고 이 세션이 스위치를 전환하지 않았다. 큐의 다른 담당 작업을 대신 실행하지 않았다.

## 검증·근거

- 원본 readiness SHA256 `3331968c11930ba0567a9a9148ffe55a2603b47927e44124c2305796b8796a1b`. JSON bytes를 그대로 보존했고 인증/토큰/메일 주소가 없다. collector 문자열 자체를 PM 인수 증거로 사용하지 않는다.
- 본 PC 실제 image `sha256:1bdbf6c2dd816f852d816d12e219ee1326febfa11d3f0f52d5eb1f6cc598bde3`. 모델/검사 uid1000·root read-only·cap drop·no-new-privileges, 게시 canary 접근 거부. validator network none·AI profile도 미제공.
- [원본 readiness](../../../../evals/pm-preparation/20261005/ginaginaring-readiness.json), [실제 시작 manifest](../../../../evals/team-automation/20261005/ginaginaring-start-r1.json), [상세 근거](../../../../docs/작업근거/세션/신진하/worker-start-r1-20261005.md).
- 설치/로그인/canary/가동을 실제 제품 모델 수정·검사·PR/Project ACCEPTED나 독립 PM 인수로 확대하지 않는다.

## 남은 일·인계

PM이 원본 JSON을 checkout 밖 protected readiness 위치로 직접 인수하고 계정별 exact image pin `sha256:1bdbf6c2dd816f852d816d12e219ee1326febfa11d3f0f52d5eb1f6cc598bde3`을 검토해야 한다. 기존 의존/열린 PR 충돌 확인 뒤 첫 data capability를 release하고 고정 패킷을 배정한다. 본 Worker는 그 패킷 안에서 모델 개발→인증 없는 검사→자기 PR→Project 보고를 수행한다. 지금 자기 job count는 0. 부모 Done·팀 참가작 완성은 미검증이다.

이 기록/근거/원본을 같은 commit으로 공유한 뒤 고정 report hook으로 doing 자기보고와 실제 ACCEPTED를 확인한다. 이 문서 작성 시점에는 아직 그 보고를 전송하지 않았다. 이후 실제 수신증은 로컬 고정 receipt와 사용자 결과 보고에 연결한다.

## 새 PM 안내 대조

[운영 Issue28의 후속 안내](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-5986026645)를 메일로 읽었다. 신진하는 기존 원 readiness를 PR 또는 비공개 메일로 넘겨 PM이 data 인수를 열도록 요청받았다. 새 로그인/canary 재실행 요청은 아니다. 해당 요청에 따라 원 bytes와 시작 근거를 자기 인계 PR로 공개하고 부모 Done으로 표시하지 않는다.

Git의 JSON 기본 LF 정규화 때문에 첫 로컬 commit의 원파일 hash 대조가 실패해 push를 중단했다. 기존 `evals/pm-preparation/** -text` 규칙이 적용되는 불변 근거 경로에 원본 bytes를 그대로 보존했으며, 별도의 공통 Git 속성/정책을 변경하지 않았다. 이전 unpublished commit은 이력으로 남겼다. 최신 조회 main `d95b225029171fec71fe50fcbcd66a65d849914d`와 runtime 파일이 동일함을 대조했다.
