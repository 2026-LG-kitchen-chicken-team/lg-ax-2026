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

**현재 실행 제한:** `ResearchBundleProducerSidecar`는 PM P0 정식 schema/adapter 수신 전의 생산자 묶음이다. 이를 기존 `Evidence`나 기획 API에 그대로 업로드하지 않는다. 실제 AI 실행·운영 인수는0이며 특정 SKU의 사실 판단 적격은 그대로0이다. 제품군 연구와 정확 SKU 사실 판정을 구분한 P0 소비 인수가 남는다. [구체 인계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6038078659).

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

1. PM이 P0 ResearchBundle schema/consumer·source type 매핑을 고정한다.
2. D4 담당 창은 이 고정 자료 manifest와238개 membership으로 표본·중복·개발/평가/시연 분리·노출을 독립 검수한다.
3. CORE/PM은 승인한 개발 제품군 입력만 소비해 실제 기획 실행을 검증한다. 평가 후보·시연·격리 자료를 개발·튜닝에 섞지 않는다.

이 자료 전달은 D1·D2 첫 인수 단위다. P0/실제 모델/독립 평가/PM 병합·통합과 #12 전체 완료는 별도다.
