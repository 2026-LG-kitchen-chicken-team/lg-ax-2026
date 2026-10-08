# DATA-W3-01a10c5c-7f0e2b9a — 인계·운영 무결성 부분 인수

최신 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`의 배정과 기존 W3 기록을 읽고 **새 CORE W1/W2 부분 수신 기록**을 고정했다. W3는 비공개 전달·수신 무결성, 운영 결과 보존 대조, PM 연락만 맡는다. W1 의미 검수·W2 자료/표/분류는 각 창이 이어간다.

| 확인 대상 | 현재 확보한 근거 | 아직 미확인 |
|---|---|---|
| 기존 input-only ZIP | 현재 전체11,106bytes/SHA가 sender pin과 일치. 기존11-entry metadata 재사용 | PM 승인 경로/수신자·PC/읽기 범위, 실제 전달 및 수신 파일SHA |
| 정상·조건 R9 운영 결과 | 기존 R9-OPS-01..07 명세와 선언SHA, PM 보고/CORE 수신 범위 | 실제 저장 public JSON·wire·DB·동일DB 재시작 전후 |
| PR279 / W1 | CORE 고정head의 공개54파일 부분 인수 보고 | 두 raw JSON·동일7·무Gold4 실제AI답변·독립점수 |
| PR280 / W2 | CORE 고정head의 공개20파일 부분 인수 보고 | automatic graph/승인adapter·분류/날짜·구매SKU/당시판본 승인 |
| PR267 CI | 기존4job 실제success/steps13·13·17·17 | PM 인수·운영 적용/부모Done |
| PR279/280 CI | 8job failure, 실제steps0와 결제/지출 시작 제한 annotation | 실제 CI 실행·PM 인수·병합 |

- [ZIP 현재 인수표](archive-intake.json), [운영7항목 JSON](operating-intake.json), [운영 대조표](operating-intake.csv).
- [CORE 두 창 수신 근거](cross-window-receipts.json), [PR/CI 현재 관측](pr-state.json), [PM 요청·담당 연결](dependency-intake.csv).
- [기존 메일 요청 범위](mail-request-coverage.json), [정확 자료/댓글 pins](source-pins.json).

확인/상충/미확인을 분리한다. **새 수신 자료에서 확인된 파일 해시 상충은 없으며**, 부족한 운영/승인 증거는 미확인이다. 미확인은 FAIL이나 글로벌 미생성 판정이 아니다. 보고서/코드/수신 댓글/화면 검수가 실제 원 출력·ZIP 수신·독립성 승인·PM 인수로 바뀌지 않도록 근거 종류를 보존했다.

원 ZIP·private 입력·Gold·메일 주소/원문/IDs·자격정보는 Git에 넣지 않았다. 현재 ZIP 전체hash 확인만 수행했으며 이미 끝난11-entry 검사·225회·11문항·기존109HTTP/DB재시작 검사를 재실행하지 않았다. 모델/OCR·API/MCP 운영 probe·DB/서버/restart·자동화ON·결제/한도/workflow 변경0.

다음 하나: **PM의 기존 비공개 경로·수신자/PC·input-only 읽기 범위 결정을 받고 동일 원ZIP부터 전달·수신SHA를 대조한다.** Gold/전체raw/usage/자동표/최종채점은 이 전송의 추가 선행 조건이 아니다. 기존 원 운영 export나 첫 승인 필드는 도착한 해당 범위부터 인수한다.

2026-10-08 13:13:47 KST에 기존 PM 스레드로 새 CORE부분수신·PR279/280 CI·W3예약상태만1메일 보완 발송했다. SENT/같은스레드/검증수신자/제목/새본문 exact를 원메시지로 재조회했고 첨부0이다. [메일 수신증 요약](mail-delta-confirmation.json). 받은6sourcepins·4댓글body·운영7항목·9담당조건·12기존job의 격리자료audit와 AGENTS/CLAUDE 일치 PASS, 실제운영/모델품질 승인 아님. [검증근거](verification.json). [현재 예약 경계](coordination.json).

새 [W1 PR281·W2 PR282 후속 인계](followup-intake.json)도보존했다. source pin은초기6+새댓글2=8개이다. 두후속PR의8job도steps0·시작제한이며실제ZIP/운영원증빙수신을대신하지않는다.
