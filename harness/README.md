# LG AX AtoZ 하네스

아이디어 탐색·도출부터 비교·선정·Agent 설계·구현·평가·제출까지, 현재 Codex가 자연어 요청에 따라 수행하는 하네스다. '하네스' 키워드를 따로 말할 필요는 없다.

**현재 사용법:** [AtoZ_사용법.md](AtoZ_사용법.md). 단계/행동 계약은 `atoz.json`, 재개 상태는 `atoz_state.json`, 실제 산출물은 `runs/current/`에 있다.

```powershell
python scripts/ax_workflow.py next
python scripts/ax_workflow.py packet design
python scripts/ax_workflow.py validate
```

Codex가 패킷의 일을 실제 도구로 수행해 결과 파일을 만들고 `finish <stage> <artifact>`로 검토·증빙을 기록한다. 선행 단계 누락, 빈 결과, 변경된 증거를 검사한다. 이전에는 진행 검사만 있었고, 지금은 단계별 실행 행동과 입력/출력 계약·재개·변경 전파를 연결했다.

전체 12단계 중 이번 대화에서 목표 정렬·조사·아이디어 도출·비교·핵심 검사·선정·설계까지 수행했다. 이전 선택은 Theme B Kitchen Recovery였다. 최신 요청에서는 LLM/기존 도구 대비 가치를 추가해 6개 후보를 비교했고 현재 주제는 재검토 중이다. 현재는 공식 과제·키친 콘셉트·Agent 역할을 연결한 `runs/official_alignment/`의 4단계이며, 이전 발산·선정 결과와 구분한다. 최신 문서는 `기획/공식과제_기준_후보정리.md`다. 수상 확률이나 실제 모델 생성 품질을 입증한 것은 아니다. 제안서/신청·모델 연결·UI·독립 평가·발표는 남아 있다.

기존 `project.json`과 `scripts/harness.py`의 `status/validate/gate topic/gate submission`은 공식 접수 점검을 위해 유지한다. `topic_trial.py`는 이전 A4/B1/B5의 제한된 규칙 실험이고 `flow_audit.py`는 이번 UX 그래프 실험이다. CI는 상태·코드·저장된 실행 결과를 검사한다. 기획의 우수성, 서명 진위, 실제 접수 성공은 자동으로 판단하지 않는다.

참고: 사용자 `harness-100`의 시장 조사·PM·LLM 앱·테스트 구조. 실제 읽은 파일과 적용 범위는 `research/atoz/README.md`에 기록했다. 별도 유료 API나 하위 Agent를 만들지 않고 현재 Codex가 순서대로 역할을 수행한다.
