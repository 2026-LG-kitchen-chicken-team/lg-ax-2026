# LGAX 운영 자료·집계·최종 출력 대조

- 담당: 신진하 / ginaginaring. 사용자 직접 실행·PR 게시 지시.
- 작성 시각: 2026-10-07T00:52:19.210253+09:00. 기준 main: `9cd2d56be52588764c18c109c9ffca4c104bd48c`.
- 새 폴더: `evals/data-operation-audit/20261007T002145-01a10f51`.
- 본문은 고정 자료와 보존 응답 검수 결과다. 승인 운영 자료 응답과 최신 코드의 세 제품 결과는 수신하지 못했다.

## 검수 결과

|범위|확인 결과|남은 부분|
|---|---|---|
|#12·#13 고정 원문|PR196 원7파일이 현재 main과 동일. 근거/리뷰 메타177행의 ID·모델·자료 성격·문서 버전·원문UTF-8 해시·위치 일치. 원PDF3의 보존 바이트 해시 일치.|실제 운영 public/workspace 응답177행은 미확인.|
|#16·148 집계|PR194 보존15질의와108리뷰 연결을 원 고정 자료에서 재계산. 분모·분자·날짜 제외·원문ID 일치.|운영팩 최종 선택·주입·동일 허용 범위의 실제 운영 응답 미확인.|
|WEB 인계|PR186 API/MCP·화면·JSON·Markdown 인계의 같은 aggregate/자료해시·청소006 연결 일치. 보존 그림에서도4건/제외1·5/청소25% 확인.|시험 주입 결과. 이번 새 브라우저 검증·운영 배포 확인은 없음.|
|R06|과거 공개 리뷰 발췌 팩의 냉장고·식기세척기 출력 신원 연결 일치. 식기세척기 반복 결과도 확인.|전자레인지는 최종 출력 없음. 최신 PR190/운영 세 제품 결과는 미확인.|
|R07|과거4실행의 기록된 재현 결과와 원 입력·출력·상태가 일치. 모델 요청/응답만 주입하는 runner와 입력변경 거절 수신증 확인.|새 재현 실행0. 과거 보류·실패 재현은 현재 모델 품질·정상 완주 증거가 아님.|
|R08|과거 세 제품은 failed/held/failed이며 모든 당시 r08_acceptance=false.|최신 고정 코드에서 판단·적절한 보류·질문·미상 정보·기능 근거를 만족하는 세 제품 결과 필요.|

## 자료 범위 정정

현재 인수된 `lg-manual-scope-20261006.3-pm-intake` 설명서 팩의 실제 제품 리뷰는0건이다.
별도 보존한 `lg-docs-and-review-excerpts-20261006.1` 팩에는 LG 제품 페이지 발췌가 제품별1건씩, 총3건 존재한다.
원CSV·발췌문SHA와 기존 출처 위치를 검수했다. 구매자 신원과 원HTML 전체를 이번에 재검증한 것은 아니며,
이 팩을 현재 PM 승인 운영팩·독립 평가·최신 코드 품질의 완료 근거로 승계하지 않는다.
원36건과 DATA 날짜 시연은 합성 자료이고 구성 날짜다.

## 집계 자료팩

아래 날짜 수는 전체36건의 날짜 있음/미상이며,10월 결과는 FRIDGE-A만 선택한 값이다.

|팩|자료 버전|날짜 있음 / 미상|10월 청소 언급|
|---|---|---|---|
|original|0.1.0|0 / 36|분모 0 / 청소 0 / 비율 null|
|pm|pm-synthetic-trends.v1|31 / 5|분모 3 / 청소 1 / 비율 1/3|
|data|synthetic-dated-demo.20261006.v1|9 / 27|분모 4 / 청소 1 / 비율 1/4|

같은 청소 주제라도 PM001의1/3과 DATA006의1/4는 서로 다른 출처·자료 버전·원문 목록이다.
긍정 리뷰의 청소 언급을 포함하며 실제 고객 불만·수요 비율로 해석하지 않는다.
실제 프로젝트의 aggregate ID는 서버가 반환한 것을 사용한다. 이 시험 프로젝트의 ID를 운영에 재사용하지 않는다.

## 원 세 제품 결과

실행 코드 `b940a11245d7940f79662682e73527b8b3bafef1`의 보존 결과다.
새 PR190 head `28e4431`의 실모델 결과로 표시하지 않는다.

|사례|제품|상태|최종 출력|decision.valid|당시 위반|R06 범위|
|---|---|---|---|---|---|---|
|fridge|T876MEE1H1|failed|있음|False|SUPPORT_UNKNOWN · HOLD_WITHOUT_QUESTIONS|신원 연결 일치|
|dishwasher|DUE6BGL2E|held|있음|False|NO_CANDIDATE_VIOLATION · NO_CANDIDATE_UNCERTAIN|신원 연결 일치|
|microwave|MW23FDI|failed|없음|False|VALIDATION_FAILED|최종 출력 미확인|
|dishwasher-fresh-replay|DUE6BGL2E|held|있음|False|NO_CANDIDATE_UNCERTAIN|신원 연결 일치|

냉장고는 질문 없는 보류와 지원 미확인 위반을 남겼다. 식기세척기의 held 역시 decision.valid=false다.
전자레인지의 입력/빈 출력 재현 일치는 유효한 최종 분석 출력을 뜻하지 않는다.
CORE의 PR190 고정head84회귀 확인과 CI4/4는 별도 검수 수신증이며, 실제 세 제품 새 품질 검사로 집계하지 않는다.

## 해시와 판본

- 원문 해시: 정규화 없이 문자열을 UTF-8로 인코딩한 SHA256.
- 파일 해시: 고정 Git blob/원PDF의 바이트 SHA256.
- DemoDataset과 staging generated artifact의 canonical JSON 해시 영역을 구분한다.
  공식 설명서 staging 해시를 WorkspaceStore 실제 응답 해시로 추정하지 않는다.
- 합성 `MANUAL-006`의 근거 판본2.0과 제품 기본 판본1.0은 의도된 별도 기록이다.
  근거를1.0으로 덮지 않고 실제 응답의 원근거 판본과 대조한다.
- 보존된 리뷰+설명서 팩은 합친 판본 문자열을 사용한다. 현재 main의 개별 설명서 판본과 같은 scope로 취급하지 않는다.

## 실제 운영 미확인과 인계

PR196/200/190에 남은15GET의 과거 관측은 연결 오류·502다. 이번에 같은 미확인 주소를 재조회하지 않았다.
새 승인 endpoint/viewer 또는 비밀없는 운영snapshot이 발견되지 않아 운영 연결 수신 조건을 충족하지 못했다.
이는 현재 서버OFF나 자료 불일치의 판정이 아니다.

`operation-handoff-needed.json`에 PM이 인계할 최소 필드를 명시했다.
public과 workspace는 승인된 공통 허용 범위를 비교하며, 의도된 비공개 범위를 억지로 같게 만들지 않는다.
토큰·개인 인증·원시 비공개 모델 응답을 PR이나 Issue로 요청하거나 게시하지 않는다.

## 산출물과 재검수

|파일|내용|
|---|---|
|operation-record-comparison.csv|고정177행과 운영 미확인 상태|
|trend-comparison.csv|원·PM·DATA 팩의 보존15질의 재계산|
|final-output-source-comparison.csv|과거4실행의 원문·위치·판본·출력참조 여부|
|three-product-output-audit.json|과거 결과·현재 PR190 출력 미수신·리뷰 범위|
|WEB-handoff-comparison.json|WEB 인계/보존 그림의 해시와 범위|
|reproduction-evidence.json|고정 입력·코드·모델·설정·기록된 재현 연결|
|operation-history-consumed.json|새 조회와 구분한 과거 관측|
|operation-handoff-needed.json|운영/집계/최신3제품 결과 최소 인계|
|comparison-checks.json|이번 정적 대조의 항목별 기대·실제값|
|input-pins.json|소비한 고정 Git/local 파일의 바이트 해시|
|preservation.json|기존3148 tracked파일 보존|
|source-observation.json|PR·Project·팀 인계 조회 시점/상태|
|work-record.md|사용자 지시·수행·실패/미확인·다음 행동|
|audit-builder.py.txt|실제 수행한 자체 작성 오프라인 검수 코드; 저장소 코드 실행 없음|

모델/OCR 새 호출0, 운영 HTTP 새 조회0, 브라우저 새 실행0, 저장소 검사 suite 새 실행0.
이번 3003개 대조 항목의 불일치0은 고정 자료의 일치만 뜻한다.
기존 코드·자료·개인 README는 변경하지 않았다. 자동화·예약·비용·원 실패 기록 변경0.
Refs #12, #13, #16, #148. PR 검수·PM 인수·운영·부모Done은 별도다.
