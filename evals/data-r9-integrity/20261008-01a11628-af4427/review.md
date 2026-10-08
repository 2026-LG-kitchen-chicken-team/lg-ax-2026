# 메일 요청 인수 현황과 DATA 잔여

기준: main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`, 2026-10-08 KST. 담당 신진하(`ginaginaring`). 이 단위는 기존 검수의 재사용 조건과 남은 인수를 확인한다. 전체 메일 업무는 아직 완료되지 않았다.

## 끝난 범위와 남은 범위

| 항목 | 실제 확인 | 남은 인수 / 담당 |
|---|---|---|
| 후기·분할·R9 원문 | PR246의238건 감사 재사용, PR266의184 Source·개발141·관리14·참고5 검수 병합 | 구매 SKU/게시일 미확인은 유지. 새 근거가 있을 때만 DATA가 보완 |
| FR01 | 기존225행·11질문 재채점 파일의 승인 상태·원바이트 유지 | 반복 불필요. 무Gold4 의미 응답은 별도 기존 출력 인수 |
| input-only | 원ZIP11,106bytes/11항목 및 metadata의 현재 SHA가 기존 발신 검증과 동일 | PM 전달 경로 확정 → DATA 원ZIP 전달 → CORE 실제 수신증 → DATA 대조 |
| 같은 입력 비교 | Agent/일반 LLM 원출력·실패/재시도/전체 usage 미수신 | 기존 실행 담당/PM이 해당 입력 SHA의 기존 결과 또는 미생성 상태 회신 |
| 운영 API/MCP·저장/복원 | PR267의 기존48항목 대조 재사용. PM의 실제 운영 보고와 생성기 ZIP 수신은 존재 | 실제 전송 envelope·저장 원본·같은 DB행·기존 재시작 전후쌍은 DATA 미수신. PM export 후 대조 |
| 표 자동 연결 | 수동5셀·각주1·Evidence3의 CORE 수신 완료. 원 sidecar SHA 유지 | 실제 자동 graph·승인 adapter·CORE 입력 수신을 기존 DATA 표 담당 창이 검수 |
| 후기 주제/의견 | 개발141 초안의 WEB/CORE 파일 수신·무결성 확인 완료. 원 파일SHA 유지 | PM 분류 승인 또는 수정할 원ID → 담당 DATA 수정 → WEB 같은 승인판 적용 |

파일 준비, 상대의 실제 수신, 운영 적용, 의미 검수, PM 승인을 [intake-status.json](intake-status.json)의 각 열로 분리했다. 미수신과 실제 실패를 혼동하지 않는다.

## 이번에 진행한 일

- 관련 본인 메일·원 댓글·온라인 Project·수동 큐·PR 상태를 확인했다. PR267의 고정 head `3219307c72a0d190ed95f1b279c14350b02ccda2`에서 CI4건 성공을 확인했다. OPEN/PM 검수 대기다.
- 기존 감사/재채점/수동 표/분류 원문5파일의 SHA와 Git blob/checkout 바이트 일치를 확인했다. 기존238건·873항목·225행·수동표 전체 검사는 반복하지 않았다.
- 현재 private outbox의 ZIP 및 metadata만 해시 대조했다. Gold·답안·방식키는 읽거나 보내지 않았다. `cases.json`은 ZIP 내부 manifest이며 outbox의 별도 `manifest.json`이 아니다.
- 작업 중 다른 DATA 창의 `DATA-PM-COORD-20261008-01a1100e` 조율을 확인했다. [ZIP 경로 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6049909352), [운영 export·PR267 검수 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/267#issuecomment-6049909890), 09:55 KST 메일의 SENT를 실제 확인했다. 이 창이 발송한 것으로 쓰지 않았으며 중복 발신하지 않았다. 발송은 PM의 열람·회신·승인이 아니다.
- [remaining-acceptance.json](remaining-acceptance.json)에 전달·자동 표·분류·기존 비교 결과의 구체 인수 항목을 고정했다. PR267의 운영 export7항목은 고정 commit 링크로 재사용한다.

## DATA 역할에서 아직 부족한 결과

1. **전달 완료 증명:** 준비된 ZIP은 있으나 상대 PC가 실제 받은 파일의 SHA/크기/목록이 없다. DATA의 전달 후 확인까지 남아 있고, 시작 조건은 PM의 기존 승인 연결 확정이다.
2. **자동 처리 검증:** 수동으로 맞춘 셀·각주 관계를 실제 자동 출력과 비교한 결과가 없다. R9의 기획 근거 관계 그래프는 PDF 표 자동 추출 증거가 아니다. 생산 담당/adapter 승인 없이 다른 창의 구현을 가져오지 않는다.
3. **실제 운영에서 원문 보존 확인:** source-only 검사와 PM 보고를 넘어 같은 실제 HTTP/MCP/run/DB를 직접 대조할 원본이 필요하다. 새 실행을 요구하지 않는다.
4. **승인된 분류와 효과 측정:** 초안 인계는 끝났지만 의미 승인·같은 버전의 실제 화면 인수와 독립 비교는 남았다. 날짜 미상141건으로 월/계절 추세를 만들 수 없으며, 사용량·공수 절감률은 미측정으로 둔다.

주체·희망/경험·시간 왜곡을 고치는 CORE 구현, 공통 계약·API·운영 서버, PM 최종 승인은 DATA 단독 편집 범위가 아니다. DATA는 고정 원문·반례·무결성 검수와 수신 대조를 맡는다.

## 다음 순서

1. PM의 기존 경로·운영 export 회신을 받으면 해당 파일만 검수한다. 미확보 pre-restart 원본을 새 재시작으로 대체하지 않는다.
2. PM은 자동 표 생산/adapter 담당과 고정 버전, 분류 승인 버전 또는 수정할 원ID를 지정한다. 기존 수신 완료 파일은 재전송하지 않는다.
3. DATA는 수신과 의미 검수를 기록하고, CORE/WEB은 실제 소비 결과를 회신한다. PM이 부분 인수와 부모 완료를 판단한다.

이 시점에 사용자가 직접 검사나 모델 실행을 할 일은 없다. 팀의 경로 결정·기존 파일 인계·승인이 아직 필요하다. 이 PR은 위 전체 업무의 완료 선언이 아니다.

## 근거와 한계

[메일·댓글·PR 근거](source-receipts.json) · [현재 발신 핀](sender-current.json) · [재사용 검증](reuse-verification.json).

CORE의 디스크나 PM의 비공개 운영 DB에 직접 접근하지 않았다. 확인하지 못한 외부 전달은 알 수 없다. GitHub 댓글 새로고침1회 연결 중단은 기록했고, 메일에 연결된 정확한 두 댓글을 재조회해 회복했다. 새 모델/OCR/수집/서버 재시작/자동화ON/생산 파일 변경은 0이다.

## 실제 게시와 동시 작업 인수

- [PR272](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/272)를 게시하고 PM 검수를 요청했다. [#234 인계 댓글](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6049997210)을 인증 계정으로 게시한 뒤 본문 일치를 재조회했다. 요청 게시만 확인했으며 상대 읽기/회신/승인은 아직 확인하지 못했다.
- 게시 중 발견한 [PR269](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/269) `2672f00b2a9ac5bad38e7b523f67e2814d0ec144`의 본문·파일목록을 읽었다. 기존 DATA 표 담당 창의6참고Source·14anchor 및 최신2run 보고 인수이며 실제 원출력/자동표/ZIP 수신은 여전히 미완료라고 명시한다. 이 창에서 검사를 반복하지 않는다.
- [PR270](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/270) `33b6312721c79f234f035fbe408f7d570fa6c36d`의 본문·파일목록도 확인했다. 15모델 적용범위/공식FAQ/새 날짜 관측의 별도 reference이고 원238/개발141과 draft를 유지한다. 표시일 관측을 게시일 확정으로 바꾸지 않으며 운영 bundle에 미등록이다. 이 두 PR은 OPEN으로, 이 창이 원자료 검사를 새로 수행하거나 PM 인수를 대신하지 않았다.
