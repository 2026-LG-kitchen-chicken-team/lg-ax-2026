# 다섯 Skill의 offline 재실행과 호출 기록

승인 작업 P2-PM-004 / R23·R28의 로컬 호출 계약이다. 공통 응답 JSON과 기존 스키마는 유지하고 실행 기록을 별도 sidecar로 보존한다. 독립 평가 입력·정답을 포함하거나 읽지 않는다.

| Skill | 입력·개발 예시 | 판단과 Tool | 출력·보류 |
|---|---|---|---|
| [evidence_lookup](../../skills/evidence_lookup/SKILL.md) | query, model_id, document_version, limit / 해당 폴더 examples/input.json | DemoStore.search_evidence, 결정적 원문 조회 | items/total/sources; 빈 검색은 성공 |
| [need_extract](../../skills/need_extract/SKILL.md) | review_evidence_ids, 모델/버전 / 해당 폴더 examples/input.json | 등록한 추출 handler | needs/desired_outcomes/unresolved |
| [product_compare](../../skills/product_compare/SKILL.md) | needs/feature_ids/evidence_ids, 모델/버전 / 해당 폴더 examples/input.json | 등록한 대조 handler | gaps/unresolved; insufficient_evidence는 보류 |
| [concept_draft](../../skills/concept_draft/SKILL.md) | needs/gaps/constraints/max_concepts, 모델/버전 / 해당 폴더 examples/input.json | 등록한 콘셉트 handler | concepts/hold_reasons/no_candidate_reasons |
| [review_revision](../../skills/review_revision/SKILL.md) | needs/gaps/concepts/violations/changed_evidence_ids/revision_count, 모델/버전 / 해당 폴더 examples/input.json | 등록한 수정 handler, 수정 2회 상한 | 변경/근거/unresolved/revision_count |

각 SKILL.md에서 로컬 schemas/input.json·output.json, 개발 예시와 scripts/run.py를 연결한다. 실행 코드는 [SkillRuntime](../../packages/core/src/lgax_core/skill_runner.py), 공통 객체 원본은 [lgax.schema.json](../../packages/contracts/schemas/lgax.schema.json), handler 등록법은 [기존 실행 안내](../pm/skills.md)를 따른다. 기본 Runtime의 네 판단 handler는 미등록이며 `NOT_IMPLEMENTED`가 정상적인 현재 오류 결과다.

## Offline 실행

사전에 잠금 파일 기준으로 설치된 Python 3.11/uv 환경에서 저장소 루트에서 실행한다. offline은 의존성을 내려받지 않는 옵션이며 네트워크 차단 기능은 아니다. 아래 기본 실행기는 외부 모델을 호출하지 않는다.

```sh
uv run --offline --no-sync python skills/evidence_lookup/scripts/run.py --input skills/evidence_lookup/examples/input.json --output runtime/skills/evidence-001.json
uv run --offline --no-sync python skills/need_extract/scripts/run.py --input skills/need_extract/examples/input.json --output runtime/skills/need-001.json
uv run --offline --no-sync python skills/product_compare/scripts/run.py --input skills/product_compare/examples/input.json --output runtime/skills/compare-001.json
uv run --offline --no-sync python skills/concept_draft/scripts/run.py --input skills/concept_draft/examples/input.json --output runtime/skills/concept-001.json
uv run --offline --no-sync python skills/review_revision/scripts/run.py --input skills/review_revision/examples/input.json --output runtime/skills/review-001.json
```

조회는 종료 코드 0, 나머지 네 미구현 업무는 2를 기대한다. 코드 0은 envelope 성공이지 의미 품질 또는 보류 해제 판정이 아니다. 반복할 때 `-002` 등 새로운 파일명을 사용한다. 기본 기록 경로는 `OUTPUT.trace.json`이며 `--trace-output 새경로`로 바꿀 수 있다. 입력/출력/기록은 서로 다른 경로여야 하고 출력·기록의 기존 파일은 거부한다. 저장 실패는 stderr 오류와 코드 2이며 일부 파일이 생길 수 있으므로 두 파일이 모두 존재하고 서로 일치하는지 확인한다. 읽기/JSON 파싱 실패에는 `records:[]`와 `cli_error`를 남기며 실제 Skill 호출을 꾸미지 않는다.

## 기록 계약 v1

Python `runtime.execute(skill_id, payload)`의 반환 envelope는 그대로다. `runtime.records`는 실행마다 누적한 기록의 깊은 사본이다. 메모리에만 유지하므로 장기 보관은 호출자의 책임이며 CLI는 `{records:[...], cli_error:null}` 형태로 저장한다. 공유 Runtime의 동시 호출 순서·분산 저장·암호화·서명은 제공하지 않는다.

- `run_id`: 호출마다 UUID 기반 새 ID. `started_at`, `finished_at`: UTC 관측 시각.
- `input`, `input_sha256`: 스키마를 통과한 입력 사본과 정렬한 UTF-8 JSON의 SHA256. 스키마 오류 입력은 둘 다 null이다. 허용된 자유 텍스트의 개인정보는 자동 가림하지 않으므로 승인된 합성/비민감 입력만 사용한다.
- `tool`: 등록 backend_id/execution_kind와 `called`. `called`는 callback 진입을 뜻하며 내부 모델/HTTP 호출 횟수나 완료를 뜻하지 않는다. 미등록/입력 오류/수정 상한 거절은 false다.
- `stage`: input_validation → retry_validation → context_validation → handler_selection → revision_budget → handler_call → output_validation → completed 중 마지막 도달 단계. 완료 전 오류 위치도 보존한다.
- `decision`: `succeeded`, `held`, `failed`와 hold_reasons. unresolved/hold_reasons, Gap의 insufficient_evidence 또는 INSUFFICIENT_EVIDENCE 오류가 있으면 held다. 정상적인 후보 0개 사유만 있으면 succeeded다. 모델 내부 추론을 기록하거나 의미 품질을 판정하는 필드가 아니다.
- `output`, `error`: 검증된 반환 응답 사본과 오류 또는 null. 잘못된 handler 출력/원시 예외 본문은 저장하지 않는다.
- `retry_of`, `retry_count`, `automatic_retries`: 순차 명시 재시도 연결, 최초 0/추가 최대 2, 자동 재시도 0. `contract_version`과 `record_version`은 별개다.
- `trusted_collector_verified`: 항상 false. 로컬 기록은 인증된 실모델 증빙이 아니다.

## 명시 재시도와 수정 횟수

```python
response = runtime.execute("need_extract", payload)
previous_id = runtime.records[-1]["run_id"]
# 실제 실패/보류를 검토한 호출자가 같은 Runtime에서 명시적으로 요청한다.
response = runtime.execute("need_extract", payload, retry_of=previous_id)
```

같은 Skill·동일 입력의 실패/보류 기록만 연결할 수 있고 이전 run에서 분기하거나 추가 2회를 초과하면 handler 호출 없이 INVALID_ARGUMENT이다. 거부된 재시도 자체를 부모로 삼아 예산을 초기화할 수 없다. 입력을 바꾸면 별도 신규 실행이다. Runtime 재생성/신규 실행을 통한 전역 예산 관리는 상위 Agent 책임이다. CLI의 새 프로세스는 신규 실행이며 이전 파일을 신뢰해 retry 이력을 복원하지 않는다. handler 내부 재시도는 Runtime 계수에 포함되지 않으므로 collector에서 별도 계측한다. `revision_count`는 업무 수정 횟수이며 전송/호출 재시도와 구분한다. 2회 수정 입력에는 callback을 호출하지 않고 보류한다.

## 검증과 남은 실모델 근거

```sh
uv run --offline --no-sync python -m unittest discover -s tests -p test_skill_runner.py -v
uv run --offline --no-sync python -m unittest discover -s tests -p test_model_client.py -v
```

단위검사는 합성 자료와 명시 fixture/모의 transport로 성공·실패·보류·재시도·기존 출력 스키마 호환과 파일 보존을 확인한다. 실제 모델/시장 성능을 입증하지 않는다.

trusted collector는 별도 승인 환경에서 다섯 Skill의 실제 반복 호출 및 실패를 run ID로 연결하고, 작동 코드 commit/파일 hash·자료 pack hash와 모델/문서 버전·선택 adapter·모델 digest·설정·원 응답·전체 모델 호출/내부 재시도·측정값을 직접 수집/대조해야 한다. backend_id/live_model 선언이나 로컬 sidecar만으로 verified를 부여하지 않는다. 이 구현은 collector 실행·네 판단 handler 연결·실모델 반복 성공·부모 P2-PM-004 완료·Project 변경을 수행하지 않는다.
