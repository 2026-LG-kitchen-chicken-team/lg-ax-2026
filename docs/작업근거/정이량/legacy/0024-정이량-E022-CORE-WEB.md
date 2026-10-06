<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 68301..70917 · 원문 행: 249..256

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
### 정이량-E022-CORE-WEB — 실제 병렬 착수·향후 연락처 반영 근거

- 2026-10-05 09:21:23 KST 관측. 고정 PR87 f49258f의 원 readiness SHA b8ef51863b70a2a60c3821932430bf565eb933caaa7add45654e30adad18729f와 승인 image sha256:36ad082dbccf05bc9cff7c4dc5766e9ab7ed8c42198b0b731cf3831c546aaaf0를 그대로 보호 경로에 복사했다. 독립 검수의 원runtime5개·entry 일치/CORE001 Done·Issue8 owner·비중첩 경로 확인과 실제 broker3gate=true 뒤 release했다. 원 model network probe=false는 실제 첫 생성에서 확인할 조건이다.
- 원 config 백업→새 SHA1997d3b63750723624541ea854f05cfa70dd99d2ecded1256b2f308ce0690710·readiness3계정·web/core2release를 적용했다. 보호된 core-start-config-receipt는 원 broker/journal/사용량 동일을 검사한 수신증이다. `core-web-start.json` SHAa7df79a1a8f35a6ccc598e7d2f33d9e68509c928122774556adf5e7f10779fba는 원 controller 조회·config receipt·broker state·recent journal의 해시를 연결하며, 원 조회는 C:/LGAX-state/jeongiryang/pm-production-20261005의 해당 timestamp 파일에 보존했다. Windows 줄바꿈을 포함한 실제 보관 bytes의 hash로 metadata를 보정했으며 공개 JSON은 Git과 같은 LF로 고정했다. 관측 내용은 바꾸지 않았고 원 decoded stdout hash도 correction에 보존했다.
- 직접 중앙 관측: global/4계정 ON, web auto-cbcaed…와 core auto-34edc… 모두 owner 일치·running/attempt1/generation1/중단 사유 없음·같은 d95b225 base다. 자동 PM의 core assign 실제 receipt SHA927688988d63d894685d47bb9db1c657fc6598738a1455559bfcdc92fad29631를 stdout에서 확인했다. Running/lease는 Worker 착수 증거이며 생성·검사·PR·제품 품질 완료는 아니다.
- 신진하 후속 안내의 실제 Gmail ID1a1096f4922b9490·SENT/From/To/Subject 대조는 private/runtime/data-readiness-followup-receipt.json이다. 수신자 열람은 미확인이다. 최길웅 향후 주소 변경은 직접 사용자 지시와 private contacts/contact-history에서 검증했고 기존 actual SENT/outbox는 바꾸지 않았다. 원 이메일·민감 데이터는 공유 근거에 넣지 않는다.
- 독립 동시성 감사는 실제 policy/worker/broker 코드와 별도 in-memory guard에 근거한다. disjoint 개발·stale merge 거부·최신base 수정 요청 허용을 지지하지만 자동 rebase/세PR 무재작업 인수·처리량 개선은 입증하지 않는다. 기존 web-only 최초 관측과 원 실패/예산은 덮어쓰지 않았고 원본 수신 전 data release/Done도 하지 않았다.


<!-- member-log:body:end -->
