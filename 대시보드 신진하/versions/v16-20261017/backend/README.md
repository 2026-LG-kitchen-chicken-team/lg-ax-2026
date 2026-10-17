# KITCHEN AX Python 실행기

웹 화면과 분리된 로컬 실행기입니다. Python 표준 라이브러리만 사용하며 다섯 단계는 실제 입력에 대한 결정적 규칙으로 작동합니다. 네트워크 검색·독립 서브 에이전트·제품 성능 검증을 수행하지 않습니다. 정적 공개 사이트에서 실행되는 브라우저 분석과 이 Python 서버는 별도의 실행 환경입니다.

## 실행

프로젝트 최상위 폴더에서 다음을 실행합니다. Python 3.10 이상을 사용합니다.

```powershell
python -m backend.server --port 8032
```

이 컴퓨터의 Codex 번들 Python을 사용할 경우:

```powershell
& 'C:/WORKSPACE/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m backend.server --port 8032
```

테스트:

```powershell
python -m unittest discover -s backend/tests -v
```

기본 주소는 `http://127.0.0.1:8032`이며 다른 컴퓨터에서 직접 접속할 수 없습니다. 브라우저 요청은 HTTP localhost/127.0.0.1 출처만 기본 허용합니다. 필요한 개발·배포 출처를 추가할 때는 환경 변수 `AX_ALLOWED_ORIGINS`에 정확한 Origin을 쉼표로 구분해 지정합니다. 전역 와일드카드는 사용하지 않습니다. 외부 서비스 배포 시 HTTPS·인증·사용자별 저장 격리를 갖춘 별도 서버 구성이 필요합니다.

## 구성

- `engine.py`: 자료 조회 → 니즈 구조화 → 기능 대조 → 콘셉트 작성 → 검토·수정. 브라우저와 같은 단계 ID 및 공통 결과 필드를 사용하지만 두 규칙 구현의 의미 해석 결과가 완전히 같다고 보장하지 않습니다.
- `server.py`: 단계 단위 HTTP API. 단계를 나눠 호출하면 웹 화면에서 실행·중지·대기 상태를 제어할 수 있습니다.
- `repository.py`: 실행 ID당 단일 SQLite 스냅샷. 같은 ID 저장은 갱신하며 자료·결과를 별도 중복 테이블로 만들지 않습니다.
- `llm_adapter.py`: 명시 호출만 가능한 교체용 JSON HTTP 어댑터 한 개. 미설정 상태는 오류로 알리고 규칙 실행을 LLM 실행으로 표시하지 않습니다.
- `contracts.schema.json`: 자료·단계 결과·이벤트·실행·LLM 계획의 교환 규약. 서버에서는 표준 라이브러리로 핵심 타입·ID·근거 무결성을 검사하며 전체 JSON Schema 엔진을 탑재하지 않습니다.

## API

| 경로 | 동작 |
|---|---|
| `GET /health` | 로컬 규칙 모드, 5개 Skill, LLM 설정 여부/마지막 명시 호출 성공 여부 |
| `POST /api/stage` | `{stage,context}`를 받아 한 단계 결과 반환 |
| `GET /api/runs` | 최근 100개 저장 실행 ID·갱신 시각 |
| `POST /api/runs` | `{id,snapshot}` 단일 실행 저장/갱신 |
| `GET /api/runs/{id}` | 해당 실행 스냅샷 복원 |
| `POST /api/llm/plan` | 선택적으로 LLM에 다섯 단계의 기획 계획 요청 |

`/api/stage` 예시:

```json
{
  "stage": "retrieve",
  "context": {
    "request": "냉장고 선반 청소 불편을 대조해 주세요.",
    "conditions": {"categories": ["cleaning_transport"], "excludedTerms": []},
    "reviews": [
      {"id":"R-001","model":"K-A01","text":"선반을 청소하려면 식품을 전부 꺼내야 해서 불편해요.","source":"합성 리뷰","synthetic":true}
    ],
    "models": [
      {"id":"K-A01","name":"가상 냉장고","version":"v1","source":"합성 설명서","synthetic":true,"features":[
        {"id":"K-A01:F1","name":"분리형 선반","evidence":"식품을 옮긴 뒤 선반을 분리해 세척한다.","condition":"탈착 전 식품 이동","page":4}
      ]}
    ],
    "results": {},
    "decisions": {}
  }
}
```

응답의 공통 구조:

```json
{
  "stage":"retrieve",
  "skill":"source_retrieve",
  "mode":"local_rules",
  "executor":"python",
  "llm_connected":false,
  "processed":1,
  "total":1,
  "result":{"summary":"...","activity":"...","items":[],"sources":[],"warnings":[],"assumptions":[]}
}
```

다음 단계 요청에는 같은 원본 입력과 앞선 응답을 `context.results.retrieve` 등에 담습니다. `stage`는 `retrieve`, `structure`, `compare`, `concept`, `validate` 중 하나입니다. 결과 필드는 각각 `matchedReviews/models`, `needs/positiveReviews/mixedReviews`, `comparisons/withheld/clarificationQuestions`, `concepts/withheld`, `checks/issues/repairTargets/acceptedConcepts`를 포함합니다.

`processed/total`은 응답에서 실제 생성·확인한 자료/묶음/대조/후보/검사 수입니다. 단계 실행 중의 시간 추정 퍼센트를 만들지 않습니다. HTTP 단계는 동기 처리이므로 일시정지는 단계 사이에서 적용합니다. 이미 처리 중인 HTTP 요청은 물리적으로 취소하는 API를 제공하지 않습니다.

선택 단계부터 재실행할 때는 그 단계와 이후 결과를 먼저 무효화합니다. 원본 자료·모델 버전이 바뀌면 `retrieve`부터 다시 실행합니다. Python의 배치 보조 함수 `run_pipeline`은 검사 실패 시 필요한 가장 이른 단계부터 최대 2회 재실행하며 수정 전후를 남깁니다. 불명확한 비교는 `clarificationQuestions`로 전달되며 사용자가 `decisions[questionId] = "include"` 또는 `"hold"`를 선택합니다. `include`는 가정 표시이며 기능 근거가 없는 후보를 생성하는 허용이 아닙니다. 대기·질문·버튼은 웹 실행기가 관리합니다.

원문은 항상 자료입니다. 업로드 문장에 포함된 명령·코드·역할 변경 지시는 실행하지 않습니다. 누락 모델을 다른 모델로 대체하지 않고, 기능 근거 부재를 기능 부재로 바꾸지 않습니다. 긍정-only 리뷰는 보류 설명과 함께 분리하고 긍정·부정 혼합 원문은 전체를 유지합니다. 합성 여부와 출처·페이지·버전·사용 조건이 있으면 인용에 보존합니다. 실제 정확도·시간 절감률·비용은 계산하지 않습니다.

## LLM 연결 준비 범위

초기에는 키를 요청하거나 저장하지 않습니다. `/api/stage`는 어댑터 설정 여부와 무관하게 로컬 규칙입니다. 외부 호출은 사용자가 `/api/llm/plan`을 명시 호출했을 때만 발생합니다.

```powershell
$env:AX_LLM_URL = 'https://your-provider.example/v1/chat/completions'
$env:AX_LLM_MODEL = 'your-model-id'
# AX_LLM_API_KEY는 실행 환경의 비밀 설정으로 주입합니다. 파일에 기록하지 않습니다.
python -m backend.server
```

공급자는 JSON `model`, `messages`, `response_format` 요청을 받아 `{result:{summary,steps,assumptions}}` 또는 `choices[0].message.content`의 JSON을 반환하는 엔드포인트여야 합니다. 공급자별 차이는 이 어댑터 파일 한 곳에서 교체합니다. `steps`는 순서가 맞는 다섯 Skill이며 원문에 없는 근거 ID를 거부합니다. 시간 제한 기본 45초, `AX_LLM_TIMEOUT`으로 5~120초 설정 가능합니다.

현재 어댑터가 수행하는 것은 기획 계획 작성입니다. 다섯 Skill 전체의 LLM 기반 의미 분석·검색 도구·자동 위임은 아직 구현하지 않았습니다. `llm_configured`는 환경 설정 여부, `llm_connected`는 마지막 명시 계획 호출의 성공 여부입니다. 실제 LLM 연결 검증은 자격 정보와 공급자 엔드포인트가 제공된 뒤 수행해야 합니다. 서버는 API 키·응답 본문·요청 원문을 로그에 출력하지 않습니다.

SQLite 파일은 기본 `backend/data/runs.sqlite3`입니다. 이는 해당 컴퓨터의 단일 사용자 저장소이며 공개 공유 DB가 아닙니다. 브라우저 저장과 자동 동기화하지 않으므로 같은 실행을 여러 저장소에 중복 생성하지 않도록 연결할 때 한 저장 방식을 선택해야 합니다.
