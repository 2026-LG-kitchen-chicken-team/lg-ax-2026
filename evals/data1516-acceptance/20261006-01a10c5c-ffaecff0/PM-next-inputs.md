# #15·#16 다음 인수에 필요한 입력

DATA가 준비·검증한 결과이며 PM 결정/실운영 응답을 대신 만들지 않았다.

|범위|필요한 PM 인계|DATA가 이어서 할 검사|
|---|---|---|
|#15|공개 중복8입력의 진단용 보존 또는 미노출 교체 결정과 근거 링크|독립성 표시·자료 버전·노출 기록 유지. 진단 자료를 독립 평가로 승격하지 않음|
|#15|결과 작성/개발과 독립된 검토자, 승인 비공개 수신 경로·수신증 방법|입력 전용 ZIP과 PM/CORE 검토 전용 ZIP의 SHA 대조 및 실제 수신 기록. 답안/방식키를 모델 입력으로 보내지 않음|
|#16·148|선택한 원/PM/DATA 팩, 날짜/주제 승인 버전·근거, source/annotation/date-source 파일 핀|원36 undated/PM31 dated+5 unknown/DATA9 dated+27 unknown 구분|
|#16·148|승인된 실제 운영 project snapshot·동일 query의 API/MCP aggregate·당시 원문 전페이지|모델/문서/자료/annotation 버전·분모/분자·근거 IDs·원문 일치|
|#16·148|같은 운영 project/aggregate의 저장 snapshot 및 재개 이후 aggregate·snapshot|전체 `memberships.__all__`와 분모 모든 원문·metadata 보존|
|#16·148 오류|실패 요청별 실제 HTTP 상태·오류 코드/응답|5xx를 타당한 입력 거절로 세지 않음|

실제 운영 원문/DB에는 개인정보가 있을 수 있다. 원 capture·토큰·주소·비공개 원문은 승인 private 경로에서 보존하고, 일반 PR에는 안전한 요약/파일 해시만 연결한다. 위 목록은 새 운영 주입·재시작·배포 지시가 아니다. WEB의 실제 차트/원문/내보내기는 최길웅 담당이며 DATA 정합 검수와 분리한다.
