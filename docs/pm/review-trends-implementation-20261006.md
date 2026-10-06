# 리뷰 동향 PM 공통 구현·DATA/WEB 인계

2026-10-06, PM Issue152. [확정 계약](review-trends-contract-v1.md)을 공통 Schema·검증·private 연결·불변 저장 소스로 구현했다. **실제 집계기와 날짜 승인 자료를 연결한 참가자 기능 완성은 아니다.** 격리 테스트 수치·CI·병합/배포 결과는 대기이며 PM의 후속 증빙을 붙인다. 팀·개인 자동화는 OFF이고 이번 변경은 직접 지시를 받은 수동 개발이다.

## 구현 범위와 남은 경계

| 영역 | 이번 소스 구현 | 남은 인수 |
|---|---|---|
| 공통 계약 | Metadata/Request/Aggregate/원문 조회 DTO, INVALID_INPUT 추가, Python·Ajv 공용 fixture | 격리 검사와 CI 결과 |
| 공통 의미 검사 | 실제 원문/모델/문서/source 결합, 자료·annotation 해시, 날짜/분모/중복/기간/membership/ID 검사 | 승인 DATA 자료와 집계기 적용 검증 |
| private API/MCP | owner/viewer/admin, no-store, 조회3경로·읽기3도구, 미연결501 | DATA148 collector 주입과 실제 외부 ChatGPT/Claude 호출 |
| snapshot | SQLite 불변 결과·정규 metadata·완전 membership·당시 원문 저장, 해시 확인·재시작 조회 경로 | 실제 실행·재시작 검사 증빙 |
| 웹 클라이언트 | 같은 계약/ID를 사용하는 TypeScript 조회·원문 페이징 | WEB149 기간/제품/주제 필터·그래프·빈 구간/제외/표본·원문 사용자 화면 |

기존 canonical Review·8열 CSV·PlanningRequest와 `data/demo` 원문은 변경하지 않았다. Schema fixture의 ID·해시는 형식 검사 자리표시자이고, API 단위 collector fixture의 합성 날짜는 테스트 범위다. 이들을 승인 운영 sidecar나 실제 게시일·수요 근거로 등록하지 않는다. 기존 36개 리뷰에 날짜를 만들어 채우지 않는다.

## DATA148 주입 인터페이스

`apps/api/src/lgax_api/workspace_trends.py`의 `TrendCollector`는 서버 운영자가 명시적으로 주입하는 callable이다. 기획자/LLM이 HTTP/MCP로 collector·날짜·주제 annotation·원문을 업로드하여 승인하는 경로는 없다.

```python
collector(project_snapshot, dataset, canonical_filters) -> TrendCollection(
    aggregate=aggregate,
    metadata=approved_sidecar,
    memberships=memberships,
)

create_workspace_app(
    db_path,
    registry,
    evidence_store=trusted_store,
    trend_collector=approved_collector,
)
```

위 코드는 호출 규격이다. `approved_collector` 구현과 실제 승인 자료는 DATA148의 후속 결과로 인수한다. 현재 CLI는 collector를 자동 탐색하거나 활성화하지 않고 기본값 None을 유지한다. 운영 서버 배포와 주입은 PM 검수 후 명시적으로 연결한다.

collector는 project·dataset·정규 filters의 복사본을 받는다. `aggregate.filters`는 전달받은 정규 filters와 같아야 한다. 반환 후 gateway는 DATA의 성공 선언을 신뢰하는 대신 공통 검사를 거친다. 계약/근거/수치가 맞지 않으면 저장하지 않고 오류를 반환한다.

`memberships`는 아래처럼 모든 bucket에 분모 원문과 주제 원문의 **완전한 정렬 ID 목록**을 넣는다.

```json
{
  "MONTH-2026-10": {
    "__all__": ["REVIEW-EVIDENCE-001", "REVIEW-EVIDENCE-002"],
    "cleaning": ["REVIEW-EVIDENCE-001"]
  }
}
```

`__all__`에는 유효한 고유 리뷰 전체를 넣으며 미분류 리뷰도 포함한다. 주제 필터로 분모를 줄이지 않는다. 목록은 해당 bucket/topic의 canonical review Evidence ID만 포함하고 중복 없이 정렬한다. `__all__`은 내부 분모 키이며 사용자 원문 조회 topic으로 노출하지 않는다. aggregate의 대표 `evidence_ids`는 정렬된 목록의 처음50개다. 원문 전체는 membership으로 페이징하고 `evidence_count`·`evidence_ids_truncated`와 맞아야 한다.

## 승인 metadata·해시·정규화

DATA148은 모든 in-scope 원 리뷰에 sidecar row를 제공해야 한다. 날짜를 모르면 `published_at=null`, `date_precision="unknown"`, `date_provenance=null`로 기록한다. 행을 생략해 분모를 줄이지 않는다. 같은 리뷰의 동일 row 반복은 보존하여 `duplicate_count`에 반영하고, 같은 리뷰 ID의 상충 annotation이나 같은 dedup key의 상충 본문은 거절한다.

`apps/api/src/lgax_api/trend_validation.py`의 공통 helper를 사용한다.

| Helper | 의미 |
|---|---|
| `canonical_annotation(metadata)` | topic ID와 row를 정렬한 복사본. 반복 row와 원문 bytes는 제거/정규화하지 않는다. |
| `annotation_digest(metadata)` | 위 정규화에서 자기 `annotation_sha256`만 제외한 canonical UTF-8 JSON SHA256 |
| `trend_identity(filters, metadata, aggregation_version)` | project·정규 filters·자료/annotation 해시·분류/주제/중복/집계 버전으로 결정한 TREND ID |
| `trend_periods(filters)` | 요청이 닿는 전체 월/계절/연도 경계·ID·label·partial 표시 |
| `trend_sample_warnings(buckets)` | 빈 구간 또는 20건 미만 표본의 의무 경고 문자열 |

JSON 정규 직렬화는 `ensure_ascii=False`, `sort_keys=True`, `separators=(",", ":")`, `allow_nan=False`다. `dataset_sha256`은 transport `contract_version`을 제외한 canonical DemoDataset의 해시이며 원 출처 파일 바이트 SHA와 구분한다. `text_sha256`은 canonical Review의 실제 `text.encode("utf-8")` 해시다. NFC/NFD·공백을 바꾼 본문을 동일 원문으로 간주하지 않는다.

날짜 provenance의 `source_sha256`은 **승인 sidecar에 고정된 출처 해시**다. 공통 모듈은 원 출처 파일 바이트를 가지고 있지 않으며 이 값을 원 파일에서 직접 다시 계산하거나 실제 게시일을 독립적으로 승인하지 않는다. 모델·문서·자료 성격·source 결합과 같은 source pin의 일관성을 확인한다. DATA는 운영 metadata를 승인할 때 원 파일/URL·버전·해시·locator·날짜 확인 방법과 증거를 별도로 남겨야 한다. 날짜를 확인하지 못했으면 null로 유지한다.

자료나 annotation의 내용이 바뀌면 새 버전/해시와 새 aggregate ID를 사용한다. 동일 annotation의 row/topic 순서만 바뀌었으면 같은 정규화·hash·ID·snapshot을 갖는다. 원본 sidecar의 승인 증빙과 원문 파일은 DATA 영역에 별도로 보존한다.

## 기간·분모·의무 경고

요청은 단일 model/source_kind와 승인 source 목록에 제한한다. 기간은 KST **[start_date,end_date_exclusive)**이고 시작<종료, 최대10년과 최대120월 bucket을 함께 검사한다. source/topic ID의 중복 입력은 오류이며 유효한 목록만 정렬한다.

| granularity | ID 예시 | 전체 경계 |
|---|---|---|
| month | `MONTH-2026-10` | 2026-10-01~2026-11-01 |
| season | `SEASON-2026-WINTER` | 2026-12-01~2027-03-01 |
| year | `YEAR-2026` | 2026-01-01~2027-01-01 |

봄3~5·여름6~8·가을9~11·겨울12~2다. 2027년1~2월은 겨울2026이다. bucket에는 전체 달력 경계를 기록하고 숫자는 요청 구간에 포함된 리뷰만 센다. 일부 기간이면 `partial_period=true`이며, 빈 bucket도 생략하지 않는다. 월/계절/연도와 topic은 공통 순서에 맞아야 한다.

제외 순서는 자료/모델 scope → 날짜 없음 → 요청 기간 밖 → scope 내부 중복이다. input=in_scope+scope밖, in_scope=날짜없음+기간밖+중복+유효 고유 리뷰를 대조한다. `unclassified_review_count`는 유효 고유 리뷰의 부분집합이다. 한 리뷰가 여러 topic을 가져도 분모는 유효 고유 리뷰 전체다. 분모0은 `ratio=null`, 분모>0·topic0은 `ratio=0`이다.

DATA collector는 `trend_sample_warnings(aggregate["buckets"])`가 반환한 문자열을 `warnings`에 포함해야 한다. 공통 검사는 누락을 거절한다. 0건은 “집계 가능한 리뷰가 없습니다”, 1~19건은 “표본이 적습니다”라는 기간별 문맥을 준다. 이는 통계적 유의성·실제 판매량·계절적 인과관계 주장이 아니다. 추가 한계 설명은 warnings 또는 최대800자 notes로 남긴다.

## private 조회·불변 저장

원래 작업실 인증·owner/viewer/admin 권한을 먼저 검사한다. viewer는 자기 principal의 GET 조회가 가능하며 타 작업실 접근은403이다. 응답에는 no-store를 적용하고 서버/collector의 원 오류 문자열과 비공개 상세는 외부에 반환하지 않는다.

- `GET /api/workspace/projects/{project_id}/review-trends`: 반복 `source_ids`/`topic_ids` query를 받고, 승인 collector 결과를 검증·저장한다.
- `GET .../review-trends/{aggregate_id}`: 해당 작업실에 저장된 동일 aggregate를 조회한다.
- `GET .../{aggregate_id}/evidence?bucket_id=&topic_id=&offset=0&limit=50`: 실제 membership의 canonical 원문을 조회한다. limit1~50, offset≥0이며 다음 페이지가 없으면 next_offset=null이다. 없는 집계/bucket/topic은404, 목록 끝 이후 offset은 원문 없는 정상 페이지다.

초기 성공 envelope는 `{ok:true,data:{aggregate,contract_version:"0.1.0"}}`, 원문 envelope는 공통 `WorkspaceTrendEvidenceResponse`다. 새 private MCP 도구는 `review_trends`, `get_review_trends`, `trend_evidence`이며 읽기·반복 안전·closed-world annotations를 사용한다. TypeScript 웹 클라이언트의 `reviewTrends`, `getReviewTrends`, `trendEvidence`도 같은 API를 호출한다. 기존 공개 합성자료3도구·공개 endpoint는 변경하지 않는다.

SQLite `workspace_review_trends`에는 aggregate·정규 metadata·완전 membership·당시 원문과 snapshot SHA를 저장한다. 동일 ID의 다른 결과는 덮어쓰지 않고 거절한다. 과거 aggregate/드릴다운은 저장된 당시 원문을 읽으므로 이후 live 자료가 바뀌어도 새 자료로 결과를 바꾸지 않는다. 기존 프로젝트에서 새 집계를 요청할 때 자료 drift는409로 거절한다.

기본 collector=None이면 유효한 요청도 **501 NOT_IMPLEMENTED**이며, fixture 숫자나 빈 성공 결과로 대체하지 않는다. DATA 승인/집계기 인수가 끝나기 전 운영 연결을 준비 완료로 표시하지 않는다.

## 다음 작업과 검증 상태

1. DATA148: 승인 날짜/분류 sidecar·결정적 집계·완전 membership을 구현하고 원본 확인 증빙과 함께 인계한다. 기존 CSV/importer·원문을 보존한다.
2. WEB149: 공통 클라이언트로 기간/제품/주제 선택·분모/제외/빈 구간·표본/부분 기간·그래프·원문 페이지 흐름을 연결한다. 501과 실패를 정상 그래프로 표현하지 않는다.
3. CORE150: 필수 판단 품질 보완 뒤 승인 원문을 기존 근거 경로로 연결한다. closed PlanningRequest에 임의 aggregate 필드를 추가하지 않는다.
4. PM152: 격리 테스트·CI·병합/통합 증빙을 기록하고 승인 collector를 명시적으로 연결한다. ChatGPT·Claude 계정에서 새 private 도구의 실제 발견/호출은 별도로 검증한다.

공용 fixture, Python 형식/의미 검사, API·저장·원문·MCP mock/SDK, 웹 계약/클라이언트 검사를 작성하고 인증 없는 Docker에서 전체1345(3 skip)·관련87·웹433+4/빌드·계약/하네스/지침·lint 통과를 확인했다. [PR156](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/156)의 실제 CI/브라우저/병합·운영 인수는 해당 PR과 운영 Issue28의 후속 checkpoint에서 확인한다. 수신증·입력 해시는 `evals/pm-intake/20261006/trends/verification.json`이다. SDK나 MockTransport 결과를 외부 ChatGPT/Claude 연결 성공으로 표현하지 않는다. 실제 호스트 연결·운영 날짜 승인·사용자 그래프·기획 Agent 전체 품질·제출 완성은 남아 있다.
