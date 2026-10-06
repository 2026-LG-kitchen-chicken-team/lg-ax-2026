# 리뷰 동향 공통 인터페이스 v1 — PM 공통 연결 구현

2026-10-06 Issue152의 공통 규격이다. 이전 설계 확정에 이어 **공통 JSON Schema·형식/의미 검사·private API/MCP·웹 클라이언트·불변 SQLite snapshot의 소스를 구현했다.** 실제 DATA 집계기와 승인 sidecar 연결, WEB149의 그래프/사용 흐름, ChatGPT·Claude 계정에서 새 도구를 실제 호출하는 검증은 남아 있다. 기존 Review·8열 CSV·자료 원본·PlanningRequest는 변경하지 않는다. 테스트 수치·CI·병합/배포 증빙은 검증 결과 대기이며 후속 PM 기록으로 연결한다. 필수 판단 품질 보완이 동향 기능보다 우선이다. 구체적인 DATA148 인계 규격과 구현 범위는 [구현 인계](review-trends-implementation-20261006.md)를 따른다.

## 자료를 연결하는 sidecar

기존 리뷰에 날짜/주제를 억지로 넣지 않고 서버가 승인한 별도 `ReviewTrendMetadata`를 사용한다. 조회하는 기획자/LLM이 임의 날짜·주제·원문을 제출해 집계 자료로 승인하는 경로는 만들지 않는다.

- 상위 필드: `dataset_version`, `dataset_sha256`, `annotation_version`, `annotation_sha256`, `topic_taxonomy_version`, `dedup_policy_version`, `classification`, `rows`.
- `classification`: `method`는 human/rule/model/unclassified, `model_id`·`revision`은 해당할 때 실제 버전, 해당 없으면 null.
- 각 row: `review_id`, `evidence_id`, `source_id`, `model_id`, `document_version`, `source_kind`, `text_sha256`, `published_at`, `date_precision`, `date_provenance`, `topic_ids`, `classification_status`, `dedup_key`.
- `source_kind`는 기존 계약의 synthetic/public/licensed/private를 재사용한다. 같은 집계에서 자료 성격을 섞지 않는다.
- `published_at`은 YYYY-MM-DD 또는 offset/Z가 있는 RFC3339 시각이며 `date_precision` day/instant와 일치해야 한다. 날짜가 없으면 null·unknown·date_provenance=null이다. 날짜가 있으면 승인 출처의 `source_id`·`locator`·`source_sha256`로 날짜를 확인할 수 있어야 한다. 모델이 추측한 날짜만으로 승인하지 않는다.
- `classification_status` classified/unclassified를 구분한다. `topic_ids=[]`만으로 미분류를 판단하지 않는다. 한 리뷰의 주제 ID는 중복 없이 최대50개다. 중복 키가 없을 때도 원 리뷰 ID의 중복 입력은 중복으로 계산한다.
- 모든 review/evidence/source/model/version/hash는 작업실의 고정 자료와 실제로 결합돼야 한다. 인용 근거는 같은 리뷰 원문을 가리킨다. dataset_version과 document_version은 서로 다른 값이다.
- annotation 해시는 자신의 `annotation_sha256`을 제외한 고정 canonical JSON으로 계산한다. `canonical_annotation`은 row의 topic ID와 row 전체를 정렬하며, 같은 원 리뷰의 반복 row는 제거하지 않는다. `annotation_digest`와 SQLite snapshot 저장에 같은 정규화를 사용해 입력 순서만 바뀐 동일 내용이 같은 해시/ID와 저장 결과를 갖도록 한다. 리뷰 원문의 Unicode·공백·바이트를 정규화하지 않는다.
- 날짜 출처의 `source_sha256`은 승인 sidecar의 출처 고정값이다. 현재 공통 모듈에는 원 출처 파일 바이트가 없으므로 원 파일 해시나 실제 게시일을 독립적으로 확인한 것으로 표현하지 않는다. DATA148은 실제 승인 과정에서 원본 위치·버전·파일 해시·날짜 근거를 확인해야 한다. 공통 검사는 기존 리뷰/Evidence의 원문 UTF-8 해시와 모델·문서·출처의 결합을 검사한다.

현재 기존 리뷰36개의 날짜는 알 수 없으므로 원 자료를 보존한다. 시연용 날짜를 넣으면 새 synthetic 자료/annotation 버전으로 분리한다. 실제 수요·판매 계절성의 증거로 쓰지 않는다.

## 요청과 집계

`ReviewTrendRequest`는 `project_id`, 단일 `model_id`, 고유 `source_ids`(1~50), `dataset_version`, `start_date`, `end_date_exclusive`, `granularity`(month/season/year), 고유 `topic_ids`(0~50), 단일 `source_kind`, `timezone="Asia/Seoul"`을 받는다. 기간은 KST 달력의 **[시작일, 종료일)**, 시작<종료, 최대10년·120월 bucket으로 제한한다. 원 작업실에서 허용한 자료/모델 범위를 확장하지 않는다.

`ReviewTrendAggregate`에는 다음을 보존한다.

- `aggregate_id="TREND-"+hex64`, `project_id`, 자료/annotation 버전·해시, `trend_contract_version="review-trends.v1"`, 검증된 `filters`, timezone, `aggregation_version`, classification, topic/dedup 버전.
- counts: `input_review_count`, `excluded_out_of_scope_count`, `in_scope_review_count`, `excluded_undated_count`, `excluded_outside_period_count`, `duplicate_count`, `eligible_unique_review_count`, `unclassified_review_count`. 처리 순서를 자료/모델 scope → 날짜 유무 → 기간 → scope 내부 중복으로 고정하고 제외를 중복 합산하지 않는다. input=in_scope+범위밖, in_scope=날짜없음+기간밖+중복+유효 고유 리뷰가 되도록 검사한다. unclassified는 유효 고유 리뷰의 부분집합이다. 냉장고 범위10건이 날짜 없으면 undated10이며 전체 제품36건을 undated로 세지 않는다. 중복은 같은 모델/자료 성격/승인 출처 범위에서만 제거하고 같은 키의 상충 본문은 거절/진단한다.
- bucket: `bucket_id`, `period_start`, `period_end_exclusive`, `label`, `partial_period`, `total_reviews`, `topics`.
- topic: `topic_id`, `topic_review_count`, `ratio`(0~1 또는 null), `evidence_count`, 고유 `evidence_ids`(최대50), `evidence_ids_truncated`. 대표 ID가 잘렸으면 완전한 원문 목록은 별도 드릴다운으로 조회한다.
- `warnings`와 `notes`(선택, 최대800자)는 원자료/처리 한계를 설명한다. 숫자 생성·인과/판매량 주장에 쓰지 않는다.

분모는 해당 기간의 유효한 **고유 리뷰 전체**이며 주제 필터로 먼저 좁히지 않는다. 같은 리뷰·같은 주제는 한 번만 센다. 한 리뷰에 여러 주제가 있어 주제별 분자의 합은 분모보다 클 수 있다. 각 주제 분자 자체는 분모를 넘을 수 없다. 분모0이면 ratio=null, 분모>0·해당 주제0이면 ratio=0이다. 빈 구간과 0%를 다르게 표시한다. 표본20미만의 작은 표본 경고는 통계적 유의성 판정이 아니다.

ID는 project·정규화/정렬한 filters·고정 자료/annotation 해시·aggregation/topic/dedup 버전으로 결정한다. filters의 중복 ID는 입력 오류로 거절한다. 클라이언트 종류·생성 시각은 포함하지 않는다. 웹/MCP의 같은 요청은 같은 ID, 다른 작업실/자료 버전은 다른 ID다. SQLite에 aggregate·정규화한 metadata·완전한 membership·당시 canonical 원문을 저장하고 동일 ID의 서로 다른 결과를 거절하는 소스를 구현했다. 저장한 결과/원문 조회는 현재 자료로 재계산하지 않는다. 재시작 보존·동시 동일 요청·자료 변경 후 과거 결과 조회의 실제 검사 결과는 대기다.

월은 월초~다음 월초, 연도는1/1~다음1/1이다. 봄3~5·여름6~8·가을9~11·겨울12~2이며 **겨울2026=[2026-12-01,2027-03-01)**이다. 2027년1~2월은 겨울2026에 속한다. 요청이 기간의 일부만 포함하면 partial_period=true이고 숫자는 요청 범위 안에서만 계산한다. 전체 계절 수치처럼 표시하지 않는다. 윤년·UTC/KST 경계·정렬을 검사한다.

## private 웹/API/MCP 연결

새 연결은 기존 작업실 owner/viewer/admin 인증·401/403·원문 오류 가림·no-store를 재사용한다. 공개3도구 endpoint를 개인 자료/작업실 도구로 변경하지 않는다.

| 구현한 공통 인터페이스 | 목적 |
|---|---|
| GET `/api/workspace/projects/{project_id}/review-trends` | 검증된 query의 결정적 집계 |
| GET `.../review-trends/{aggregate_id}` | 승인된 작업실의 고정 집계 snapshot |
| GET `.../{aggregate_id}/evidence?bucket_id=&topic_id=&offset=0&limit=50` | 집계에 실제 포함된 해당 bucket/topic 원문 페이징 |
| MCP `review_trends`, `get_review_trends`, `trend_evidence` | 같은 코어/권한/ID를 조회하는 read-only 도구 |

드릴다운 결과는 aggregate_id·bucket/topic·offset·limit·total·next_offset·canonical Evidence[]이며 임의의 타 집계 원문을 반환하지 않는다. MCP는 readOnlyHint/idempotent=true, openWorld=false다. route/tool과 웹 클라이언트는 구현했으며 실제 DATA 집계기/sidecar가 미연결인 기본 adapter는 **501 NOT_IMPLEMENTED**를 반환한다. 숫자·그래프용 성공 응답을 꾸미지 않는다. 정상 날짜 없는 자료는 승인 집계기를 연결한 뒤 빈 bucket·실제 제외 건수로 표시한다. 기존 공개3도구는 변경하지 않았다. 실제 외부 호스트 호출은 미확인이다.

자료/annotation/hash 불일치는409 DATASET_MISMATCH, 동향 입력 의미 오류는422 INVALID_INPUT, 계약/근거 불일치는422 CONTRACT_MISMATCH로 처리한다. FastAPI query 형식 오류와 기존 공통 형식 오류는 기존 INVALID_ARGUMENT 경로를 유지한다. 공통 Error enum에 INVALID_INPUT을 추가했고 기존 오류 코드는 유지한다. JSON Schema와 별도 의미 검사를 함께 구현하여 실제 source 존재·고정 범위·분자/분모·기간·membership·ID를 대조한다. 권한은 서버의 기존 owner/viewer/admin 경계에서 검사하며, 이 검사를 실제 날짜 출처 승인 완료의 증거로 사용하지 않는다.

기획 Agent 연결은 처음에는 승인된 evidence_ids의 기존 근거 경로를 사용한다. closed PlanningRequest에 임의 aggregate 필드를 추가하지 않는다. aggregate 참조를 정식 입력으로 늘리는 변경은 코어·웹·MCP와 공통 계약 PR에서 검토한다.

## 담당 인수와 의미 있는 검사

1. PM152: 독립 schema/fixture와 필드 간 의미 검사, 집계기 injection·private 조회/공유 ID·snapshot 저장·웹/MCP 공통 클라이언트를 소스로 구현했다. 독립 검수의 표본 경고 누락과 annotation 순서에 따른 저장 충돌을 보완했다. 격리 검사·CI·병합/배포 근거는 대기이며 실제 DATA 집계기 연결 완료를 뜻하지 않는다.
2. DATA148: 위 sidecar·결정적 집계·근거 드릴다운을 구현한다. 기존8열 importer를 깨지 않고 원문/날짜 근거/모델/버전을 결합한다. PM 규격 미정 때문에 대기할 필요는 없으며 실제 연결 전 부분 결과임을 표시한다.
3. WEB149: 위 요청/응답의 명시적 synthetic fixture로 기간 필터·분모/누락/빈구간·그래프·원문 흐름을 준비한다. 실제 API/코어 미연결을 완료로 바꾸지 않는다.
4. CORE150: 필수 판단 품질 보완 뒤 집계 원문→기존 기능 대조→기획 가설·과잉 해석 검사를 이어간다.

필수 검사: 형식 정상/잘못된 sourcekind·날짜, 원문/hash/version/타 모델 바꾸기 거부, 날짜null/부분기간/빈분모/주제0/다주제/중복, 겨울 연도/윤년/KST 경계, 주제 필터를 바꿔도 분모 불변, 웹/MCP 동일ID·자료/작업실 변경시ID변경, 타 작업실401/403, 존재하지 않는집계/해당하지 않는근거, 드릴다운 페이징/잘림, 동일ID 다른결과 덮어쓰기 거부·재시작 snapshot 보존. 강한 LLM 해석은 고정 숫자를 재계산하는 대신 실제 원문·표본 한계를 인용해야 한다.

재사용 위치는 기존 Review/SourceKind와 Python FormatChecker, Review CSV parser/importer, DocumentStore의 원문 연결, WorkspaceStore의 project 권한·고정 dataset hash·source scope, private API middleware, private MCP WorkspaceClient다. 동향 Schema에 엄격한 Gregorian date/date-time 패턴을 추가하고 Python/Ajv가 같은 fixture에서 2026-02-30 거부·2028-02-29 허용·시간대 없는 timestamp 거부를 대조하도록 전용 검사를 작성했다. Date.parse의 날짜 보정에만 의존하지 않는다. 형식 검사·의미 검사·API/MCP/클라이언트 검사의 실제 결과는 대기다. 공통 검증 소스는 모델을 호출하지 않으며, DATA 실제 집계와 LLM 해석의 호출/비용은 실제 연결 후 별도 기록한다.
