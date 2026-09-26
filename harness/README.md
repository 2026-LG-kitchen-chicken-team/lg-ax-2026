# LG AX AtoZ 하네스

아이디어 탐색·도출부터 비교·선정·Agent 설계·구현·평가·제출까지, 현재 Codex가 자연어 요청에 따라 수행하는 하네스다. '하네스' 키워드를 따로 말할 필요는 없다.

**현재 사용법:** [AtoZ_사용법.md](AtoZ_사용법.md). 단계/행동 계약은 `atoz.json`, 재개 상태는 `atoz_state.json`, 최신 선정 산출물은 `runs/sample_first/`에 있다. 패킷의 `runs/current/`는 기본 작성 경로이며 실제 완료 파일은 상태 기록을 따른다.

```powershell
python scripts/ax_workflow.py next
python scripts/ax_workflow.py packet design
python scripts/ax_workflow.py validate
```

Codex가 패킷의 일을 실제 도구로 수행해 결과 파일을 만들고 `finish <stage> <artifact>`로 검토·증빙을 기록한다. 선행 단계 누락, 빈 결과, 변경된 증거를 검사한다. 이전에는 진행 검사만 있었고, 지금은 단계별 실행 행동과 입력/출력 계약·재개·변경 전파를 연결했다.

최신 요청은 구현 난도와 1차 서류 설득력 두 조건만으로 원점 재검토하는 것이다. 6개 최소 구현을 비교하고 공개 데이터 접근·파싱·연결을 실행해 **Theme A 고객 불편·기존 제품 대조 기반 키친 상품기획 Agent**를 위임 선정했다. 현재 12단계 중 목표~선정 6단계가 완료 기록되었고 다음은 상세 설계다. 최신 근거는 `기획/샘플데이터_기준_재검토.md`다. 사용자 정정에 따라 샘플·가상 명세·모의 연동을 모든 후보에 공통 적용해 난도를 보정했고 같은 A 선정을 유지했다. 새 실험이 아니라 기존 자료·저장 결과를 재검토했다. 원자료 표본과 모델 성능·현업 효용·합격 확률의 검증을 구분한다. 이전 설계·12개 후보·A/B 우선 추천은 각 실행 폴더에 보존했다. 새 안의 상세 설계·제안서/신청·모델 연결·UI·독립 평가·발표는 남아 있다.

기존 `project.json`과 `scripts/harness.py`의 `status/validate/gate topic/gate submission`은 공식 접수 점검을 위해 유지한다. `topic_trial.py`와 `flow_audit.py`는 이전 후보의 제한된 규칙·UX 그래프 실험이다. CI는 상태·코드·저장된 실행 결과를 검사한다. 기획의 우수성, 서명 진위, 실제 접수 성공은 자동으로 판단하지 않는다.

참고: 사용자 `harness-100`의 시장 조사·PM·LLM 앱·테스트 구조. 실제 읽은 파일과 적용 범위는 `research/atoz/README.md`에 기록했다. 별도 유료 API나 하위 Agent를 만들지 않고 현재 Codex가 순서대로 역할을 수행한다.
