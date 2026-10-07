# DATA16/148 개발 후기 주제·의견 초안 인계

담당 신진하, 고유ID `01a114f6`. 상태 **draft / PM 승인 전**.

## 고정 입력

- D1/D2 [PR254 고정 head94b560d](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/tree/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600).
- PM [PR245](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245) 병합 commit `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`의 기존 Schema·집계기. 생산/공통 파일을 편집하지 않았다.
- 원 데이터 버전 `r8-public-research.20261007.v1`, D1 manifest `lg-public-research.20261007.d1-01a10600.v1`.
- 새 annotation 버전 `r8-development-topic-draft.20261008.01a114f6.v1`.
- [source-pins.json](source-pins.json)에 고정 입력/실제로 import한 PM 코드65파일의 Git blob SHA와 commit이 있다.

|대상|원 고유ID 수|이번 처리|
|---|---:|---|
|development|141 = 냉장고48 + 식기세척기48 + 전자레인지45|원문을 읽어 draft annotation, 인용 범위, 양면/반례 작성|
|independent_evaluation|36|membership ID만 대조; 본문 분류/새 복사 없음|
|demonstration|49|membership ID만 대조; 본문 분류/새 복사 없음|
|quarantine|12|membership ID만 대조; 본문 분류/새 복사 없음|

입력 관측239/고유238/재관측1(`860977`)은 고정 D1 manifest의 선행 관측 회계다. 이번 consumer는 고유ID를 사용하고 수집을 반복하지 않았다. 비개발97을 제외한 다음 개발141 전부의 게시일 미상으로 시간 분모에서 제외한다. 이 두 제외 단계는 겹쳐 더하지 않는다. 구매SKU 확인0이며 page_model과 purchased_model=null을 유지한다.

## 산출물과 사용 순서

1. [handoff-summary.json](handoff-summary.json): version·파일SHA·대상/제외/분모·승인/운영 상태.
2. [development-sources.json](development-sources.json): 고정 ResearchBundle3의 **review Source141만** 원 객체 그대로 복사. URL/selector/원ID/판본/본문/hold/exposure 유지. 공식 설명서·FAQ·설치·시연/평가 자료를 후기 annotation으로 섞지 않았다.
3. [annotation.draft.json](annotation.draft.json): 141행, 292개 원문 인용의 unicode codepoint `[start,end)`와 SHA, 24개 draft 주제, 종합 의견, 상품/서비스/가격 영역, 기대·과거제품·조건 유보, 반례12쌍.
4. [draft-memberships.json](draft-memberships.json): 원 ID별 제품군/의견/주제·극성 membership. 한 후기가 같은 주제의 양쪽에 속할 수 있다. 건수는 초안 검토용이며 모든 topic ratio는 null.
5. [partition-memberships.json](partition-memberships.json): 원238의 분할 ID. [review-id-map.json](review-id-map.json)은 실제 Source ID와 별도 검수용 Review/Evidence 기대 대응.
6. [date-only.metadata.json](date-only.metadata.json), [projection.date-only.dataset.json](projection.date-only.dataset.json), [empty-collector-checks.json](empty-collector-checks.json): 기존 집계기의 날짜 미상 제외/빈 분모 검사. 아래 적용 한계를 함께 읽는다.
7. [검수 근거](../../../../../evals/data-trend-handoff/20261008-01a114f6/README.md).

## 초안 의미와 반례

Codex가 이 작업의 개발 원문을 읽어 작성했다. 별도의 참가작 모델/OCR 호출은 없으며 **사람의 정답/독립 평가 Gold/PM 승인된 분류**가 아니다. 별점은 분류 규칙으로 사용하지 않았다. 본문 기준 종합 의견 초안은 긍정106/부정13/혼합16/판단미확인3/중립3이다. 의미 정확도는 null이며 승인 전이다.

중요 문맥을 골라 인용했으며 모든 주제 언급의 포괄성/누락률은 검증하지 않았다. [인수 검토 지점](approval-checklist.md)에 구체 원ID·판단 범위·WEB 인수 기준을 연결했다.

|검토 사례|보존할 양면/한계|
|---|---|
|848850, 별점5|냉장실 접근/용량 만족과 깊숙한 수납 접근·전면 돌출의 아쉬움. 같은815mm처럼 맥락을 합치지 않는다.|
|798666, 별점1|제품은 마음에 든다는 문장과 배송·설치 설명의 불만. 제품 성능 부정으로 일괄 분류하지 않는다.|
|807886, 별점3|본문은 반복되는 `좋아요`뿐. 별점을 불만 주제로 바꾸지 않는다.|
|837305 ↔ 859746|같은 MW23FDI 표시 페이지의 가열 실패 보고/빠른 가열 만족. 실제 구매SKU·시기·식품/용량/설정/전원/시험조건 일치 미확인. 원문100W 반문·리콜 요구는 공식 출력/리콜 사실이 아니다.|
|440531 ↔ 773516|같은 DUE6BGL2E 표시 페이지의 건조 불편/건조 만족. 코스·적재·열풍·조건 차이 미확인.|
|850388|디자인 긍정과 성능 체감 판단 한계. 성능 불만/혼합 감정으로 확정하지 않았다.|

반례는 조건이 다른 보고도 존재함을 보여준다. 불편 보고를 무효화하거나 고객 원인/제품 결함·호전·시장 수요를 판정하지 않는다. 냉장고 소음/식기 냄새처럼 대응 반례가 없는 주제의 반례를 만들어 넣지 않았다.

## 기존 집계기의 실제 재사용 범위

PM 고정 코드의 `lgax_api.review_trends.build_review_trend_collection`을 import해18페이지 범위×월/계절 **36개의 빈 날짜 검사**를 실행하고, 고정 출력36개를 다시 계산해 일치했다. 모든 시간 membership은 비어 있고 분모0·ratio=null이다. 월별/계절별 추세 자료나 차트를 생성·표시하지 않는다.

기존 집계기는 model_id를 필수로 요구한다. 확인되지 않은 구매SKU를 채우지 않고, 별도 검수용 `PAGE-{displayed_model}` 범위를 사용했다. `OBS-R8-REVIEW-*`/`OBS-R8-EVIDENCE-*`는 원 Source와 대응하는 **관찰 투영 ID**이며 신규 canonical Evidence 등록 성공이 아니다. `record_review_id`, `record_document_version`, `record_original_text_sha256`가 없는 원v2 행은 null로 남겨 원 필드 부재도 보존했다. 전체 HTML SHA가 없는 DOM 관측을 전체 HTML 확보로 기록하지 않았다.

집계기에 전달한 sidecar는 전부 `classification_status=unclassified`, `topic_ids=[]`, `published_at=null`이다. 위 주제 초안은 trusted collector에 주입하지 않았다. 빈 cleaning 필터의 count0은 승인된 cleaning 언급이 없다는 의미가 아니다. 공통 계약 변경/운영 DB·API 등록/재시작/웹 변경도 수행하지 않았다. 실제 R8 product_group→운영 trend 연결은 PM의 승인 계약/담당 consumer에서 처리해야 한다.

## 파일 SHA 구분

- annotation.draft.json 파일SHA: `871c4618737f380e24725854aa8f37c665c3a8de8eca9775c3e65ca679211409`.
- development-sources.json 파일SHA: `e47f77303b83597a9c146e96f10cd1ff505d480e9f53abb80448178e481a1162`.
- date-only.metadata.json 파일SHA: `d34c2bd32b89f96718ad4ab278e797c004611c88b4107780ee23e9dbc34239ee`.
- date sidecar의 canonical annotation SHA: `d387b3a02c366d04a0b1afb3e1f41436b782a70d687b2a7d464dc19d6e17dded`.

파일 바이트 SHA와 canonical annotation SHA는 다른 값이다. 원 입력 출처/SHA·null·ID membership과 같은 version을 WEB에 인계하며, 실제 파일 읽기 수신과 실제 운영/화면 소비 검증은 별도로 기록한다.

## 실제 WEB 읽기 수신

[choigilung 수신 회신6043200182](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6043200182): 고정 e52cd06의 위 두 파일을 실제 읽고 version/SHA·141Source 원 객체·292인용·12반례·24taxonomy·development분리/null·의견 분포를 대조했다고 보고했다. 작성자/대상head/본문을 인증된 GH조회로 확인했다. WEB의 검수 스크립트/receipt.json은 로컬commit이며 공개파일은 아직 미수신이다.

이는 **파일 읽기 수신**이며 PM분류승인/운영/차트/실화면소비가 아니다. [실제 수신 근거](../../../../../evals/data-trend-handoff/20261008-01a114f6/recipient-receipts.json)에 CORE/WEB 회신과 범위를 함께 고정했다. handoff-summary.json의 `web_receipt_confirmed=false`는 e52cd06 산출 생성 시점의 snapshot 상태이며 현재 수신 결과는 별도 이 파일에 있다. 고정 원문/annotation/version/SHA는 수신 뒤 수정하지 않았다.
