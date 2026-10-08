# DATA W2 변경분 검수 — DATA-W2-R2-01a10600-r2-a63f9d

기존PR288 설치Q&A 검수/CORE수신은 재사용하고, 새PR278 날짜·설명서 정정 및 PM284/WEB268의 기존 실행 기록만 대조했다. 원main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`·원자료/README·다른 창은 읽기 전용이다.

- [후기 날짜 JSON](date-role-inspection.json) · [CSV](date-role-inspection.csv): 원ID6/본문SHA·구매일자 직접확인. kimchi 현재HTML SHA는 producer와 달라 새capture/locator를 보존, 본문SHA6은같음. 게시일/구매SKU/구매당시판본null·시간분모0·ratio null.
- [공용 설명서 설치 범위](manual-installation-scope.json): 기존2PDF SHA 그대로, 새정정2주장에 해당하는3페이지만 native text+기존render 대조. K10cm/2.5cm의 대상 및 sensor종속설명, O p4 built-in예외/p11장식문·결로 분리. 예외/센서 exactSKU 존재·개별설치·2024구매판은 미확인.
- [실제 소비 기록](source-consumption-inspection.json) · [source metadata CSV](runtime-source-metadata.csv): PM신규4run은 frozen DUE6선택ID SHA와 일치. WEB 새냉장고1원JSON의 선택6/실제result canonicalSHA와 main58-source 묶음SHA를 대조. 모델·판본·locator·원문SHA는 frozen pack join이며 실제SourceFact/원prompt에 들어있다고 주장하지 않는다. pending26은 받은ID집합에없지만 다른run전체소비는미확인.
- [자동 표 인수](automatic-table-intake.json) · [승인/분모 경계](approval-intake.json): graph/승인adapter·분류pin 추가미수신, 자동성능null. PMsource해시/AI관계graph/수동표로 자동출력을 대신하지 않는다.
- [고정 입력](input-pins.json) · [추출/환경/원실패](source-extraction-record.json) · [확인/상충/미확인](findings.json).

새검사는 이번수신/인용/버전 경계만 offline에서 수행한다. 기존238/141·80/84/12/29/1101/53·225회/11문항·100쪽·기존HTTP/DB/모델평가 재실행0. 원review/문서·HTML·이미지·model reply 전문/Gold/ZIP을 공개하지 않는다. 새모델/OCR/설치·운영API/DB/재시작·메일·자동화ON0. 실제모델콜/반례생성/의미검수는 해당원작성자 보고이며 이번실행0.

현재 미확인 범위: 실제automatic graph+승인adapter의첫2페이지, 승인topic/지적SourceID·유효게시일, 정확구매SKU/당시판본·pending26의다른실제소비receipt. PM인수/CI/병합/부모Done은별도다.

사용자 요청에 따라 내부 작업목록 문서·링크를 현재 PR에서 제외했다. 원자료 검수 결과와 미확인 항목은 보존했다.
