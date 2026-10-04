# 명시적으로 켜는 작업실 Agent 실행

기존 작업실은 기본 설정에서 요청을 저장하고 `not_implemented`·`output: null`을 반환한다. 이 경로는 모델을 호출하지 않는다. 실제 판단 연결은 서버의 `--enable-planning` 또는 trusted 코드에서 `create_workspace_app(..., planning_runner=EnvPlanningRunner())`를 설정했을 때만 켜진다. 입력 body에는 provider·모델·endpoint·파일 경로·활성화 옵션을 넣을 수 없다.

```powershell
uv run --no-sync python -X utf8 -m lgax_api.workspace_server --db private/workspace-live/workspace.sqlite --credentials private/workspace-live/server-credentials.json --port 18879 --dataset evals/core-planning/examples/dataset.json --enable-planning
```

서버 환경의 `LGAX_MODEL_ADAPTER`, `LGAX_MODEL_ENDPOINT`, `LGAX_MODEL_ID`, `LGAX_MODEL_DIGEST`와 기존 출력/문맥/시간 제한을 명시적으로 설정해야 한다. 서버 주소·digest 설정이 없거나 모델 연결이 실패하면 판단 성공을 만들어내지 않는다. 자격증명은 기존 `init_workspace.py`의 비공개 저장 위치를 따른다. 이 예시는 실행 명령이며 실제 모델·API 성공이나 서버 활성 증빙이 아니다. 기존 18869 작업실을 덮어쓰지 않고 별도 port·DB를 사용할 수 있다.

`create_workspace_app(db_path, registry, *, planning_runner=None, evidence_store=None)`는 서버 코드에서만 받는 옵션이다. 자료 미지정 시 기존 `default_store()`를 유지한다. `--dataset`도 서버 시작 시 선택한 합성 자료이며 클라이언트 요청으로 선택·교체할 수 없다. injected fixture runner는 검사 전용이고 `execution_kind: fixture`를 남긴다.

## 입력과 저장 경계

같은 `POST /api/workspace/projects/{project_id}/runs`에서 기존 인증·editor/admin 쓰기 권한·owner·origin/host·body 계약을 먼저 확인한다. 단일 모델과 Product 원본의 문서 버전만 실제 판단 대상으로 지원한다. 다중 모델 또는 다른 Product 문서 버전은 비용 발생 전 `NOT_IMPLEMENTED`로 명시적으로 거절한다. 제품군·모델·자료 버전·문서 버전·자료 SHA와 parent는 프로젝트의 고정 범위를 따른다.

`build_planning_input`은 해당 범위의 **전체 기능과 전체 원문 근거**를 DemoStore에서 다시 읽어 CORE001 입력을 만든다. 사용자 요청과 제외 조건을 그대로 복사하며 내부 수정 회차는 매 새 실행 0에서 시작한다. 명세/문서 변경은 기존 프로젝트를 몰래 바꾸는 대신 새 자료 범위의 프로젝트가 필요하다.

읽기 트랜잭션에서 owner·parent·범위를 확인한 뒤 연결을 닫고 모델을 실행한다. 모델 호출 중 SQLite 쓰기 트랜잭션을 유지하지 않는다. 결과 저장 직전에 owner·parent·자료 범위를 다시 확인하고 짧은 쓰기 트랜잭션으로 **새 snapshot 한 개**를 추가한다. parent와 과거 요청/결과는 변경하지 않는다. 중간에 자료/범위가 달라지면 `DATASET_MISMATCH`로 저장을 거절한다.

## 실제 결과와 실패 기록

`Run`에는 검사한 canonical concepts·status·내부 revision_count·events·근거 ID를 투영한다. 웹의 기존 출력은 `{needs, gaps, planning_execution}`이다. `planning_execution`에는 PlanningAgent 원본 입력·최종 입력·decision·errors·trace·model_calls·raw 응답·metadata가 들어간다. 기존 JSON Schema의 자유 output object를 사용하며 웹은 같은 needs/gaps를 표시한다. API와 전용 MCP가 같은 저장 기록을 조회하므로 별도 분석 코어를 만들지 않는다.

`completed`는 CORE001 출력·입력 연결과 최종 `review_judgement`의 accept 검사를 통과해야 한다. held/failed는 새 실행에 기록하고 Run의 후보를 비운다. 보류 이유·질문과 원본 출력/trace는 부가 내역에 유지한다. 잘못된 runner 출력도 완료로 저장하지 않고 failed와 `rejected_execution`을 남긴다. JSON으로 표현할 수 없는 기록은 그 생략 이유를 명시한다. 예외 문자열·provider 주소·자격증명은 실패 응답에 넣지 않는다. 환경 실패의 `live_model`은 선택된 실행 경로이며 `model_calls: []`이면 실제 호출 성공 증거가 아니다.

`request_revision`은 사용자 조건 변경 회차이고 Agent의 최대 2회 내부 수정과 구분한다. 같은 입력의 후속 실행도 새 run ID를 가지며 parent 링크만 추가한다. snapshot 저장201이나 fixture 검사 통과는 실제 Agent 성능·독립 평가·WEB003/PM003·PM004 전체 완료를 입증하지 않는다.

## 검사와 실제 검증

```powershell
uv run --no-sync python -X utf8 -m unittest discover -s tests -p "test_workspace*.py" -v
uv run --no-sync ruff check packages/core/src/lgax_core/workspace.py packages/core/src/lgax_core/workspace_planning.py apps/api/src/lgax_api/workspace_server.py tests/test_workspace_planning.py
```

신규 시험은 기본 미호출·scope/owner/parent·요청 변경/부모 불변·내부 수정 회차·보류/실패·잘못된 완료·트랜잭션 경계와 API body/권한을 확인한다. MockTransport를 사용하는 실제 PlanningAgent 흐름도 **fixture 시험**으로만 기록한다. 별도 실제 모델/API 실행은 PM이 입력·서버 설정·자료/모델 버전·원본 응답·같은 run 조회/호스트·웹 연결을 증빙해야 한다. 이 문서 생성과 자동 검사만으로 그것을 완료 처리하지 않는다.
