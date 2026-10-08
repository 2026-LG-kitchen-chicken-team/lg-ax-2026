# 조건 변경 보고 일부 의미 검수 — DATA-W1-01a108a8-0823-9b837714

원문 의미 판단은 W1/Codex가 수행했다. 프로그램은 위치·span·참조만 검사하며 Gold 정확도·최종 채점이 아니다. 기존 CORE/W1-F1/F2/F3의 코드 검사를 재실행하지 않았다.

[구조화 표](changed-semantic-review.json) · [원문 위치](source-anchors.json) · [실행 조건](execution-conditions.json)

| ID | 기준·출력 위치 | 판정 | 원문 대조·한계 | 후속 |
|---|---|---|---|---|
| C01 | 조건 충돌 · /runs/1/proposed_changes | 상충 | 추가 조건은 하드웨어 변경 없이 개선인데 받은 제안 필드가 턱 높이 재설계다. | 수신된 보고 필드의 충돌은 확인하고 변경 전체 원 JSON의 독립 판정은 미확인으로 유지한다. |
| C02 | 제목·작동 방식 · /runs/1/concept_title | 상충 | 수납 가이드라는 변경 제목과 구조 조정을 요구하는 mechanism/proposed_changes가 맞지 않는다. | 제목 변경을 제약 충족·비구조적 개선으로 해석하지 않는다. |
| C03 | 부모·회차 · /runs/1/previous_brief_id | 확인 | 부모 ID가 새 냉장고 정상 brief와 연결되고 revision은1이다. | 기존 요청 정상1f83/조건754268과 다른 실행 가족임을 보존한다. |
| C04 | 동일 입력 인정 · /runs/1/same_input_scope_and_source_facts_as_revision_0 | 미확인 | 같은 scope/facts라는 true는 WEB 보고다. 실제 변경 원 JSON/입력 wire는 없고 조건도 추가됐다. | 같은 조건 A/B 또는 canonical7 Agent/일반LLM 동일 입력 비교로 인정하지 않는다. |
| C05 | 완료·검증 상태 · /runs/1/status | 부분 지지 | complete/validation_issues 빈 배열/repair0은 보고된 구조 상태이며 C01 충돌을 해소하지 않는다. | 성공 표시를 조건 준수·품질·PM 승인·Gold 정확도로 승격하지 않는다. |
| C06 | 인용·기간·주체·누락 · /runs/1/note | 미확인 | 키 필드만 복사된 보고이며 변경 요약/인용/comparisons/전체 source_facts 값은 없다. | 정상 내용이 그대로였다고 가정해 변경 결과의 의미를 대조하지 않는다. 전체 또는 정확 부분 필드를 W3로 요청한다. |
| C07 | 모델·설정 · 해당 필드 미수신 | 미확인 | 변경 결과의 model/digest/context/sampling/output/native 설정 pin은 /runs/1 일부 보고에 없다. | 정상 runtime 설정을 변경 원파일에서 확인한 값으로 복사하지 않는다. |
| C08 | 실패·재시도·usage · /runs/1/call_count | 미확인 | 44.4초/2call/repair0은 WEB 보고이며 모든 native 호출·실패·retry·토큰 원장은 받지 못했다. | 미수신 사용량은 null이고 다른 PM native4run/9콜을 이 실행의 usage로 대입하지 않는다. |
