# CORE002 판단 흐름 Draft와 PM 인수

## 범위

**LLM 연결 및 실제 모델 실행은 미완료이며, 사용자 지시에 따라 PM 정이량이 이 Draft PR을 이어받아 연결·실행·검증을 진행한다.** 이 문서는 인수 요청이며 PM의 실제 수신/착수/승인 증거가 아니다. CORE001 PR #51 검수 대기 중 독립 개발한 CORE002 부분 구현이다. CORE002의 `live_model` 완료 근거나 공식 의존 해제를 등록하지 않는다.

`packages/core/src/lgax_core/planning_agent.py`의 `PlanningAgent`가 명시적으로 주입한 `StructuredModelClient`와 읽기 전용 `DemoStore`를 사용한다. 원 입력은 CORE001 내부 계약이다. 기본 Skill CLI와 API/MCP/Workspace는 기존 상태를 유지한다. 새 Agent를 생성하는 경로에서만 세 판단 handler를 등록한다.

1. 원 요청·제품·선택 근거·기능·문서 버전과 단계 계획을 보존한다.
2. 원 근거를 `get_evidence`로 다시 읽고 입력 snapshot과 대조한다. 자료 버전과 현재 제품 기능 전체를 확인한다.
3. `need_extract` → `product_compare` → `concept_draft`를 기존 SkillRuntime에서 실행한다. 각 단계에는 작은 독립 Schema와 실제 원문/사용자 조건이 전달된다. 선언 응답을 하드코딩하는 production handler는 없다.
4. CORE001 검사로 실패 단계를 결정한다. 관련 단계부터 최대 두 번 다시 생성하고, 회차 2 이후에는 미해결로 종료한다. 연결/pin/설정 오류는 다른 모델로 우회하거나 자동 반복하지 않는다.
5. 보류/실패에는 채택 가능한 후보를 반환하지 않는다. 미해결 마지막 선언은 `rejected_output`과 trace에 보존한다. 생성·JSON·근거 오류도 원 응답/정제 오류와 함께 기록한다.

단계 결과의 리뷰 극성·지원·해결·중복은 모델 선언이다. 검사 통과만으로 의미 정확도·수요·신규성·제외 조건 준수를 입증하지 않는다. 계획은 입력에 따라 작성하는 결정론적 단계 계획이며 모델의 자율 검색 계획이 아니다. 조회는 선택된 근거 ID의 실제 읽기이며 대규모 검색/재정렬은 자료 담당/후속 범위다.

## 호출 / 실행

```python
from lgax_core.model_client import StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore

# 승인된 모델 연결과 고정 digest 설정은 PM이 준비한다.
with StructuredModelClient.from_env() as client:
    result = PlanningAgent(client, DemoStore()).run(core001_input)
```

`core001_input`의 sources/features/product는 같은 저장소의 원본이어야 한다. 변경 명세를 평가하려면 원 데이터와 입력을 함께 갱신하고 새 실행을 만든다. `revision_count=0`으로 시작하며 원 요청과 내부 수정 회차를 분리한다. 여러 제품 모델은 각각 독립 입력/실행으로 호출한다.

```powershell
# 아래 연결 값은 PM이 승인된 본인 SSH 포워드/서비스를 확인한 뒤 설정한다.
$env:LGAX_MODEL_ADAPTER = 'ollama'
$env:LGAX_MODEL_ENDPOINT = 'http://127.0.0.1:18864'
$env:LGAX_MODEL_ID = 'qwen3:8b'
$env:LGAX_MODEL_DIGEST = '500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
$env:LGAX_MODEL_MAX_OUTPUT_TOKENS = '2048'
$env:LGAX_MODEL_CONTEXT_TOKENS = '8192'
uv run python -m lgax_core.planning_agent --input evals/core-planning/examples/fridge.input.json --dataset evals/core-planning/examples/dataset.json --output private/runtime/core002-fridge-live.json
```

예시 입력/자료는 합성자료이며 분석 결과를 포함하지 않는다. 이 명령은 실제 모델 실행이며 이 Draft의 수행 결과가 아니다. 환경 설정이 없으면 명시적으로 실패한다. `--input`, `--dataset`과 같은 경로에 결과를 쓰지 않는다. CLI의 성공 종료 코드는 completed이며 held/failed는 2다. 자료/설정/연결 문제는 분석 성공으로 처리하지 않는다.

기본 Lab 경로의 256 출력 토큰/5,000자 prompt 제한은 여러 객체의 결과에 부족할 수 있다. 충분한 출력 예산을 지정할 수 있는 직접 Ollama 경로를 우선 검토한다. prompt·schema가 문맥에 실제로 들어갔는지, `done_reason`, 사용량, 모델 digest를 [PM 모델 규격](../pm/model-adapters.md)에 따라 확인한다. 예산 값은 실제 모델 검증 없이 확정된 평가 조건이 아니다.

## 로그 / 근거

반환값의 `original_input`은 원 요청·자료 그대로이고 `input`은 마지막 내부 회차를 포함한다. `output`은 내부 판단 결과, `decision`은 CORE001 검사 결정이다. `status`는 completed/held/failed이며 Workspace Run을 자동 저장한 것으로 해석하지 않는다.

- `trace`: 실제 계획, bootstrap 자료 SHA, 원문 읽기 입력/출력, Skill 입력/검증 envelope, 검사/수정/종료.
- `model_calls`: 각 단계·회차·입력 SHA, 요청 문맥/Schema, 모델 이름/digest, 전달 prompt/해시, pin 검증 후 raw completion, 구조화 값/metadata, 정제 오류.
- metadata: 기존 클라이언트의 모델 revision·설정·시간·토큰·종료 이유. endpoint/접속 비밀은 로그에 넣지 않는다. 현재 저장소는 합성 자료만 허용한다.

의도적으로 모의 transport를 사용한 검사는 `execution_kind="fixture"`를 명시한다. Production 기본 live_model 표기만으로 실제 네트워크/모델 실행이 증명되지는 않는다. PM은 실제 서비스의 로그·원 응답·digest·실행 commit을 교차 확인한다.

## PM이 이어서 할 일

- #51 계약 검수/병합을 우선 진행하고 이 Draft의 선행 branch를 최신 main에 맞춘다.
- 승인된 연구실 접속/SSH 포워드와 모델 환경을 준비한다. GPU 사용량·기존 프로세스/포트 소유를 먼저 확인한다. 이 Draft는 GPU/모델 설치·서버 시작·SSH 설정을 수행하지 않았다.
- 예시와 서로 다른 요청/제외 조건·변경 명세로 실제 모델을 호출하고 결과/실패/회차/사용량·원 응답을 고정한다. 의미 오류와 prompt/출력 예산 부족을 확인하고 조정한다.
- 사용자 지정 인수 범위의 연결·실행·검증을 진행하고, 기존 담당 기록을 대신 수정하지 않고 PM의 별도 기록/근거를 추가한다. 판단 기능 수정이 필요하면 담당자에게 구체 지시를 연결한다.
- 실제 코어 결과의 Workspace/API/MCP/웹 저장·사용자 이력 연결은 PM 통합 영역이다. 현재 CLI와 라이브러리가 그 경로를 변경하지 않는다.
- `review_revision`의 독립 Skill 연결, 세 제품/전체 변경 재검토·독립 의미 평가·최종 Done은 후속 조건으로 유지한다.

## 모의 검사 재현

```powershell
uv run python -m unittest discover -s tests -p test_planning_agent.py -v
uv run ruff check packages/core/src/lgax_core/planning_agent.py tests/test_planning_agent.py
```

개발용 normal 선언 fixture를 네트워크 경계의 MockTransport로 전달한다. 기존 Qwen pin/JSON/Schema 클라이언트와 실제 SkillRuntime/CORE001 검사는 실행하지만 실제 LLM은 호출하지 않는다. 원문 변조/모델·자료 버전, 긍정·상충·미언급 보류, 단계별 재시도/회차 상한, raw 응답과 메타데이터 보존, 원 입력 보호, 연결 부재 실패를 검사한다. 기대 대응을 실제 모델 입력에 전달하는 코드는 없다.
