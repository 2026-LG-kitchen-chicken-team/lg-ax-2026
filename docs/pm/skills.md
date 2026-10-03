# 다섯 업무 Skill 실행 계약

2026-10-04, P2-PM-004의 실행 패키지 작업. 신청서의 다섯 업무를 재사용 가능한 문서·입출력 규격·실행 진입점으로 구성한다. **패키지 구성과 실제 판단 기능 완성을 구분한다.**

| 업무 ID / 폴더 | Skill 이름 | 현재 실제 실행 |
|---|---|---|
| `evidence_lookup` | `evidence-lookup` | DemoStore의 원문 조회·모델/문서 버전 필터 |
| `need_extract` | `need-extract` | 판단 handler 미등록: `NOT_IMPLEMENTED` |
| `product_compare` | `product-compare` | 판단 handler 미등록: `NOT_IMPLEMENTED` |
| `concept_draft` | `concept-draft` | 판단 handler 미등록: `NOT_IMPLEMENTED` |
| `review_revision` | `review-revision` | 판단 handler 미등록: `NOT_IMPLEMENTED` |

폴더와 코드 ID는 신청서의 underscore 표기를 유지한다. SKILL.md의 이름은 Skill 작성 지침의 소문자·hyphen 규칙을 따른다. 각 폴더에는 필수 `SKILL.md`, 독립 JSON Schema `schemas/input.json`·`output.json`, 실행 가능한 `scripts/run.py`, 구조화 입력 예시가 있다. 조회의 `expected-output.json`과 나머지 네 업무의 `expected-error.json`은 현재 실행기로 재현하는 결과다. 예시의 Need·Gap은 직접 작성한 입력 fixture이며 실제 판단 결과가 아니다.

## 호출과 오류

```powershell
uv run python skills/evidence_lookup/scripts/run.py --input skills/evidence_lookup/examples/input.json --output runtime/skills/evidence_lookup.json
uv run python skills/need_extract/scripts/run.py --input skills/need_extract/examples/input.json --output runtime/skills/need_extract.json
```

나머지도 같은 명령의 폴더 이름만 바꾼다. 종료 코드 `0`은 등록된 handler의 실행 성공, `2`는 출력 JSON의 오류다. 유효한 빈 조회는 성공이며, 잘못된 ID·없는 문서 버전·미등록 업무와 구별한다. 입력 파일은 UTF-8 JSON이며 비밀키를 받지 않는다. 저장 위치는 호출자가 지정하고 CLI는 외부 API나 모델을 암묵적으로 호출하지 않는다. 입력·출력이 같은 파일이면 원본을 보존하고 stderr의 오류 JSON과 종료 코드 2를 반환한다.

`SkillRuntime.execute(skill_id, payload)`는 API/MCP에서 사용할 수 있는 동일한 envelope를 반환한다.

```json
{"ok": true, "data": {
  "skill_id": "evidence_lookup", "contract_version": "0.1.0",
  "execution_kind": "deterministic", "backend_id": "demo-store:literal-token-count",
  "model_id": "FRIDGE-A", "document_version": "1.0", "source_kind": "synthetic",
  "result": {"query": "청소", "items": [], "total": 0, "search_method": "literal_token_count"},
  "sources": []
}}
```

위 JSON은 형식 설명이며 해당 검색어의 실제 실행 결과가 아니다. 오류는 기존 `{ok:false,error:{code,message,details}}` 형식을 쓴다. `catalog()`는 다섯 업무의 등록 여부·backend ID·execution kind를 보여주며 미등록은 `NOT_IMPLEMENTED`다.

모든 입력은 `model_id`·`document_version`을 요구한다. 업무별 추가 입력과 결과는 폴더의 스키마가 기준이다.

| 업무 | 추가 입력 | 결과 |
|---|---|---|
| evidence_lookup | query, 선택적 limit(1~50) | 원문 items·전체 일치 수·조회 방식 |
| need_extract | review_evidence_ids | canonical Need·need_id별 희망 결과·미해결 |
| product_compare | needs·feature_ids·evidence_ids | canonical Gap·미해결 |
| concept_draft | needs·gaps·constraints·선택적 max_concepts(1~3) | canonical Concept·보류 사유 |
| review_revision | needs·gaps·concepts·violations·changed_evidence_ids·revision_count(0~2) | 수정 객체·변경 이유/근거·미해결·수정 횟수 |

공통 타입은 `packages/contracts/schemas/lgax.schema.json`의 정의를 재사용한다. `schema_for()`는 필요한 정의만 포함한 독립 스키마를 생성한다. 공통 계약이 바뀌면 이 함수의 최신 결과로 폴더 스키마를 갱신하고 호환 검사를 수행한다. 지금의 canonical Need에 없는 희망 결과는 `desired_outcomes`에서 need_id와 연결한다. 후속 판단 담당자의 공통 계약 변경은 PM 검토와 마이그레이션을 거친다.

## 후속 실제 handler 연결

```python
from lgax_core.skill_runner import SkillRuntime

runtime = SkillRuntime(store=authorized_store)
runtime.register_handler(
    "need_extract", actual_backend.extract_needs,
    backend_id="확인한 모델/서비스 버전", execution_kind="live_model",
)
response = runtime.execute("need_extract", payload)
```

handler는 `(payload의 사본, store)`를 받고 **업무별 result 객체만** 반환한다. envelope·원천·실행 종류는 Runtime이 붙인다. JSON 입력으로 import 경로나 handler를 선택하지 않는다. 기존 handler 교체는 명시적 `replace=True`를 요구한다. 테스트용 주입은 반드시 `execution_kind="fixture"`로 등록한다. 등록 문자열만으로 실제 모델 호출이 입증되지는 않으며 후속 구현은 원시 모델 응답·revision·지연·사용량·실패와 실행 로그를 남겨야 한다.

현재 Runtime의 저장소 계약은 읽기 전용 DemoStore이며 합성 원천만 지원한다. 실제/비공개 자료 저장소 연결을 완료했다고 보고하지 않는다. 루트 프로젝트 API의 권한·공동 실행/이력은 별도 작업이고 이 CLI는 이를 우회하여 웹 사용자 권한으로 동작하는 경로가 아니다.

입력과 출력 스키마를 검사하고 근거의 원문 ID·모델·문서 버전·원문 위치를 저장소와 대조한다. 조회 결과 원문 변조, 입력에 없는 근거, 잘못된 Need/Gap 참조와 기능 모델/버전 혼용을 거절한다. 결과 `sources`는 실제 저장소의 원문을 반환한다. 수정은 최대 두 번이며 그 후 등록된 수정 handler를 호출하지 않고 보류한다. 이 검사는 의미적 정확성·기존 기능과 불편의 관계·신규성·시장 수요·제조 가능성을 증명하지 않는다.

## 남은 완료 조건

네 판단 handler의 실제 구현·실제 모델 실행, 다섯 업무를 연결한 반복 실행, 세 제품 시나리오·오류와 명세 변경 대응, 실행/수정 이력·재시작 재현은 남아 있다. 따라서 **P2-PM-004 전체 acceptance와 참가작 31요구 완료를 이 패키지로 주장하지 않는다.** 검증 결과와 작업 완료 판정은 후속 run에 별도로 기록한다.

## 패키지 검증

`uv run python -m unittest discover -s tests -p test_skill_runner.py -v`로 실제 조회·유효한 빈 결과·잘못된 ID·원문/모델/버전 검증·미구현 응답·fixture 구분·출력 규격·참조·후보 상한·수정 상한·CLI 원본 보존을 검사한다. 10/4 이 패키지의 21개 검사가 통과했고 담당 Python 파일의 Ruff 검사도 통과했다. 다섯 CLI를 임시 출력 폴더에서 실행하여 예시 결과와 일치함을 확인했다(조회 정상, 나머지 네 업무 `NOT_IMPLEMENTED`).

Skill 작성 지침의 `quick_validate.py`로 다섯 SKILL.md의 frontmatter와 이름을 확인했다. 이는 실제 판단 handler·모델 품질·Agent 완주의 검증을 대신하지 않는다. 이 작업의 상세 코드/입력/실행 근거는 PM의 공통 작업 기록과 후속 run에 연결한다.
