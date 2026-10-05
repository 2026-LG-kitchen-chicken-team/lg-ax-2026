# 다섯 업무 Skill의 offline 재실행 계약

P2-PM-004, R23·R28의 로컬 실행 기록이다. 응답 envelope와 canonical 스키마를 변경하지 않는다. 독립 정답은 포함하지 않는다.

| Skill | 개발 입력·판단/Tool | 출력·보류 |
|---|---|---|
| [evidence_lookup](../../skills/evidence_lookup/SKILL.md) | query, 모델/버전, limit → DemoStore.search_evidence | items/total/sources; 빈 결과는 정상 성공 |
| [need_extract](../../skills/need_extract/SKILL.md) | review_evidence_ids, 모델/버전 → 추출 handler | needs/desired_outcomes/unresolved |
| [product_compare](../../skills/product_compare/SKILL.md) | needs/feature_ids/evidence_ids, 모델/버전 → 대조 handler | gaps/unresolved; insufficient_evidence는 held |
| [concept_draft](../../skills/concept_draft/SKILL.md) | needs/gaps/constraints/max_concepts → 콘셉트 handler | concepts/hold_reasons/no_candidate_reasons |
| [review_revision](../../skills/review_revision/SKILL.md) | needs/gaps/concepts/violations/changed_evidence_ids/revision_count → 수정 handler | changes/unresolved/revision_count; 2회 수정 뒤 보류 |

각 SKILL.md의 schemas/input.json·output.json과 examples/input.json은 계약 및 개발 예시다. scripts/run.py는 [SkillRuntime](../../packages/core/src/lgax_core/skill_runner.py)을 호출하며 [canonical 계약](../../packages/contracts/schemas/lgax.schema.json)의 객체 정의를 재사용한다. [handler 등록 안내](../pm/skills.md)와 연결된다. 기본 runtime에는 조회만 등록되어 있다. 나머지 네 업무는 NOT_IMPLEMENTED 오류이며 fixture 등록은 실모델 구현을 의미하지 않는다.

## 재실행

잠금 파일 기준으로 의존성이 이미 설치된 Python 3.11/uv 환경, 저장소 루트에서 실행한다. offline 옵션은 다운로드를 막지만 네트워크 격리 기능은 아니다. 기본 CLI는 외부 모델을 호출하지 않는다.

```sh
uv run --offline --no-sync python skills/evidence_lookup/scripts/run.py --input skills/evidence_lookup/examples/input.json --output runtime/skills/lookup-001.json
uv run --offline --no-sync python skills/need_extract/scripts/run.py --input skills/need_extract/examples/input.json --output runtime/skills/need-001.json
uv run --offline --no-sync python skills/product_compare/scripts/run.py --input skills/product_compare/examples/input.json --output runtime/skills/compare-001.json
uv run --offline --no-sync python skills/concept_draft/scripts/run.py --input skills/concept_draft/examples/input.json --output runtime/skills/concept-001.json
uv run --offline --no-sync python skills/review_revision/scripts/run.py --input skills/review_revision/examples/input.json --output runtime/skills/review-001.json
```

조회는 종료 0, 기본 미등록 네 업무는 2다. 반복 실행에는 새 파일명을 쓴다. 결과와 `OUTPUT.trace.json`을 함께 보존한다. `--trace-output 새경로`로 기록 경로를 정할 수 있다. 입력/출력/기록은 모두 달라야 하며 기존 출력·기록은 덮어쓰지 않는다. 저장 실패는 stderr 오류/종료 2이며 일부 파일이 남을 수 있다. 두 파일의 존재와 기록의 output 일치를 확인해야 저장 완료다.

## 기록 v1

`execute(skill_id, payload, retry_of=None)`는 기존 envelope를 반환한다. `runtime.records`는 누적 기록의 깊은 사본이며 메모리에만 존재한다. CLI는 `{records: [...], cli_error: null}` sidecar를 쓴다. 공유 runtime 동시 실행·분산 저장·서명·암호화를 제공하지 않는다.

- run_id는 호출별 새 UUID이며 started_at/finished_at은 UTC 시각이다. contract_version과 record_version을 구분한다.
- input/input_sha256은 스키마 검사 및 정렬 UTF-8 JSON 직렬화가 모두 성공한 입력과 그 바이트의 SHA256이다. 실패 시 둘 다 null이다. 자유 텍스트의 민감정보를 자동 가림하지 않으므로 승인된 비민감 개발 자료만 사용한다.
- 단독 surrogate(예: query의 `\ud800`)는 JSON 파싱·스키마 검사를 통과하더라도 UTF-8 인코딩에서 INVALID_ARGUMENT이다. input_validation 단계, failed, tool.called=false, 해당 run ID와 오류 envelope를 보존한다. 원 입력이나 원 예외 메시지를 저장하지 않는다.
- tool은 backend_id/execution_kind 등록 선언과 called를 남긴다. called는 callback 진입이며 내부 모델 호출 횟수·완료 증거가 아니다.
- stage는 input_validation, retry_validation, context_validation, handler_selection, revision_budget, handler_call, output_validation, completed 중 마지막 단계다.
- decision.status는 succeeded/held/failed다. unresolved/hold_reasons, Gap insufficient_evidence, INSUFFICIENT_EVIDENCE 오류는 held다. 정상 후보 0개 사유만 있으면 succeeded다. 모델 내부 추론이나 의미 품질 판정은 기록하지 않는다.
- output/error는 반환 응답 사본과 오류 또는 null이다. 검증 실패한 handler 원 출력과 임의 예외 본문은 남기지 않는다.
- retry_of/retry_count/automatic_retries는 명시 재시도 연결·최초 0/추가 최대 2·자동 재시도 0이다. trusted_collector_verified는 항상 false다.

파일 읽기/JSON 파싱 실패만 records=[] 및 cli_error로 남긴다. execute가 처리한 실패는 records에 실행 기록이 존재하며 cli_error=null이다. CLI 저장 JSON은 ASCII escape로 UTF-8 안전하게 쓰며 JSON으로 읽은 내용은 동일하다.

## 실패 후 명시 재시도

```python
response = runtime.execute("need_extract", payload)
prior = runtime.records[-1]["run_id"]
response = runtime.execute("need_extract", payload, retry_of=prior)
```

같은 runtime의 동일 Skill·동일 입력 실패/보류만 순차 연결한다. 모르는 ID·입력 변경·성공 run·분기·추가 2회 초과·거부된 재시도에서 예산 재시작은 INVALID_ARGUMENT이며 Tool을 호출하지 않는다. 입력 변경은 새 실행으로 취급한다. 새 runtime/새 CLI 프로세스는 이력을 복원하지 않으므로 전역 예산은 상위 Agent 책임이다. 업무 revision_count는 별도이며 2회 수정 입력은 호출 전 보류한다. handler 내부 재시도는 별도 collector 계측이 필요하다.

## 검증 범위

```sh
uv run --offline --no-sync python -m unittest discover -s tests -p test_skill_runner.py -v
uv run --offline --no-sync python -m unittest discover -s tests -p test_model_client.py -v
```

개발 예시·합성자료·fixture로 성공/실패/보류/회복·재시도 상한·Python/CLI surrogate 오류 기록 보존을 확인한다. 단위 검사로 부모 완료를 판정하지 않는다. trusted collector는 별도 승인 환경에서 실제 모델 반복 실행, 실행 코드 commit/hash, 자료 pack/hash·모델/문서 버전, 선택 adapter/model digest/설정, 원 응답·전체 호출/재시도와 측정을 직접 검증해야 한다. 로컬 기록과 live_model 선언은 그 증거를 대신하지 않는다.
