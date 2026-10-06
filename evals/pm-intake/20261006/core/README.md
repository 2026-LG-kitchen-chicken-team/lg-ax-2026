# PM CORE intake · 2026-10-06

고정 main `02f9a643e92c4665f2f0f71a5690f9ed6ed28930`에 PR142와 PR145의 선택된 코어를 인수한다. 원 작성자의 전체 기록은 `provenance.json`의 고정 SHA 링크로 보존하며 개인 기록을 다시 작성하지 않는다. PR97/136의 제외 조건·기능 지원과 잔여 불편 분리 수정도 검토했고 최신 일반화 및 의미 검토 경로에 연결했다.

`PlanningAgent`는 exact model/document scope → frozen source reads → need_extract → product_compare → concept_draft → structural review → semantic/no_candidate review를 실행한다. 검토가 수정을 요구하면 설치된 한 `RevisionSession`의 review_revision을 사용한다. 단계 재실행과 수정 Skill은 한 CorrectionBudget의 최대 2회를 공유하고 실패한 실제 시도도 소비한다. 새 요청은 원본·제외 조건을 고정한 별도 실행이며 내부 회차 0에서 시작한다. 자료·모델 출력은 도구·backend·경로·권한을 부여하지 못한다.

`quality-inputs.json`은 독립 평가용 답안이 아닌 후속 검토 조건과 고정 입력/hash이다. `cases/{fridge,dishwasher,microwave}-{normal,changed}.input.json` 6개는 기존 합성 자료 원본 `synthetic.dataset.json`을 사용한다. normal과 changed는 같은 제품·문서·원문이며 changed에서 제외 조건만 변경했다. 원문은 LG 제품 사실·실제 고객 수요의 증거가 아니다. 공개 설명서만 있는 DATA 입력은 별도로 인수하며 리뷰가 없으면 Need를 만들지 않고 모델 호출 전에 보류한다.

명시적으로 준비한 모델 환경에서 후속 실모델 실행의 CLI는 다음 형태다. endpoint/model/digest는 호출자가 승인된 환경에서 제공하고 이 폴더에는 로그인·endpoint·비밀을 넣지 않는다.

```text
python -m lgax_core.planning_agent --dataset evals/pm-intake/20261006/core/synthetic.dataset.json --input evals/pm-intake/20261006/core/cases/fridge-normal.input.json --output NEW_OUTPUT.json
```

입력/출력 경로는 별개이며 매번 새 출력에 저장한다. 기본 standalone Skill CLI는 임의 모델을 시작하지 않는다. PlanningAgent의 `model_calls` 원문 전송/응답, `skill_trace.records` 실제 handler 호출, `correction_budget.attempts`, `revision_session.audit`, `semantic_reviews`, `no_candidate_reviews`를 함께 대조한다. fixture, live_model, 규칙 검사, 독립 품질 판정을 구분한다. 실모델 3제품 정상/변경 반복, 독립 평가와 강한 일반 LLM 기준선은 미완료이다.

`actual-fridge-normal-compare-rejected.json`은 인수 source `37f7e3fd0e76eff8115941e7d456ffdf6424d0d4`의 실제 8B 냉장고 정상 실행에서 나온 Need/Compare 응답과 원 입력을 보존한다. 설명서 MANUAL-001이 실제로 입력에 있었지만 모델은 모든 Gap에서 이를 인용하지 않았고 기존 선반 분리 기능을 명시적 미지원으로 잘못 판단했다. 원래 실행은 두 호출 뒤 `GAP_MANUAL_MISSING`/`UNSUPPORTED_WITHOUT_MANUAL`로 보류됐고 내부 수정 회차는 0이었다. 이 JSON의 원본 출력 hash는 원 실행과의 대응이며, 새 테스트에서 응답을 재생하는 것은 실모델 재실행이나 수정된 결과의 품질 증명이 아니다.

후속 좁은 수정은 정확한 제품·문서·자료 종류의 연결된 설명서 원문이 모두 이미 있을 때만 누락 비교를 같은 최대 2회 예산으로 모델에 다시 요청한다. 원문 ID를 자동 추가하거나 판단을 자동 승인하지 않는다. 원 자료가 없거나 비교 근거가 미언급·상충·불명확이면 보류를 유지한다. 별도 후속 문제로, 구조상 유효한 `held` 결과는 현재 semantic/no_candidate review 경로에 들어가지 않아 모델이 만든 근거 없는 보류 사유를 의미 검토로 잡지 못할 수 있다. 이번 수정은 그 범위를 확장하지 않으며 원 실패의 질문·보류문을 후속 재현 근거로 보존한다.
