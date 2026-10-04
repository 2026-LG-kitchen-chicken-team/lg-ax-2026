# CORE002 후속: 제외 조건·기획 가설의 별도 의미 검토

새 판단 코드의 실제 LLM 실행·검증은 미완료이며, 사용자 지정에 따라 PM 정이량이 이 Draft PR을 이어받아 진행합니다. PM의 PR58 원 실행에서 제외 위반을 발견한 사실과 이 변경의 새 실모델 검증을 구분합니다. 배정은 `PM-20261005-CORE-002-SEMANTIC-REVIEW` / Issue #8입니다.

## 문제와 처리

PM의 `workspace-live.json` 변경 실행은 수정 회차2에서 계약 accept였지만 `CON-002`는 “자동 세척 장치 제안” 제외 조건에 대해 “자동 세척 모드 추가”를 제안했습니다. 현재 설명서는 기존 부품만으로 실행할 모드라는 근거를 제공하지 않습니다. 원 입력/원 출력은 보존합니다.

`PlanningAgent`는 기존 계약 검사 통과 뒤 후보가 있을 때 같은 명시적 모델 클라이언트로 **별도 semantic_review 호출**을 수행합니다. 생성 단계의 distinct 선언을 의미 준수로 사용하지 않습니다. 원 요청/후보·현재 자료·기능을 전달하고 입력/출력 해시, 실제 전송 prompt·schema·raw completion·pin metadata를 기록합니다. 모델이 검토 verdict를 생성하고 Python 검사는 그 선언의 완전성과 원문 일치를 검사합니다. 의미 정확성은 PM의 실제 독립 검토가 필요합니다.

| 검토 | 반드시 기록할 항목 | 완료 경계 |
|---|---|---|
| 각 후보 × 각 제외 조건 | 후보 ID, 조건 index/원문, 후보 원문 인용, compliant/violation/uncertain, 판단 이유/원문 근거 | 누락·중복·다른 조건/후보 인용은 거절 |
| 각 후보 × 기획 품질4기준 | 작동 방식, 현재 기능과 차이, 미검증 가정, 근거 없는 사실/효과 단정 여부와 인용 | satisfied/violation/uncertain |
| 불확실성 | 확인할 실제 질문 | 후보 없는 held로 종료 |
| 확정 위반/잘못된 검토 | 위반한 조건·후보·이유를 concept 단계 feedback으로 전달 | 기존 계약 검사와 같은 최대2회 예산 |
| 두 번 수정 후 잔여 위반 | 마지막 후보/검토/오류 원본 보존 | failed, 내보내는 후보는 비움 |
| 연결/pin 실패 | 오류 및 마지막 미검토 후보 별도 보존 | 우회/계약 accept fallback 없이 종료 |

후보0개는 기존 정상 사유·모든 불편 해결·보류 경계를 유지하며 의미 모델 호출을 추가하지 않습니다. 후보가 있으면 제외 조건0개라도 품질 검토는 수행합니다. 정상 후보 경로의 호출은 기존3회+별도 검토1회이고, 정상 생성 뒤 의미 위반으로 후보 생성/검토만 두 번 다시 하는 경로는 총8회입니다. 다른 단계 실패의 실제 호출 수는 trace로 확인합니다. 같은 수정 예산을 공유하며 별도의 두 회차를 더 얻지 않습니다. 실제 토큰/지연은 전체 호출·실패/재시도를 포함해 PM이 측정합니다.

`semantic_review.py`는 제품별 금지어·미리 작성한 판정을 사용하지 않습니다. literal 검사는 문자열 인용의 일치 여부이며 의미 판단의 대체가 아닙니다. 새 후보 가설은 허용하고 제조 가능성/효과 미검증을 가정으로 남기도록 별도 검토합니다. 자동 사용자 승인/후보 선택은 하지 않습니다.

## 결과와 소비자

공통 JSON Schema·Skill 계약·API/웹 코드는 변경하지 않습니다. 내부 planning_execution에 `semantic_reviews`와 review trace/model call이 추가되며 기존 decision/status/출력 후보 경계에 반영됩니다. review_judgement trace는 실제 기존 검사 결과를 보존하고 최종 review_decision/semantic_review를 별도로 기록합니다. 기존 Workspace runner는 이 PlanningAgent를 사용하므로 다음 PM 검증에서 새 검토가 적용됩니다. 기본 request-only/미구현 Skill 경로는 그대로입니다. Draft55의 별도 review_revision callback 통합은 CORE003 후속입니다.

## 재현 및 PM 인수

```powershell
uv run python -m unittest discover -s tests -p test_semantic_review.py -v
uv run python -m unittest discover -s tests -p test_planning_agent.py -v
```

테스트의 reviewer 응답은 authored fixture입니다. PM의 원 live 출력에 대한 기존 계약 accept 재현과 불확실 선언을 받아 hold로 끝나는 경계를 확인했으며, 새 모델이 실제로 위반을 탐지했다고 주장하지 않습니다.

`evals/core-exclusions/independent/`는 정상·변경 제외·부정문·유사어·모호한 모드·상충 조건의 새로운 합성 입력/대응 dataset입니다. 개발 원문/예상 응답과 분리하고 실제 응답은 넣지 않습니다. changed_exclusion.before는 같은 자료의 이전 요청입니다. reviewer-only는 모델에 제공하지 않습니다.

PM이 승인된 기존 연결·모델/출력 예산을 설정한 뒤 실행할 예시:

```powershell
uv run python -m lgax_core.planning_agent --input evals/core-exclusions/independent/negation.input.json --dataset evals/core-exclusions/independent/negation.dataset.json --output private/runtime/exclusion-negation-live.json
```

각 cases.json 항목은 해당 input/dataset 쌍을 사용합니다. changed_exclusion.before는 changed_exclusion.dataset.json과 짝을 이루며 before/after 결과를 서로 다른 경로에 보관합니다. 기존 원 출력은 덮어쓰지 않습니다.

PM은 기존 승인된 Qwen 연결/digest와 충분한 전체 출력/문맥 예산에서 정상/조건 변경/독립6입력을 실제 실행하고, 조건별 원 인용·판정과 원문 의미를 별도로 검토해야 합니다. 기존 위반은 위반 수정 또는 모드/장치 불확실 보류로 종료해야 합니다. 부정문/유사어/조건 충돌의 실제 원 응답·모든 호출/수정/종료·실패·코드/모델/자료 버전을 보존합니다. 생성과 검토에 같은 모델을 쓰므로 편향을 공유할 수 있으며 trace 완비가 의미 품질 증거는 아닙니다. 실제 결과에서 실패하면 담당 코어가 후속 수정합니다.

이번 근거는 partial/fixture/replay이며 CORE002/003 완료/PM 검수·병합·통합 성공은 별도입니다.
