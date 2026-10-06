# R4 원 날짜 미상·PM 날짜팩·DATA 날짜팩 인계

배정: [PM DATA-INTEGRATION-R4](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6015348109). 본인 관련메일을 읽은 뒤 공개 PM PR188 고정 입력과 실행 당시 main을 대조했다. 이 표는 검증한 입력과 실행 범위의 인계이며 운영팩 선택을 바꾸지 않는다.

- DATA 코드/원 입력 pin: `087bd534e5b400b05c2963341d07587c1ee70772` (검사 시점 main).
- PM 공개 날짜 입력 pin: `2d4ea07e078e99776d534a10f4ed43ab8fec7095` ([PR188](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/188)). 이 원문 pin을 최신 운영 배포 완료로 쓰지 않는다.
- [108개 원문·ID·모델·버전 바인딩](run-01a1100e-03/review-bindings.json), [15개 query/재계산·재생](run-01a1100e-03/queries.json), [40개 거절](run-01a1100e-03/rejections.json), [실제 검색](run-01a1100e-03/searches.json). 모델 생성0회.

## 고정 source/version/ID와 10월 결과

|자료팩|dataset 버전·review / Evidence ID|출처 ID|전체 구성 날짜 / 미상|FRIDGE-A 10월 분모·청소 언급·비율|범위 내 미상 / 기간 밖|
|---|---|---|---:|---|---|
|original|`0.1.0` · `REVIEW-NNN / REVIEW-EVIDENCE-NNN`|`REVIEWS-CSV-v1.0`|0 / 36|0 · 0 · null|10 / 0|
|pm|`pm-synthetic-trends.v1` · `DEMO-TREND-REVIEW-NNN / DEMO-TREND-REVIEW-EVIDENCE-NNN`|`PM-TREND-DEMO-REVIEWS-v1`|31 / 5|3 · 1 · 0.3333333333|2 / 5|
|data|`synthetic-dated-demo.20261006.v1` · `SYNTH-DATED-REVIEW-NNN / SYNTH-DATED-REVIEW-EVIDENCE-NNN`|`SYNTH-REVIEWS-DATED-DEMO-v1`|9 / 27|4 · 1 · 0.25|1 / 5|

전부 합성 리뷰36개이며 review/Evidence ID 집합은 세팩 간 서로 다르다. 원 dataset raw SHA `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`, 원8열 CSV raw SHA `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9`를 실제 Git 원바이트와 대조했다. 문장·제품 모델·리뷰 문서 버전36개는 각 새팩과 동일하며 원 CSV의 날짜 없는8열도 그대로다.

## 동일 조회와 다른 숫자의 이유

공통 조회는 project_id=`data-r4-pack-binding`, model_id=`FRIDGE-A`, 프로젝트에 고정한 document_version=`1.0`, source_kind=`synthetic`, start_date=`2026-10-01`, end_date_exclusive=`2026-11-01`, granularity=`month`, topic_ids=`["cleaning"]`, timezone=`Asia/Seoul`이다. source_ids와dataset_version은 위 표의 해당팩 값을 사용한다. 문서 버전은 TrendQuery에 임의 필드로 보내지 않고 프로젝트 snapshot에서 고정한다. [각각의 완전한 query](run-01a1100e-03/queries.json)에 세팩·기간별 값을 보존했다.

|팩|10월 원 리뷰 번호 / 현재 Evidence IDs|청소 numerator|의미|
|---|---|---|---|
|original|없음|없음|FRIDGE-A 원10리뷰 모두 날짜 미상 → excluded_undated10·분모0·ratio null|
|pm|DEMO-TREND-REVIEW-EVIDENCE-001, DEMO-TREND-REVIEW-EVIDENCE-002, DEMO-TREND-REVIEW-EVIDENCE-004|DEMO-TREND-REVIEW-EVIDENCE-001|001·002·004를10월에 구성. 청소001은 번거로움 문장. 006은 미상이라 분모에서 제외|
|data|SYNTH-DATED-REVIEW-EVIDENCE-002, SYNTH-DATED-REVIEW-EVIDENCE-003, SYNTH-DATED-REVIEW-EVIDENCE-006, SYNTH-DATED-REVIEW-EVIDENCE-007|SYNTH-DATED-REVIEW-EVIDENCE-006|002·003·006·007을10월에 구성. 청소006은 크게 불편하지 않다는 긍정 문장|

1/3과1/4는 서로 다른 날짜 배치와 다른 원문 membership의 결과다. DATA006의 긍정 청소 언급도 주제에는 포함한다. 세팩 모두 감정극성 미라벨이며 이 비율을 불만률·실제 불편 빈도·수요로 바꾸지 않는다. 원001은 DATA팩에서 `2026-09-30T14:59:59Z`(KST9/30), 원002는 `2026-09-30T15:00:00Z`(KST10/1)이다. PM009는 `2026-12-31T15:00:00Z`(KST2027/1/1)라12월에서 제외되고1월·겨울에 포함된다.

## 날짜 provenance·주제 preview

- 원팩36행: published_at=null / date_precision=unknown / date_provenance=null. 실제 게시일 추정 없음.
- PM팩31행: date-schedule.json의 row1~36에 바인딩. 이 파일은 날짜·ID 표이며 리뷰 문장은 dataset/Evidence에 따로 있다. schedule 실제 SHA와 row의 review ID·날짜·정밀도를 대조했다.
- DATA팩9행: 별도 source.synthetic-dated-demo.v1.json의 section ID에 바인딩. 날짜·정밀도·review ID와 같은 원문 text 및 실제 파일 SHA를 대조했다. 원 날짜 없는CSV를 날짜 근거로 쓰지 않는다.
- 원candidate7주제 mapping과 새2팩 mapping은 같은 원 리뷰 번호별로 일치했다. 원/DATA의human 분류와 PM의고정 rule 재매핑을 구분하며 후보분류 승인이나 complaint polarity 승인으로 기록하지 않는다.
- 실제 날짜 source 파일SHA·dataset/annotation raw/canonicalSHA는 [고정 pin JSON](run-01a1100e-03/pack-audit.json)에 있으며 서로 다른 종류의 SHA를 섞지 않는다.

## 실제 검사·소비 경계

- 108개 review/Evidence 원문·모델·버전·source 바인딩, 15query(10월/빈기간/겨울/12월/1월) 독립 분모·청소 membership 재계산, 동일 요청 재생과 빈비율null 통과.
- 같은Evidence 중복의 분모 증가를 방지했고 주제가 다른 중복은 거절했다. 40개거절은 잘못된 모델/버전·원문SHA·ID·출처, 세팩 sidecar/Evidence 교차 입력, 실제날짜 source SHA 교체 등을 포함한다.
- 각팩 실제 내부BM25 검색은 scope를먼저 적용했고 원문 Evidence만 반환했다. 동일 요청 결과가 같고 잘못된 모델/버전은 명시 거절됐다. 공개 literal_token_count 계약이나실행API를BM25로 바꾸지 않았다. 15query는 개발/입력검증이며 독립 모델평가·고정45/225행 성능비교가 아니다.
- [실제 loopback HTTP receipt](document-http-main-087bd53.json): 같은main의 원PDF3 등록/검색/원문21/재시작·46HTTP요청을 다시 실행했다. 자체 ephemeral socket·새DB·보존원문 복사본만 사용, 모델/중앙예약0. raw_runtime_receipt_sha256을 보존하고 공개 사본의 환경 경로만 표식으로 바꿨다.
- PR183은20:15 PM 부분 인수·병합. 별도 승인계획 바꿔치기 수정은 [PR189](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/189)에 제출했고, 20:44 조회 headc4d1ea9의CI4/4 SUCCESS를확인했다. 후속의 실제 병합/통합은 별도 관측 대상이다.

## 재현·담당자 인계

```text
git fetch origin refs/pull/188/head
python -B -X utf8 evals/data-integration-r4/20261006/audit_pack_bindings.py --pm-ref 2d4ea07e078e99776d534a10f4ed43ab8fec7095 --output <새 출력 폴더>
```

Python3.11과현재core/contracts/API src를PYTHONPATH에 지정한다. 스크립트는git 원문만읽고 새output폴더에 증거를쓴다. 기존 출력은 덮어쓰지 않는다. [준비 실패2건](setup-failure-history.json)은 검사프로젝트/기대값 수정이며제품/계약코드를완화하지 않았다.

|담당|막힘/남은 범위|요청|
|---|---|---|
|PM @jeongiryang|어떤팩을운영에선택할지·분류승인·#15독립평가·공개BM25계약은DATA단독결정범위 밖|세팩을ID/version/source별로 유지하고 승인된팩만별도DB/같은bootstrap에명시주입, PR189와이R4작은단위를검수|
|CORE @unknownamed|질문없는보류/맥락·기능지지 의미 품질은고정R4실패표와R6유실근거 이후의후속|원응답/비용을보존해실제기능/원불편과대조; DATA가모델을중복생성하지않음|
|WEB @choigilung|PM31팩의기존1/3화면을DATA9팩의1/4화면검증으로승계할수없음|동일dataset/source IDs/aggregate의버전·분모·제외건수·긍정006원문·차트/내보내기를연결해검사|

동향 자기보고는#16·#148, 원문/검색 자기보고는#13에 각각 연결한다. 실제 운영주입·새DATA팩 브라우저·실고객 시계열·독립품질/부모Done은미완료이며자동화OFF다.
