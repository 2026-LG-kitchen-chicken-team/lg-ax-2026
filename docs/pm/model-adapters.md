# PM 구조화 모델 호출 어댑터

`P2-PM-003/004`에서 사용하는 공통 모델 호출 기반이다. 상품기획 판단 프롬프트와 Agent 정책은 황대겸 담당 기능에서 정의한다. 이 모듈은 지정한 모델을 호출하고, 모델 버전·JSON·스키마가 맞는 결과만 반환한다.

- 코드: `packages/core/src/lgax_core/model_client.py`
- 단위 검사: `tests/test_model_client.py`
- 실제 실행 근거: [2026-10-04 Lab/Ollama 교체 실행](../../evals/pm-workspace/20261004/live-model-adapters.json)
- 출력 예산 설정의 실제 실행 근거: [2026-10-04 Ollama 구조화 출력 검사](../../evals/pm-web-review/20261004/model-budget-live.json)

## 공통 호출 계약

```python
from lgax_core.model_client import (
    LabModelAdapter, ModelConfig, OllamaAdapter, StructuredModelClient,
)

config = ModelConfig(
    endpoint="http://127.0.0.1:18865",  # 또는 SSH 포워드의 로컬 포트
    model_id="qwen3:8b",
    expected_digest="500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
    timeout_seconds=120,
    max_response_bytes=131072,
    max_output_tokens=256,
    context_tokens=4096,
)
schema = {
    "type": "object",
    "properties": {"message": {"type": "string", "minLength": 1}},
    "required": ["message"],
    "additionalProperties": False,
}
with StructuredModelClient(LabModelAdapter(config)) as client:
    result = client.generate("한국어로 짧은 인사 한 문장을 작성하세요.", schema, "qwen3:8b")
    value = result.data
    metadata = result.metadata
    envelope = result.as_dict()  # {"data": ..., "metadata": ...}
```

직접 Ollama를 사용할 때는 `endpoint="http://127.0.0.1:18864"`와 `OllamaAdapter(config)`로 교체한다. 호출 시 `model_id`는 제품 ID가 아니라 생성 모델 이름이다. 모델 이름이나 pin을 바꾸려면 새 `ModelConfig`를 명시한다. 최신 태그로 자동 교체하거나 실패 결과를 다른 모델로 우회하지 않는다.

동기 HTTP 호출이다. 비동기 API에서 사용한다면 호출을 작업 실행기나 스레드로 넘겨 이벤트 루프를 막지 않도록 통합해야 한다. 어댑터는 context manager 또는 `close()`로 연결을 닫는다.

| 항목 | LabModelAdapter | OllamaAdapter |
|---|---|---|
| 실제 생성 API | 기존 `/generate`, `{"prompt": ...}`만 전달 | `/api/generate`에 모델·prompt·`format=schema` 전달 |
| 사전·사후 pin 확인 | `/health`의 ready 상태, 모델 목록, digest, 서비스 소스 SHA | `/api/tags`의 정확한 모델 이름·digest |
| 형식 유도 | 공통 JSON·스키마 지시를 prompt에 포함 | 같은 지시와 native JSON Schema 제약 |
| 결과 검증 | 엄격 JSON 파싱 + 로컬 Draft 2020-12 검증 | 같은 로컬 검증 |
| `backend_schema_enforced` | `false` | `true` |
| 전체 전달 prompt 제한 | 5,000자 | 16,000자 |
| 생성 설정 | Qwen3:8b·temperature 0·context 4096·출력 최대 256토큰 고정, seed 미지정 | temperature 0·seed 42 고정, context/출력 상한 설정 가능(기본 4096/256) |

Lab 서버는 `services/inference/server.py`의 현재 계약을 그대로 사용한다. 스키마 필드를 API에 보내지 않으며 `max_output_tokens=256`, `context_tokens=4096` 외의 조합은 `INVALID_ARGUMENT`/`lab_generation_budget_is_fixed`로 거절한다. 설정을 받아 놓고 고정값으로 실행하지 않는다. 직접 Ollama는 `ModelConfig(max_output_tokens=..., context_tokens=...)`로 출력 상한과 문맥 길이를 지정할 수 있다.

두 경로의 기본 출력 상한은 256토큰이다. 긴 결과가 필요한 직접 Ollama 호출은 충분한 상한을 명시한다. 출력 상한은 32~8192, 문맥 길이는 1024~32768의 정수이고 `max_output_tokens <= context_tokens - 512`여야 한다. 이 설정 검사는 최소 512토큰의 여유만 요구하며, 전체 prompt·schema가 실제 문맥에 들어가는지나 모델의 지원 문맥·GPU 메모리를 보장하지 않는다. 문자 수 제한 역시 토큰 수나 실제 문맥 적합성을 보장하지 않는다.

## 입력·실패·정보 보호

- endpoint는 명시적 포트를 가진 숫자형 loopback HTTP(S) 주소만 허용한다. `localhost`, LAN/공개 주소, 계정 정보·query·fragment·하위 경로가 포함된 주소는 거절한다. 연구실 접속은 별도로 승인된 SSH 포워딩을 이용한다.
- 환경 프록시를 사용하지 않으며 redirect를 따라가지 않는다. HTTP 요청 전체에 하나의 누적 제한 시간(기본 120초, 설정 최대 300초)을 적용하고, 각 응답은 기본 128 KiB·설정 최대 1 MiB까지 읽는다. 압축 응답은 거절한다.
- schema는 JSON object 형식의 Draft 2020-12 계약이다. 최대 16 KiB이며 외부 `$ref`·`$dynamicRef`·`$recursiveRef`를 거절하고 원격 스키마를 조회하지 않는다. 로컬 `$defs` 참조와 알려진 `format` 검증을 지원한다. 제출된 공통 계약 전체를 prompt에 넣기보다 해당 호출에 필요한 작은 정의를 사용한다.
- 응답은 JSON 값 하나 또는 전체 응답을 감싼 단일 `json`/무언어 코드 펜스만 허용한다. 앞뒤 설명·여러 JSON·가짜 펜스·손상된 JSON·중복 키·NaN/Infinity·범위 밖 부동소수는 거절한다. JSON 문자열 안의 backtick은 그대로 보존한다. 부분 문자열 추출이나 자동 수정·재호출은 하지 않는다.
- 모델 누락·중복 태그·digest 변경·응답 모델 불일치·미완료 출력·Ollama `done_reason=length`를 실패로 반환한다. Lab API는 `done_reason`을 노출하지 않으므로 잘린 응답은 JSON/스키마 검증 범위에서만 탐지한다.
- 실패는 기존 `DomainError` 계약을 따른다. `INVALID_ARGUMENT`은 설정·입력 문제, `MODEL_UNAVAILABLE`은 호출·pin 문제, `VALIDATION_FAILED`는 JSON·스키마 불일치다. `details.reason`으로 원인을 구분하며 HTTP 실패는 상태 코드만 포함한다. URL·prompt·응답 본문·예외 원문·환경 값은 실패 메시지에 포함하지 않는다.
- 성공 metadata는 모델 이름·Ollama manifest digest·스키마 SHA·형식 제약 방식·실측 시간·서버가 반환한 토큰 수와 종료 이유를 기록한다. `generation_settings`에는 전달한 `temperature`, `num_ctx`, `num_predict`, `seed`를 남긴다. Lab의 seed는 미지정이므로 `null`, 서버가 종료 이유를 제공하지 않으면 `done_reason`도 `null`이다. 직접 Ollama의 `done_reason=length`는 성공 metadata로 반환하지 않고 `MODEL_UNAVAILABLE`/`output_truncated`로 실패한다. 설정 기록은 실제 prompt가 잘리지 않았다는 증명이 아니므로 평가 때 실행 기록을 추가 대조한다. endpoint나 원문은 metadata에 넣지 않는다. `result.data`에는 실제 요청 결과가 있으므로 호출자가 접근 권한과 저장 위치를 관리해야 한다.

pin은 HF commit이 아니라 Ollama 모델 manifest digest다. 호출 전후 태그 검사는 실행 중 변경을 탐지하지만 모델 별칭 전환과 생성 요청을 원자적으로 잠그지는 않는다. 해당 LG 전용 모델 서비스의 운영자가 태그를 동시에 바꾸지 않는 운영 조건이 필요하다. 두 어댑터의 성공은 상품기획 판단의 정확성이나 제출 Agent 완성을 뜻하지 않는다.

## 환경 설정과 재실행

`StructuredModelClient.from_env()`는 다음 네 값이 모두 있어야 동작한다. 값이 없거나 pin이 유효하지 않으면 호출 전에 실패한다.

```text
LGAX_MODEL_ADAPTER=lab          # lab 또는 ollama
LGAX_MODEL_ENDPOINT=http://127.0.0.1:18865
LGAX_MODEL_ID=qwen3:8b
LGAX_MODEL_DIGEST=500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
LGAX_MODEL_TIMEOUT_SECONDS=120       # 선택
LGAX_MODEL_MAX_RESPONSE_BYTES=131072 # 선택
LGAX_MODEL_MAX_OUTPUT_TOKENS=256     # 선택, 직접 Ollama 32~8192; Lab은 256만 허용
LGAX_MODEL_CONTEXT_TOKENS=4096       # 선택, 직접 Ollama 1024~32768; Lab은 4096만 허용
```

`from_env()`도 `ModelConfig`와 같은 기본값·범위 검사를 적용한다. 출력 상한이 문맥 길이보다 최소 512 작아야 한다. Lab의 비고정 조합은 `generate()` 단계에서 생성 POST를 보내기 전에 거절한다. CLI는 이 환경변수를 읽지 않으며 명시한 CLI 인자와 기본값만 사용한다.

프로젝트의 고정 Python 3.11 환경에서 다음 검사로 네트워크·GPU 없이 계약을 확인한다.

```text
uv sync --locked --dev
uv run python -m unittest discover -s tests -p test_model_client.py -v
uv run ruff check packages/core/src/lgax_core/model_client.py tests/test_model_client.py
```

승인된 loopback 모델 서비스/SSH 포워드가 준비된 환경에서는 UTF-8 prompt·schema 파일을 지정해 실제 호출한다. 출력 폴더는 먼저 준비하고, 개인정보를 포함한 입력·결과는 `private/` 밖에 저장하지 않는다. CLI 콘솔에는 성공 여부·어댑터 또는 정제한 오류만 표시하고 결과·metadata는 지정한 파일에 LF로 저장한다.

```text
uv run python -m lgax_core.model_client --adapter lab --endpoint http://127.0.0.1:18865 --model qwen3:8b --digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 --max-output-tokens 256 --context-tokens 4096 --prompt-file private/runtime/model-prompt.txt --schema-file private/runtime/model-schema.json --output private/runtime/model-result.json
```

CLI의 `--max-output-tokens`와 `--context-tokens` 기본값도 각각 256과 4096이며 SDK와 같은 범위를 검사한다. 직접 Ollama에서 더 큰 구조화 결과를 재현하는 설정 예시는 다음과 같다. 이는 실행 방법이며 독립 평가에 충분한 예산을 확정한 것이 아니다.

```text
uv run python -m lgax_core.model_client --adapter ollama --endpoint http://127.0.0.1:18864 --model qwen3:8b --digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 --max-output-tokens 2048 --context-tokens 8192 --prompt-file private/runtime/model-prompt.txt --schema-file private/runtime/model-schema.json --output private/runtime/model-result-extended.json
```

의존성은 기존 `httpx`·`jsonschema` 및 jsonschema의 `referencing`이다. 새로운 패키지·모델 다운로드·공개 GPU endpoint를 요구하지 않는다. 공개 읽기 전용 MCP 데모와의 자동 연결은 구성하지 않았다.

## 검증 근거와 남은 통합

2026-10-04 단위검사 28개가 통과했다. Korean JSON, 두 API payload 차이, 단일 펜스, 손상/추가 텍스트·중복 키·비정상 숫자, 스키마/외부 참조, 호출 전후 모델 버전 변화, HTTP/timeout 정보 보호, redirect, 응답 크기·누적 시간, 필수 환경 pin을 검사한다. 추가 검사는 출력·문맥 예산의 범위, SDK/환경변수 전달, Lab의 비고정 예산 거절, CLI 인자→요청→검증된 결과 파일의 일치와 CLI/환경변수의 분리를 확인한다. 이 28개는 모의 transport를 사용하는 검사이며 실제 GPU 실행은 아래 근거로 구분한다.

실제 연구실 모델에서는 같은 합성 `MANUAL-001`의 `FRIDGE-A`/문서 버전 `1.0` 입력을 두 어댑터에 전달했다. 두 경로 모두 해당 값이 고정된 schema와 한국어 요약을 반환했고, 모델 digest·사전/사후 확인·로컬 스키마 검증이 통과했다. [원본 입력·schema·출력·metadata](../../evals/pm-workspace/20261004/live-model-adapters.json)에 기록했다. Lab 4,797ms와 직접 Ollama 516ms는 순차 실행·같은 모델·캐시 영향을 포함한 관측값이며 성능 우열 근거로 사용하지 않는다.

같은 Qwen3:8b digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`로 직접 Ollama의 출력 상한 2048·문맥 길이 8192·temperature 0·seed 42를 실제 호출했다. 합성 요청의 12개 항목이 JSON/schema 검증을 통과했고 서버 보고 출력은 544토큰, `done_reason=stop`, 어댑터 호출 시간은 9,313ms였다. [입력·schema·결과·설정·소스 해시](../../evals/pm-web-review/20261004/model-budget-live.json)에 기록했다. 이 한 번의 검사는 기본 256보다 큰 구조화 출력을 지정한 상한으로 처리할 수 있는지 확인한 것이다. 상품기획 Agent 실행·인용의 의미 정확성·모델 품질 비교·기준선 우열·전체 평가에 충분한 예산을 입증하지 않는다.

공정 비교는 [평가 조건](evaluation.md)에 따라 모델 digest뿐 아니라 실제 샘플링·출력 상한·문맥 길이·형식 제약 방식까지 양쪽에 맞춘다. 현재 Lab은 seed 미지정·prompt 제약이고 직접 Ollama는 seed 42·native schema 제약이므로, 두 경로를 그대로 바꿔 호출한 결과를 동일 조건 품질 비교로 표현하지 않는다.

상품기획 의미 검증, Skill 실행기와의 연결, Agent의 검사·수정 정책 및 다양한 모델의 품질 비교는 이후 담당 기능에서 검증한다. 이번 결과는 동일 Qwen 모델의 호출 경로 교체와 구조화 출력 기반을 확인한 것이다.

공식 API 참고(2026-10-04 확인): [Ollama generate](https://docs.ollama.com/api/generate), [모델 목록·digest](https://docs.ollama.com/api/tags), [구조화 출력](https://docs.ollama.com/capabilities/structured-outputs), [jsonschema 검증](https://python-jsonschema.readthedocs.io/en/stable/validate/).
