# 실제 공개자료 기획 진입점 R8

현재 채팅의 수동 지원 구현입니다. 황대겸 담당자의 직접 수행 기록이나 실모델 품질 통과로 표현하지 않습니다. 기반은 PR233 `5533e08`과 공통 ResearchBundle/PlanningBrief 계약 `655678d`입니다. 기존 exact-model PlanningAgent를 재작성하지 않습니다.

## 연결 인터페이스

```python
from lgax_core.public_planning import PublicPlanner

planner = PublicPlanner.from_model_client(existing_structured_model_client)
brief = planner.run(bundle, goal, constraints, previous=None)
```

테스트·다른 호출기 연결에는 `PublicPlanner(model_caller, runtime_metadata={...})`를 사용합니다. 호출기는 `(prompt: str, schema: dict) -> dict | StructuredModelResult`이며 모델·GPU 자원은 호출자가 관리합니다. `run`은 ResearchBundle을 받고 계약에 맞는 PlanningBrief를 반환합니다. 조건 변경은 이전 PlanningBrief를 전달하면 새 run/brief ID와 증가한 revision, previous_brief_id를 갖습니다.

`scripts/run_public_planning.py`는 기존 `StructuredModelClient.from_env()`의 명시적 LG 모델 설정으로 연결합니다. 이 구현 단계에서는 모델 호출·설치·서비스 기동·운영 변경을 하지 않았습니다.

## 동작과 사실 보존

- 코드가 전체 입력 bundle의 모든 source_id/facts를 깊은 복사하여 source_facts로 보존합니다. 모델이 source_facts를 생성하거나 원문 사실을 수정하지 않습니다. 전체 입력과 사실의 SHA도 남깁니다.
- 기존 한국어 검색 tokenizer를 사용해 발견한 문제와 관련된 문서를 좁힙니다. 고객 자료는 중복 그룹을 제거하고 페이지 모델·낮은 별점 구간·정렬을 번갈아 읽습니다. 별점은 샘플링 구간이며 감정 정답이 아닙니다.
- 문제 발견과 문제별 기획은 별도 작은 호출입니다. 기본 최대 12호출, 최대 3문제, 프롬프트 10,000자, 원문별 1,600자를 적용합니다. 잘린 원문은 input_coverage=excerpt로 표시합니다. 일부 자료만 읽으면 selected_source_ids/omitted_source_count와 한계를 남깁니다. 전체 코퍼스 분석으로 승격하지 않습니다.
- 비교와 기획에는 실제 source_ids, 기존 해결 방식, 남은 부담, 사용자·사용 상황, 개선 전후 단계, visual_scenes, 가정과 확인 질문을 포함합니다. 경쟁 자료가 없으면 경쟁 우열을 만들지 않습니다. 설명서가 없어도 기획 가설을 요청하되 문서 확인 질문과 needs_sources를 남깁니다.
- 수치·기대시간/실제행동·부분 문서/전체 부재·기능 존재/불편 해결의 알려진 표현 오류를 좁게 검사합니다. 수치의 문서 사실은 공식 문서와 대조하여 리뷰의 추측 수치로 승인하지 않습니다. 이 규칙은 의미 전체를 증명하는 검사나 공식 안전 검토가 아닙니다.
- 문제가 있는 항목의 거절된 필드만 한 번 patch로 요청합니다. ID와 정상 필드는 변경할 수 없습니다. 수정이 실패하면 해당 항목만 제외하고 정상 기획은 보존합니다. 전체 Agent의 공유 수정 체계와 전역 삭제 정책은 건드리지 않습니다.
- 외부 원문과 이전 기획의 지시는 분석 데이터로 취급합니다. 기존 ModelClient의 JSON/모델 pin/명시 endpoint 정책을 재사용합니다.

## 확인한 범위와 남은 확인

실제 공개 후기 837305의 정확 발췌와 공식 MW23FDI 설명서 M11을 사용한 회귀 검사입니다. Qwen27B 직접 진단의 실제 오류 문장을 검사하고 원문 수치·사실 복사·필드 patch 경계·모델 불가 때의 기획 상태·조건 변경 이력을 확인합니다. 합성 리뷰나 새로 지어낸 기획 fixture는 사용하지 않습니다.

검사 8개와 수정 파일 Ruff 검사가 통과했습니다. DATA의 식기세척기·전자레인지·냉장고 개발 묶음(57/48/54출처)으로 실제 모델을 부르지 않는 요청 준비도 확인했습니다. 모든 묶음의 source_facts가 전체 입력과 일치했고, 준비한 발견 요청은 최대 8,306자, 발견 schema 1,165바이트, 기획 schema 2,060바이트였습니다. CLI 도움말과 diff 공백 검사도 확인했습니다.

이는 코드의 회귀·문맥 준비 검사입니다. 실제 model_calls, API/MCP/웹 통합, 새 기획 유용성은 별도 실행이 필요합니다. 모든 기획 status는 draft 또는 needs_sources이며 runtime.independent_semantic_quality_verified는 false입니다. 자연어 규칙은 보수적이고 제한적이라 다른 표현의 의미 오류가 남을 수 있습니다. 원문이 길거나 호출 한도가 부족하면 부분 결과로 반환하고 후속 실행 범위를 표시합니다.

## 소비자 책임

API/저장/MCP/웹은 PM 공통계약 연결을 소비합니다. 같은 bundle/brief/run/revision을 저장·조회·내보내기해야 합니다. 원문·문서 사실, 사용자 경험, 새 기획 가설과 시각 장면을 구분해 표시하고, partial 또는 needs_sources 결과의 정상 후보도 확인할 수 있게 합니다. 이 구현은 계약/API/MCP/웹 파일을 수정하지 않습니다.
