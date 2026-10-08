# DATA-W2-01a1100e-756d07a2 — W2 새 수신 범위 검수

신진하(DATA), 2026-10-08 KST. 최신main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`, 별도 `codex/data-w2-01a1100e-756d07a2` 및 고유 폴더만 작성. PR278/280/282/288/290의 완료 검수와 인수는 재사용한다.

| 업무 | 확인된 범위 | 오류/상충·미확인 |
| --- | --- | --- |
| 자동 표2페이지 | 기존 DUE57/MW37 원PDF SHA 및 기존 전체렌더를 읽어 표 참조 확인. DFE845/815 조건열·DUE815, MW1000W*1/1570W·각주 보존 | 실제graph/cell/승인adapter 추가미수신 → 자동검증불가·정확도/오류수null. 역사적OCR-MW-TABLE-05의 *→∗ 오류는 재사용된 문자오류이며 새 자동셀 오류가 아님 |
| 후기·토픽 | 기존 관측239→고유238, 개발141/평가36/시연49/격리12 및 날짜미상141 제외를 metadata로 연결. 238=141+36+49+12, scope제외97=36+49+12 | topic141은draft/승인pin 미수신. 구매일·Q&A작성일은 게시일로 대입불가. 월/계절 분모0·승인분자/비율null, 후보 합산0 |
| SKU·소비 | 기존 구성품/모델/판본·Source ID를 확인·상충·미확인 경계로 연결. PM UI2의 새 revision-readback1605bytes/SHA78abaab…을 읽음 | SKU-F03/F04/M02 미확인 유지. 새run의선택6건수·묶음SHA·scope상속보고만 있고 실제Source ID값/본문판본 없음. runtime_keys는키목록, 개별26Source 소비는null |

[표 검수](table-review.json) · [날짜/집계](trend-review.json) · [SKU/새소비 근거](product-review.json).

새 인수 source: PM284 `b8ca6a7e953f0b2da483c40d5434210f50cf9277`/ `evals/pm-r9/20261008/chat-ui/live-revision-readback.json` /Git blob `ce586045758c5a4191ec322eebe902b54477c86e`, sourceSHA `78abaab48852a6fd4e7f450454c795aebe21b76d9276a472a7e415c62ce1093c`. producer manifest의 선언값과 실제파일 hash도 같다. `run-3a36b9b26f8746b295e33657e1353e65`·부모21d844는 새UI2이며 기존1f83/754268·5ccd/97dbc·동일7/noGold4와 구분한다. declared briefSHA는 원brief 파일 수신/계산으로 올리지 않는다.

W3에 실제 selected/processed IDs·source_facts·원문/판본 field와 pending26의기존소비캡처 요청을 전달했다. 원파일/메일/ZIP/DB는W3, 의미채점W1, Gold/분류승인은PM이다. 요청 자체를 수신/운영적용으로 처리하지 않는다.

중앙status17:24 예약0, 이후17:39 W3예약active를 공식조회했다. 기존W2/다른창 예약을 해제하거나 변경하지 않았다. W3→W1→W2 게시순서에 따라 현재 준비공간에서 검수하며, 앞창의실제게시/예약종료가 확인된 뒤 본인공식예약과게시를 진행한다. 자동화OFF, 새모델/OCR·225/11·과거완료검사·운영 API/DB/서버·메일0, 기존코드·자료·개인README·타창파일수정0.

## 게시 차례 확인

W3 PR291/1810297a와W1 PR292/2af0601c의게시·자기예약해제 후중앙목록0을직접조회했고, W2본인예약 manual-data-w2-01a1100e-756d07a2만 reserved=true를수신했다. 이전대기기록은그시점의관측으로보존한다. 다른예약변경0.

최신CORE292/6056753310이변경97dbc전체원응답(7425bytes/SHAe008c91f…)의기존위치를확인했다. 이원파일인수/필드인계는W3에추가로전달했고, 새UI2 run3a36/parent21d844의Source값미수신과구분한다. 기존변경15필드대기보고를전역미생성으로해석하지 않는다.
