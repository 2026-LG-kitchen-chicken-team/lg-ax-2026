# LG 해커톤 수행 하네스

이 하네스는 주제 선정부터 제출까지 작업 순서·역할·근거·검증을 관리한다. 참가작 Agent 자체와는 별개다. Python 3.11 이상, 표준 라이브러리만 사용한다.

## 실행

```powershell
python scripts/harness.py status
python scripts/harness.py validate
python scripts/harness.py gate topic
python scripts/harness.py gate submission
python -m unittest discover -s tests -v
python scripts/scenario_spike.py
python scripts/topic_trial.py --check
```

`validate`는 기록의 구조·출처 연결·완료 증빙을 검사한다. 주제의 수상 가능성이나 실제 접수 여부를 판정하지 않는다. `gate topic`은 사용자가 선택한 주제와 구현 검토가 기록되었는지, `gate submission`은 주제 및 제출 점검이 완료되었는지 확인한다. 준비 중인 gate가 막히는 것은 정상이다. CI는 `validate`와 회귀 테스트만 수행한다.

## 작업 재개 절차

1. `AGENTS.md`와 `harness/project.json`을 읽고 `status` 실행.
2. [워크플로우](workflow.md)의 현재 단계에 맞는 역할로 작업.
3. 주장마다 출처 ID, 가설에는 가설 표시, 결과에는 검증 근거를 남김.
4. 단계 산출물을 검토하고 상태·결정·위험을 갱신.
5. `validate`와 해당 단계 gate 확인. 사용자에게 결과와 남은 결정만 보고.

`project.json`이 현재 상태의 기준이다. README와 체크리스트는 사람이 읽는 요약이다. JSON의 완료 항목은 증빙 파일과 그 SHA256을 요구하므로 파일이 바뀌면 재검토가 필요하다. 서명·개인정보 파일은 커밋하지 않으며 점검 결과만 기록한다.

2026-09-27 사용자 위임에 따라 Theme A Kitchen Gap을 선정했다. `기획/최종주제_선정.md`와 `기획/주제검증_결과.md`가 최신 기준이다. 현재 하네스는 관리·기록 검사와 후보의 최소 규칙 Skill을 포함한다. 자연어 요청에 맞춰 Codex가 절차를 수행하며 별도 자동 Agent 실행기가 있는 것은 아니다. 모델 API·원문 자동 추출·생성 품질은 아직 미검증이다. CI에는 저장된 후보 실험 출력의 재현 확인도 포함한다.

## 자료 구조

- `project.json`: 출처·후보·결정·위험·단계·접수 점검의 현재 상태.
- `research/topic_trial/`: 검증 계획, 실제 자료 요약, 구조화 입력, 실행 출력. `scripts/topic_trial.py --check`로 재현 확인.
- `workflow.md`: 기획·개발·검증·제출 역할 및 단계별 완료 조건.
- `기획/주제비교_2026-09-27.md`: Theme A/B 후보와 추천 근거.
- `기획/추가아이디어_비교.md`: 사용자의 추가 검토 요청을 반영한 최신 후보 비교.
- `research/problem_signals.json`: 사람이 검토한 공식 자료의 초기 문제 단서. 고객 VOC나 자동 추출 결과가 아님.
- `기획/추천안_구현검토.md`: 추천안 범위·입출력·시연·검증·위험.
- `기획/추천안_제안서초안.md`: 공식 6항목에 맞춘 초안. HWP 제출본 아님.
- `docs/마감대응계획.md`: 지금부터 제출까지 우선순위.
- `scripts/scenario_spike.py`: 웹 기반 추천안의 제약 검사 가능성을 확인하는 작은 실행 예제.

## 참고와 적용 범위

[harness-100의 Product Manager](https://github.com/jeongiryang/harness-100/tree/main/ko/46-product-manager)와 [LLM App Builder](https://github.com/jeongiryang/harness-100/tree/main/ko/41-llm-app-builder)의 역할 분리·단계 산출물·평가 구조를 참고해 새로 작성했다. 원 템플릿의 Claude 전용 호출이나 대규모 구조는 복사하지 않았다. 현재 역할은 한 에이전트가 순서대로 수행하며 자동 다중 에이전트 실행기는 아니다.

CI는 기록과 코드의 기본 검사를 자동 수행한다. 실제 조사·아이디어 평가·제안서 품질 검토는 이 절차를 따르는 Codex 작업과 팀 검토가 수행한다.
