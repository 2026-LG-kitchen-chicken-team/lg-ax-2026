# D1 리뷰 통합과 D2 공식 자료 첫 인계

신진하의 수동 D1·D2 결과다. [PM 수동 큐 #234](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234)와 사용자의 직접 실행·PR 제출 요청을 따른다. D3 경쟁제품 생산과 D4 독립 검수, CORE 판단, PM 공통 계약/API는 편집하지 않는다.

## D1: 같은 238건을 세 가지 용도로 전달

- **연구 DB:** 기존 `save_landing_db`를 재사용해 고유 후기238개와 원 관측239개를 적재했다. 추가 표본의 원ID `860977`은 기존 후기와 중복되어 고유 수에서1개 제외하고, 두 관측의 원 JSON은 모두 보존한다. 새 DB이며 미수신된 원179개 DB나 운영 DB를 받았다는 뜻이 아니다.
- **검토 Excel:** [reviews-238.xlsx](reviews-238.xlsx)는 요약,238개 리뷰,239개 관측,18표시모델·출처를 담는다. 원문·ID·출처 URL/위치·본문 SHA·설명서 판본·기존 분할을 저장 후 다시 대조했다. 원자료에서 가린 연락처는 복원하지 않고 작성자·사진·영상·가구 정보를 새로 수집하지 않는다.
- **Agent 전달 자료:** [agent-input](agent-input/)의 제품군별 producer 묶음에는 개발141개만 넣는다. 평가36·시연49·격리12는 섞지 않는다. 기존 정확모델 입력 `canonical-models.dataset.json`은 원바이트 그대로이며 설명서3·기능9·근거21·리뷰0이다.

| 기준 | 건수·처리 |
|---|---|
| 고유 후기 |179+59=238|
| 원 관측 |179+60=239; 중복 관측1 보존|
| 개발 / 평가 후보 / 시연 후보 / 격리 |141 / 36 / 49 / 12; 재분할0|
| 격리 제외 연구 분모 |226; 전체 시장 대표성·불만 비율을 뜻하지 않음|
| 확인 구매모델 / 확인 게시일 / 정확 SKU 판단 적격 |0 / 0 / 0; 원 `null`과 보류 유지|
| 별점 |1점22·2점2·3점6·4점0·5점208; 감정 정답으로 사용하지 않음|
| 월·계절 동향 |게시일 분모0; 산출하지 않음|

추천순의 기존179개는 모두5점이다. 추가60관측은 세 모델의 최신순·낮은별점 각10개를 의도적으로 골랐다. 표본 편향을 가리고 전체 고객 수요·불만 빈도로 표현하지 않는다. 제품 페이지의 모델·리뷰 리스트MD는 구매 SKU 증명이 아니다. 현재 설명서 판본과 구매 당시 판본도 구분한다.

[d1-membership.json](d1-membership.json)은238개 ID·원문 SHA·기존 그룹과 분할·출처를 연결한다. 원 v2의 `body_group_id`는 원 필드 그대로 남기고, 기존 DB writer용 `dedup_group_id` 열에만 대응시킨다. 과거 개발 노출3그룹과 시연후보2그룹의 별도 승인 보류를 보존한다. 원 연구 split를 독립성 승인으로 바꾸지 않는다.

### DB 사용법

프로젝트의 기존 Python 환경에서, 게시 인증을 제외한 격리 환경으로 실행한다. 새 설치나 원자료 재수집은 필요하지 않다.

```sh
PYTHONPATH=packages/core/src:packages/contracts/src python data/research/r8-public-research-20261007/d1-d2-01a10600/build_d1.py --output private/research/d1-d2-01a10600
```

새 출력 경로만 허용한다. 기존 폴더/DB를 덮어쓰지 않는다. DB는 `research-238.sqlite3`, 자료와 확인 결과는 `manifest.json`, `membership.json`, `original-records.json`, `agent-input/`이다. Git·소스 ZIP의 DB 제외 규칙을 유지해 PR에는 DB 재생성 코드와 SHA/행 대조를 전달한다. 실제 DB는 사용자 로컬 산출물로 보존했다.

```sql
SELECT split,COUNT(*) FROM reviews GROUP BY split;
SELECT COUNT(*) FROM original_observations;
SELECT original_review_id,displayed_model_id,actual_purchased_model_id,published_at
FROM reviews WHERE original_review_id='860977';
```

[d1-delivery-manifest.json](d1-delivery-manifest.json)의 `source_hashes`와 출력 파일 SHA를 확인한다. DB 안 `collection`은 생성에 필요한 원자료·분할·보류 manifest이며, 외부 delivery manifest의 생성 후 출력 SHA까지 자기 파일에 포함하는 구조는 아니다.

**첫 checkpoint(6fd98c0)의 실행 제한:** `ResearchBundleProducerSidecar`는 PM P0 정식 schema/adapter 수신 전의 생산자 묶음이다. 이를 기존 `Evidence`나 기획 API에 그대로 업로드하지 않는다. 실제 AI 실행·운영 인수는0이며 특정 SKU의 사실 판단 적격은 그대로0이다. 제품군 연구와 정확 SKU 사실 판정을 구분한 P0 소비 인수가 남는다. [구체 인계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6038078659).

## D2: 원 설명서와 새 공개 근거의 구분

[d2-source-pack.json](d2-source-pack.json)과 [d2-evidence-index.csv](d2-evidence-index.csv)에 세 모델별 source ID·type·URL·확인시각·판본·쪽/구간·해시 범위를 연결했다.

| 자료 | 이번 처리 | 적용·한계 |
|---|---|---|
|기존 공식 PDF3|T876MEE1H1: MFL71401557 Rev.00_032526 / DUE6BGL2E: MFL71959117 Rev.07_030626 / MW23FDI: MFL68822538 Rev.00_120925 재사용|새 PDF 다운로드0. 기존21근거의 같은 페이지·연속 구간·본문 SHA를 대조|
|공개 FAQ3|냉장고 기계실 청소, 식기세척기 적재, 전자레인지 용기|공용 안내. FAQ 제목·요청 모델만으로 정확 SKU 기능을 확정하지 않음|
|공개 설치 안내3|냉장고 간격, 식기세척기 설치 형태, 전자레인지 통풍 공간|원 `installation` type 유지. 모델에 따른 차이를 임의 삭제하지 않음|
|공개 고객 Q&A1|DUE6BGL2E 설치공간 질문470877·LG 답변|제품 모델명 명시. 고객 치수의 `119~120mm` 표기는 모호하며 교정하지 않음|
|고객 Q&A 미확인2|T876MEE1H1·MW23FDI|미확인을 질문0/기능없음으로 표현하지 않음. 실패 단계·필요 입력 기록|

설치 보조 인덱스는 냉장고5쪽의220V/조건부16A, 식기세척기58쪽의빌트인 설치 공간, 전자레인지11쪽의상부/좌우·뒤 간격/바닥 높이를 각각 연결한다. 전자레인지의 표지·11쪽과 식기세척기58쪽 도해를 원본으로 확인했다. 텍스트 추출은 기존 pypdf6.10.0을 먼저 사용했고 OCR은0회다. 텍스트의 정확 모델 토큰 검색 false와 원본 표지의 모델명 존재를 구분해 MW23FDI 시각 확인을 남겼다.

식기세척기 설명서의 **표준 최소 깊이600mm**와 Q&A의 **조건부567~600mm**는 둘 다 남긴다. 후자는 배관 눌림·설치 기사 확인 조건이며 표준 최소값을567mm로 바꾸는 근거가 아니다. 문 앞590mm와 싱크대 깊이600mm도 서로 다른 치수다. 냉장고 공용 간격의 정확 SKU 적용은 이번 팩에서 미확인으로 남긴다.

웹의 표시 날짜는 문서 개정일로 단정하지 않는다. 미제공 판본·전체 HTML SHA는 `null`이다. 짧은 원문 발췌 SHA와 전체 PDF SHA를 구분하며, 새 이미지·문서 전체·고객 신상·후기 전문을 새로 수집하지 않았다. 기존 가상 모델·합성 리뷰는 이번 팩에 사용하지 않았다.

공용 설명서의 선택 기능에 대한 기존 [SKU 적용 결과](../../P2-DATA-001-sku-application-20261006/sku-application.json)와 [후속 근거](../../P2-DATA-001-sku-followup-20261006-91059ff2/sku-followup.json)를 연결한다. 일반 사양9개를 새로 수집하거나 기존 미확인 선택 기능을 FAQ로 확인 처리하지 않는다.

## 검사·버전·다음 인수

자료 출처는 고정 main58feb9c, 새 PR의 base는3e2a19d다. 자료8파일과 기존 landing writer의 바이트가 새 base에서도 같음을 대조했다. 새 builder의 실행은 GitHub 인증·네트워크 없는 Docker에서 했으며 source/code SHA와 원 명령/출력은 [실행 근거](../../../../evals/data-d1-d2/20261007-01a10600/)에 있다. 이전 실패·사용량·개인 기록·원자료는 변경하지 않았다.

1. P0/PR245의 정식 ResearchBundle 계약을 ef29aa8에서 수신했다. 아래 현재 입력의 계약 검사를 확인하고 PM이 운영 인수한다.
2. D4 담당 창은 이 고정 자료 manifest와238개 membership으로 표본·중복·개발/평가/시연 분리·노출을 독립 검수한다.
3. CORE/PM은 승인한 개발 제품군 입력만 소비해 실제 기획 실행을 검증한다. 평가 후보·시연·격리 자료를 개발·튜닝에 섞지 않는다.

이 자료 전달은 D1·D2 첫 인수 단위다. P0/실제 모델/독립 평가/PM 병합·통합과 #12 전체 완료는 별도다.

## P0 수신 후 현재 실행 입력

첫 로컬 checkpoint6fd98c0 뒤 PM PR245가 병합되어 ef29aa8의 `research-planning.schema.json`을 수신했다. 이전 producer 파일과 실행 증거는 보존하고, 실제 사용할 파일은 `agent-input/{fridge,dishwasher,microwave}/research-bundle.json` 세 개로 별도 준비했다. **`.producer.json`은 이전 checkpoint이며 기획 API 입력이 아니다.**

PM R8의 개발 review Source 객체141개를 그대로 재사용·원 membership과 대조했다. 기존21설명서 Evidence와 이번 FAQ3/설치3을 같은 P0 type/role로 연결하고, DUE질문470877은 고객 질문과 LG 답변 두 Source로 분리했다. Source 수는 냉장고58/식기세척기59/전자레인지53, 리뷰는48/48/45다. 경쟁제품 자료는 D3 담당의 별도 팩으로 유지하며 이 LG 팩에 섞지 않았다.

새 짧은 발췌의 원문은 현재 canonical 입력에 한 번 보관하고 D2 근거표는 `canonical_excerpt_ref`로 같은 source_id/text SHA를 연결한다. QA600/590/조건부567~600mm는 답변의 서로 다른 문단 위치·조건을 보존한다. 선택 발췌 밖에서 확인한 숫자와 조건은 별도 facts/metadata의 원 문단으로 구분하고 하나의 연속 인용이라고 표시하지 않는다. 고객 치수는 unknown fact로 유지한다.

[P0 연결·파일 SHA](../../../../evals/data-d1-d2/20261007-01a10600/p0-alignment.json). 이 변경은 자료 계약 맞춤이며 서버 등록·모델 호출·운영 인수가 아니다. 실제 기획용 서버에는 승인된 환경에서 세 파일을 `--research-bundle`로 지정할 수 있다. 이번 작업에서 서버를 켜거나 설정을 바꾸지는 않았다. 원 DB/XLSX는 재생성하지 않았고 같은 SHA를 유지했다.

다음은 D4의 고정 자료 독립 검수와 PM/CORE의 승인된 이 자료 버전 소비 인수다. 정확 SKU 판단 적격0·확인 리뷰 게시일0, 다른 정확모델 고객Q&A 미확인2는 유지한다. 제품군 기획과 정확 SKU 사실 판정은 별도다.

최종 입력3개는 P0계약 검사와 개발141개 ID·원문·표시모델·split/null/hold 대조를 통과했다. [현재 산출물 수신증](../../../../evals/data-d1-d2/20261007-01a10600/current-delivery.json). Excel은 P0수신 안내 C26 한 칸만 갱신했고 나머지 모든 값·판본·날짜·수식·표/고정열·셀 형식은 원본과 같았다. 원 Excel/6fd98c0은 보존했다. 시작·수집은10/7, 최종 규격 검사·게시 준비는10/8 KST다.

## PM 관리·냄새 절 후속 보완

PM #5의6039619781과 독립 감사 PR252/78a1906을 수신해, 기존 공식 DUE6계열 PDF의 관리·냄새/문제해결14개 범위를 같은 native page·start/end·SHA로 직접 대조했다. 새 식기세척기 입력은 `-v2-care`/73 Source, 전체는58+73+53=184이며 개발141개는 그대로다. [연속 범위·판본·쪽·SHA](d2-care-evidence-index.json)를 사용한다. 내부/필터39–40, 세척조41–42, 노즐42–43, 보관43, 냄새49, 성능50과 안전5/진단48을 연결했다. 43쪽 native `50 7`은 그대로 두고 감사의 시각50℃ 확인을 별도 표시했다. 범위/원문 대조를 새 자동 표 구조·OCR 성능이나 고객의 실제 원인/호전으로 처리하지 않는다. 정확 구매SKU·구매시점판과 선택 코스 적용은 미확인이다.
