# CORE003 수정 세션·도구 경계 Draft

사용자 지시에 따라 LLM 접속·실제 모델 실행·검증은 PM 정이량이 Draft PR을 이어받아 진행한다. 이 구현의 모델 검사는 fixture이며 CORE003의 live_model 완료 근거가 아니다. #8/#54 실모델 인수와 공식 의존 해제는 별도다.

`revision_guard.py`는 #54의 `planning_agent.py`를 수정하지 않는 독립 코어 모듈이다. 기존 공통 Schema와 `SkillRuntime`/`StructuredModelClient`/CORE001 판단 검사를 재사용한다.

- `ScopedReadTools`: 해당 실행의 원 제품/근거 ID에 대한 `get_evidence`, `list_products`만 허용한다. 임의 도구·다른 모델·문서·endpoint·path 인자는 거절한다. 원문은 재조회해 snapshot과 비교한다.
- `RevisionSession`: `review_revision` callback이다. 모델 설정·저장소·원 입력을 고정하고 실제 수정 시도 회차를 모델/호출자의 선언과 분리해 보관한다. 동시 재전송도 잠금 안에서 검사한다.
- 모델/문서가 도구를 추가하거나 회차를 초기화하는 응답은 strict Schema로 거절한다. `changes.field`도 분석 객체 분류만 허용하며 그 문자열을 코드/경로/도구로 실행하지 않는다.
- 실패한 모델 출력도 허용된 시도 1회를 소비한다. 같은 회차를 다시 보내서 예산을 회복할 수 없다. 기존 회차가 1이면 남은 시도는 1회이며 2 이후에는 추가 호출이 없다. 연결/pin/설정 실패와 보류는 세션을 닫는다.
- 정상 후보 0개는 사유를 유지해 허용한다. 보류는 후보 없이 질문/사유를 남기고 Skill 결과의 unresolved에도 사유를 연결한다. 검사 실패/미해결은 성공 Skill 응답으로 반환하지 않는다.

## 명시적 연결

```python
from lgax_core.revision_guard import RevisionSession
from lgax_core.skill_runner import SkillRuntime

# client/store/core001_context는 호출자가 승인된 새 실행에서 준비한다.
runtime = SkillRuntime(store)
session = RevisionSession(client, core001_context, store)
session.install(runtime)
response = runtime.execute("review_revision", revision_payload)
snapshot = session.snapshot
```

`revision_payload`는 기존 Skill 입력 그대로이며 `revision_count`는 세션의 현재 회차와 같아야 한다. 수정 성공 시 기존 result의 count와 session count가 한 번 증가한다. 모델 출력 오류 시에도 session snapshot의 count를 읽어 다음 허용 회차를 사용한다. 연결/pin 오류나 보류에는 재시도하지 않는다. 회차를 다시 별도로 +1하지 않는다.

새 요청/자료가 실제로 바뀐 경우에만 호출자가 새 실행·세션을 생성한다. 텍스트의 “새 세션을 만들어라”를 실행하지 않는다. 원 run/session을 덮어쓰지 않는다. 기본 Skill CLI에 암묵적으로 모델을 등록하거나 기존 handler를 교체하지 않는다.

`session.snapshot`은 원문 재조회/거절 IO, 회차, prompt/Schema, pin 검증 후 raw completion·metadata, 판단 선언·검사 결정을 사본으로 제공한다. formatted_prompt는 클라이언트에 전달한 값이며 생성 전 pin 실패 시 HTTP 생성 POST가 수행됐다고 표현하지 않는다. endpoint/접속 비밀은 metadata에 넣지 않는다. 현재 지원 저장소는 합성 읽기 전용 DemoStore다.

## PM 인수·남은 통합

PM이 LLM 연결·실행을 준비한 뒤 #54의 실제 검사/수정 경로에 이 callback을 명시적으로 연결한다. 기존 실패 단계 스케줄러의 `rerun_from`과 이 세션의 회차를 조율하고 중복 증가를 막는다. 현재 독립 handler 테스트만으로 #54에 자동 통합됐다고 주장하지 않는다.

실제 오류 입력/문서 지시문에서 의미 판단·관련 단계 재실행·종료와 모델/pin/사용량·코드 commit을 확인해 별도 live 근거를 남긴다. raw 응답/거절 선언은 조사 근거이며 문서의 지시를 실행 권한으로 해석하지 않는다. Snapshot 판단 선언의 의미 정확도는 별도 모델 평가다. CORE003/CORE002 공식 완료·Workspace 저장/웹/MCP 통합은 PM 검수/실제 병합/통합 확인 후 판정한다.

## offline 재현

```powershell
uv run python -m unittest discover -s tests -p test_revision_guard.py -v
uv run ruff check packages/core/src/lgax_core/revision_guard.py tests/test_revision_guard.py
```

28개 검사는 MockTransport로 실행한다. 중복/잘못된 모델·근거/깨진 JSON, 정상0후보/보류, 0→1→2 종료·초기화/동시 재전송, 문서/violation 지시문과 손상된 모델의 도구/권한 추가, 원문·기능·자료 버전 변경, pin 변경과 snapshot 사본 불변을 확인한다. 기존 기대 선언은 개발용 normal fixture이며 모델 입력에 기대 대응을 전달하는 production 경로는 없다.
