<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 29837..32608 · 원문 행: 115..125

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 정이량-E034-TEAM-DISPATCH — 새 DATA 증거 인수·실제 팀 배정 확인

- 실제 CI 실패/정정: PR134 sourcef876063의 PR Python은1164검사/3skip 중 고정 head 검사 뒤 TemporaryDirectory 정리 Errno39 objects 한 오류로 실패했다. push Python 성공과 실패를 구분하며 원 로그 private/runtime/pr134-ci-first-failure.log를 보존한다. 직접 Worker fetch callback에는 per-command gc/maintenance 설정이 적용되지 않았으므로 임시 fixture 저장소 local 설정 두 개만 추가한 독립4행 commit9986a89를 인수했다. 별도 Worker47·실제 반복 fetch/cleanup40 PASS를 대조했고 실 운영 소스/설정은 변경하지 않는다. 새 commit의 CI 결과는 후속 근거로 남긴다.

- 확인 기준: 2026-10-05 22:19 KST 중앙/고정 실행기/실제 PR 조회. 공개 관측 continuous-team-r8-worker-r7-recovery.json에는 실제 승인 main089ab16·전원 ON·원 job 상태와 아직 완료되지 않은 범위를 기록한다. 관측 후의 상태는 재조회해야 한다.
- DATA 원본: 인증된 ginaginaring Issue12 댓글5994111929의 원 증거 SHA45b6a8d97be8e0b531476c05df1e972ab32b7414a8a0ab0a01cd0ded25142db3와 PR133 exactheadf66af019의 원 Git 복구 기록을 대조했다. 승인 이미지·모델/validator canary 읽기 거부·publisher 정상 동작·로그인/preflight·신선도 등14조건을 확인했다. PM이 다른 PC의 검사를 직접 재실행한 증거는 아니며 담당자의 인증된 원 검사로 구분한다.
- 실제 보호된 적용: 새 config SHAd6f2616ab3a8988983b64e8c22af1f44bbb540943ac081f412a64a6b5bbade0c. 정책/원 저널·비용·모든 jobs/ON과 현재 수동 예약을 보존하며 정확한 11 DATA 보류만 제거했다. 고정 런처에서 config/DATA proof 두 핀만 변경했고 동일 R8 PM 재시작 Running을 확인했다. WEB 10보류는 해제하지 않았다. 변경 전/후 원본·완전 제거 항목·잠금·실제 수신증은 비공개에 보존한다.
- 실제 배정: CORE auto-de46e545/base089ab16→PR139/head202571823c587b02a90c42396d4060565540ef5e·CI4 PASS. 앞선 revision_product_bound 거절과 이전136 검수 실패는 보존한다. DATA/WEB 인계 Issue 댓글5994894045/5994897309·배정 JSON·실제 발송/메일 SENT 재조회를 확인했다. 주소/내부 메일 ID·자격증명은 비공개에만 있다. DATA 활성 수동 작업·WEB 복구 성공/실제 claim·CORE 병합은 별도 후속 증거를 요구한다.
- 도구 검증: test_assign_task25 PASS. 공개 notification/Issue에는 내부 메일 ID가 없고 비공개 receipt/outbox에는 실제 수신증이 유지되는 회귀를 검증했다. 배정 도구 성공이 수신자 열람/실행 완료를 증명하지 않는다.



<!-- member-log:body:end -->
