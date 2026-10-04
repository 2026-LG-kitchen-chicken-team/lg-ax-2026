# PM005: 실제 결과 수집과 A/B 검토 준비

`scripts/prepare_evaluation.py`는 **이미 외부에서 실행한 두 결과 묶음**을 대조하고 방식 이름을 가린 검토 파일을 만든다. 모델·Agent를 실행하거나 점수·승자·성능 개선을 산출하지 않는다. 현재 기획 Agent의 의미 분석·생성 백엔드는 미구현이며, 이 준비 도구만으로 P2-PM-005·E02·E03을 완료 처리하지 않는다.

검증 범위는 실제 파일 해시와 두 묶음의 선언된 실행 조건 일치다. 파일에 `live_model`이라고 적는 것만으로 실제 호출·독립 사례·강한 프롬프트가 입증되지는 않는다. PM은 원시 실행 기록, 모델 응답, 호출·재시도·설정과 자료 전달을 별도로 대조해야 한다. 테스트의 가짜 결과는 도구 검증용이며 실제 평가 증빙이 아니다.

## 1. 독립 사례 manifest

코어·자료 담당자가 개발 예시와 분리한 평가 사례를 먼저 제공한다. 최소 여섯 유형을 모두 포함하며, 사례 수·반복 횟수는 고정하지 않는다. 추가 반복은 고유한 `case_id`로 구분한다. 현재 도구는 여섯 유형의 완비만 검사하며 사례 내용의 독립성·난도·정답 타당성은 사람이 확인한다.

| category | 검증할 상황 |
| --- | --- |
| `normal` | 정상 요청 |
| `duplicate_feature` | 기존 기능과 중복되는 제안 |
| `model_version_confusion` | 제품 모델·문서 버전 혼동 |
| `conflicting_reviews` | 서로 상충하는 고객 리뷰 |
| `missing_evidence` | 판단에 필요한 근거 누락 |
| `specification_change` | 명세 변경에 따른 재검토 |

manifest의 정확한 필드는 다음과 같다. 아래는 **형식 설명용 일부 항목**으로 실행 가능한 여섯 사례 파일이 아니다.

```json
{
  "schema_version": 1,
  "independent_from_development": true,
  "cases": [
    {
      "case_id": "EVAL-01",
      "category": "normal",
      "request": {"product_group": "fridge", "improvement_task": "독립 평가 요청"},
      "data_path": "materials/EVAL-01-data.json",
      "output_contract_path": "materials/planning-output.schema.json"
    }
  ]
}
```

자료·출력 계약 경로는 manifest 파일 위치 기준이다. 자료 SHA256와 출력 계약 SHA256는 파일의 **원래 바이트**에서 계산한다. 요청 SHA256와 프롬프트 SHA256는 아래 규칙을 적용한 JSON의 UTF-8 바이트에서 계산한다. 문자열 프롬프트도 문자열을 JSON으로 인코딩한다. 같은 자료를 의미상 비슷하게 다시 쓰거나 일부만 제공한 경우 같은 조건으로 인정하지 않는다.

```python
json.dumps(value, ensure_ascii=False, sort_keys=True,
           separators=(",", ":"), allow_nan=False).encode("utf-8")
```

같은 요청·자료집·제품/문서 버전·출력 계약을 두 방식에 제공한다. Agent는 전체 자료집을 도구로 조회할 수 있게 하고 기준선에는 전체 자료를 프롬프트에 넣는다. 전체 자료가 모델 문맥 한도를 초과하면 먼저 공통 평가 자료집을 조정한다. 기준선 자료만 잘라서 비교하지 않는다. 잘못된 모델/버전 사례에서는 잘못된 입력까지 양쪽에 똑같이 제공한다.

## 2. 외부 결과 계약

두 JSON 묶음의 루트는 `{ "schema_version": 1, "method": ..., "records": [...] }`다. `--agent-results`의 method는 `agent`, `--baseline-results`는 `single_prompt_baseline`이어야 한다. 각 묶음에 manifest의 모든 `case_id`가 정확히 한 번 있어야 한다. 성공 결과만 추려 넣지 않고 실패도 포함한다.

각 record의 필드는 아래와 같다. 명시된 모든 필드가 필요하며 알 수 없는 측정치는 `null`로 쓴다.

```json
{
  "case_id": "EVAL-01",
  "execution_kind": "live_model",
  "status": "success",
  "conditions": {
    "request_sha256": "<canonical request SHA256>",
    "data_sha256": "<actual data file SHA256>",
    "output_contract_sha256": "<actual output contract file SHA256>",
    "model": {"id": "<exact model ID>", "revision": "<pinned revision>", "digest": null},
    "sampling": {"temperature": 0, "seed": 42},
    "output_budget": {"max_output_tokens_per_call": 4096, "total_output_tokens_limit": null},
    "environment": {
      "provider": "<provider>", "host": "<same endpoint identity>", "runtime": "<version>",
      "context_tokens": 8192, "adapter": "<same adapter>", "constraint_mode": "<same output constraint>"
    },
    "data_access": {
      "pool": "entire_case_dataset", "availability": "all_materials_available", "truncation": "none"
    },
    "measurement_scope": "whole_request_including_all_model_calls_and_retries"
  },
  "method_setup": {
    "prompt": "<actual recorded prompt, or JSON messages array/object>",
    "prompt_sha256": "<canonical prompt SHA256>",
    "instructions_complete": true,
    "material_delivery": "tool_access",
    "call_policy": "agent_orchestration"
  },
  "raw_output": "<unmodified result; JSON object/array also permitted>",
  "raw_error": null,
  "execution_trace": [],
  "measurements": {
    "latency_ms": null, "input_tokens": null, "output_tokens": null,
    "model_calls": null, "tool_calls": null, "cost": null, "modification_seconds": null
  }
}
```

해시 자리표시는 실제 64자리 소문자 해시로 바꾼다. model에는 정확한 ID와 `revision` 또는 `digest`가 최소 하나 필요하다. 고정된 버전을 제공하지 않는 외부 서비스라면 현재 계약의 엄격한 버전 비교를 충족했다고 주장할 수 없다. 적절한 snapshot ID/버전 증빙을 확보하거나 평가 조건을 별도로 합의해야 한다. 사용자 플랜 이름은 모델 버전이 아니다.

`conditions` 전체를 양쪽에 동일하게 기록한다. `sampling`에는 실제 사용한 모든 샘플링 설정, `environment`에는 비교에 영향을 주는 provider/host·런타임·양자화·GPU 구성과 실제 문맥 길이·어댑터·출력 형식 제약 방식을 넣는다. 문맥 길이는 위 예시처럼 `environment.context_tokens`에 기록한다. 새 최상위 조건 필드를 추가하는 방식은 현재 준비 도구의 계약과 맞지 않는다. 도구는 설정값의 누락이 현실적으로 타당한지 판단하지 못한다. 프롬프트·도구 사용 방식은 서로 다르므로 `method_setup`은 동일할 필요가 없다.

실제 호출의 샘플링·출력 예산·문맥 길이를 양쪽에 동일하게 적용하고 원시 요청·응답과 대조한다. 위 예시의 seed 42·출력 4096·문맥 8192는 기록 형식 설명이며 최종 평가의 권장 설정이나 충분성 증거가 아니다. 미지정 seed를 42로 기록하거나 미측정 값을 추정해 채우지 않는다. 동일 자료 전체를 양쪽이 사용할 수 있어야 하고, 기준선의 전체 prompt·schema·답변이 실제 문맥 한도에 들어가는지 별도로 확인한다. 설정값 일치만으로 자료가 잘리지 않았다고 판단하지 않는다.

기준선의 `material_delivery`는 `full_prompt`, `call_policy`는 `single_prompt`다. [강한 단일 프롬프트 초안](../../evals/phase2/baseline-prompt.md)을 실제 결과 계약·독립 자료에 맞게 채우고 고정한다. PM이 실제로 충분한 지시문·자료·동일한 결과 요구를 제공했는지 확인한다. Agent의 계획·반복 도구 호출을 기준선에 복제하지 않는다. 프롬프트 강도 자체를 자동 점수화하지 않는다. 최초 프롬프트는 `method_setup.prompt`에 원문으로 남기고, 후속 모델 호출·도구·host 재시도는 `execution_trace`에 원시 기록을 남긴다. 기록이 없는 경우 `[]`를 허용하지만 실제 호출 입증은 미완료다.

출력 예산은 실험 전에 충분하게 고정한다. [모델 어댑터](model-adapters.md)의 직접 Ollama는 SDK `ModelConfig(max_output_tokens=..., context_tokens=...)`, `from_env()`의 `LGAX_MODEL_MAX_OUTPUT_TOKENS`/`LGAX_MODEL_CONTEXT_TOKENS`, CLI `--max-output-tokens`/`--context-tokens`로 설정한다. 모두 기본 출력 256·문맥 4096이며 같은 범위를 검사하고, CLI는 환경변수를 읽지 않는다. Lab은 출력 256·문맥 4096만 허용하고 다른 조합을 거절한다. 긴 기준선 답변에 기본 256을 그대로 적용하면 기준선만 잘릴 수 있으므로 충분한 예산을 선택해 양쪽 조건을 다시 고정해야 한다.

성공 결과의 `metadata.generation_settings`와 원시 요청에서 출력·문맥·샘플링 설정을 대조하고, 각 호출의 종료 이유를 `execution_trace`에 보존한다. 직접 Ollama의 `done_reason=length`는 `output_truncated` 실패이며 성공으로 집계하지 않는다. Lab은 종료 이유를 제공하지 않아 `done_reason=null`이다. Lab의 seed도 미지정인데 직접 Ollama는 42이므로, 현재 두 어댑터를 교차 사용하는 것만으로 샘플링·형식 제약이 동일한 평가를 충족하지 않는다. 동일한 생성 경로·설정으로 맞추거나 차이를 명시해 별도 실험으로 관리한다. `total_output_tokens_limit: null`은 공통 총량 상한이 없다는 뜻이며 미측정 토큰 수와 다르다. 총량 상한을 쓰면 양쪽에 동일하게 적용하고 실제 실행기가 집행해야 한다.

측정은 요청 전체를 대상으로 한다. Agent 다중 호출·host 재시도·실패한 모델 호출을 포함한 토큰·지연·호출 수·비용을 합산한다. `model_calls`는 재시도를 포함한 모델 요청 수, `tool_calls`는 모델 호출을 제외한 도구 실행 수다. 비용을 측정했으면 `cost`는 `{ "amount": 0.12, "currency": "USD" }` 형태다. 양쪽 비용 통화가 다르면 거부한다. 미확인 비용·수정 시간은 `null`, 실제 측정 결과가 0인 경우만 0이다. human 수정시간은 동일한 수정 목표·시작/종료 기준으로 별도 기록한다.

실패 record는 `status: "failure"`와 `raw_error` 원문을 반드시 포함한다. 부분 출력은 `raw_output`에 그대로 보존한다. 실패를 성공으로 바꾸거나 파일에서 지우지 않는다. 합성 입력 자료에서 **실제 모델이 실행**됐다면 `live_model`이지만, 미리 적어 놓은 출력은 `fixture`다. 두 방식을 섞거나 한 묶음 안에서 fixture/live를 섞으면 거부한다. 준비 도구는 이 실행 종류 선언의 진실 여부를 확인하지 못한다.

## 3. PM 실행 방법과 검토 파일

실제 독립 사례와 두 실행 결과를 확보한 뒤 프로젝트 루트에서 실행한다. 아래 경로는 향후 수집 위치 예시이며 해당 파일들이 현재 존재한다고 뜻하지 않는다.

```powershell
python scripts/prepare_evaluation.py --cases private/evaluation/run-001/cases.json --agent-results private/evaluation/run-001/agent.json --baseline-results private/evaluation/run-001/baseline.json --output-dir private/evaluation/review-001 --key-file private/evaluation/pm-keys/review-001.json --seed 20261004
```

결과 경로는 매번 새로 지정한다. 기존 출력 폴더·PM 키가 있으면 덮어쓰지 않고 거부한다. 입력 검사가 끝나기 전에 산출물을 만들지 않으며, 쓰기 중 디스크 오류 등이 생기면 일부 파일이 남을 수 있다. 일부 산출물은 배포하지 말고 새 경로로 재시도한다.

| 산출물 | 전달 대상·용도 |
| --- | --- |
| `review.json` | 독립 검토자: 공통 요청·자료 해시·A/B 원문·실패 원문 |
| `scorecard.json` | 독립 검토자: 인용 확인 수/정확 수, 제품 모델 오류, 기능 중복 제안 수, 수정 시간, 메모의 빈 기록표 |
| `preparation.json` | 준비 상태·여섯 유형별 사례 수. 평가 완료 여부는 항상 false |
| 별도 `--key-file` | PM만 보관: seed·방식 매핑·실행 조건·프롬프트·측정치·원시 실행 기록·입력 파일 해시 |

검토자에게는 위 세 파일과 **원래 사례 자료·출력 계약**을 함께 전달한다. 별도 PM 키와 Agent/baseline 원래 결과 파일은 전달하지 않는다. seed도 PM 키에만 남긴다. 같은 seed·같은 입력이면 사례 순서와 각 사례의 A/B 배치가 재현된다. 프롬프트·측정치·실행 로그는 방식 추측을 줄이기 위해 가린 파일에서 제외된다.

가림은 **방식 라벨에 한정**된다. 원문이 스스로 Agent라고 말하거나 오류에 실행기 이름이 있으면 방식이 드러날 수 있다. 원문을 바꿔서 숨기지는 않는다. PM은 검토 전에 해당 한계를 확인하고 기록한다. 단순 라벨 가림을 완전한 이중 맹검으로 표현하지 않는다. raw 자료에 개인정보·비밀이 있을 수 있으므로 공유 범위는 별도로 확인하고 현재 수집 위치는 Git 제외 `private/`를 사용한다.

`fixture` 준비 상태는 `fixture_only`, `live_model` 준비 상태는 `live_results_awaiting_independent_review`다. 둘 다 `evaluation_complete: false`다. 사람 또는 결과 작성과 독립된 검토자가 같은 기준으로 인용·제품 모델 오류·기능 중복을 확인하고, PM이 원시 기록과 측정을 대조한 후에만 실제 평가의 완료 여부를 판단한다. 합성 자료 동작 확인을 실제 고객 수요·시장 효과로 바꾸지 않는다.

## 4. 준비 도구 검증

```powershell
uv run python -m unittest discover -s tests -p test_prepare_evaluation.py -v
uv run ruff check scripts/prepare_evaluation.py tests/test_prepare_evaluation.py
```

이 검사는 조건 차이·자료 변경·누락/중복 사례·fixture 혼입·잘못된 측정·덮어쓰기 거부, seed 재현성, null 유지, 원문 실패 보존을 확인한다. 실제 Agent의 성능 평가·여섯 독립 사례 실행·토큰 절감 검증은 포함하지 않는다.

모델 연결의 별도 근거로 2026-10-04 [28개 단위검사와 설정 안내](model-adapters.md) 및 [실제 구조화 출력 예산 검사](../../evals/pm-web-review/20261004/model-budget-live.json)가 있다. 실제 검사는 같은 고정 Qwen3:8b로 출력 상한 2048·문맥 8192에서 합성 요청의 12개 항목을 생성했고, 서버 보고 출력 544토큰·`done_reason=stop`·어댑터 호출 시간 9,313ms를 기록했다. 이는 한 번의 구조화 출력 설정 검사이며 독립 평가 사례·상품기획 판단·강한 기준선 비교·모델 품질 평가·P2-PM-005 완료 근거가 아니다.
