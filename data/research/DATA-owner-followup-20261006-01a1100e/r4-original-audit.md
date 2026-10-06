# 새 R4 고정 결과별 원문 대조

새 모델 호출 0. 원 출력·입력·데이터·9개 prompt/raw SHA를 대조했다.

|결과|원문 ID/텍스트 일치|상태·질문|인용·빠진 근거·기능 설명 검토|
|---|---:|---|---|
|fridge-changed|11/11|failed / HOLD_WITHOUT_QUESTIONS / questions[]|Need 9개의 ID는 원문에 존재. 003·007은 선반 청소 situation과 맥락 차이, 008은 희망 문장. 006은 긍정 문장이므로 누락 불편으로 단정 불가. 기능·gap·concept 단계 미도달.|
|fridge-normal|11/11|failed / HOLD_WITHOUT_QUESTIONS / questions[]|Need 9개의 ID는 원문에 존재. 003·007은 선반 청소 situation과 맥락 차이, 008은 희망 문장. 006은 긍정 문장이므로 누락 불편으로 단정 불가. 기능·gap·concept 단계 미도달.|
|fridge-missing-manual|10/10|failed / HOLD_WITHOUT_QUESTIONS / questions[]|Need 9개의 ID는 원문에 존재. 003·007은 선반 청소 situation과 맥락 차이, 008은 희망 문장. 006은 긍정 문장이므로 누락 불편으로 단정 불가. 기능·gap·concept 단계 미도달.|

## Need별 연결

|결과|Need|원문 ID|pain 원문 동일|관찰|
|---|---|---|---|---|
|fridge-changed|NEED-001|REVIEW-EVIDENCE-001|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-changed|NEED-002|REVIEW-EVIDENCE-002|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-changed|NEED-003|REVIEW-EVIDENCE-003|True|원문은 안쪽 식품 찾기·수납 정리. 고정 situation의 선반 청소 맥락과 차이.|
|fridge-changed|NEED-004|REVIEW-EVIDENCE-004|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-changed|NEED-005|REVIEW-EVIDENCE-005|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-changed|NEED-006|REVIEW-EVIDENCE-007|True|원문은 가족의 정리 표시 이해 차이. 선반 청소 맥락을 직접 뒷받침하지 않음.|
|fridge-changed|NEED-007|REVIEW-EVIDENCE-008|True|원문은 빠른 청소를 바라는 문장. 실제 발생 불편·빈도·효과로 확대할 수 없음.|
|fridge-changed|NEED-008|REVIEW-EVIDENCE-009|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-changed|NEED-009|REVIEW-EVIDENCE-010|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-001|REVIEW-EVIDENCE-001|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-002|REVIEW-EVIDENCE-002|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-003|REVIEW-EVIDENCE-003|True|원문은 안쪽 식품 찾기·수납 정리. 고정 situation의 선반 청소 맥락과 차이.|
|fridge-normal|NEED-004|REVIEW-EVIDENCE-004|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-005|REVIEW-EVIDENCE-005|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-006|REVIEW-EVIDENCE-007|True|원문은 가족의 정리 표시 이해 차이. 선반 청소 맥락을 직접 뒷받침하지 않음.|
|fridge-normal|NEED-007|REVIEW-EVIDENCE-008|True|원문은 빠른 청소를 바라는 문장. 실제 발생 불편·빈도·효과로 확대할 수 없음.|
|fridge-normal|NEED-008|REVIEW-EVIDENCE-009|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-normal|NEED-009|REVIEW-EVIDENCE-010|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-001|REVIEW-EVIDENCE-001|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-002|REVIEW-EVIDENCE-002|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-003|REVIEW-EVIDENCE-003|True|원문은 안쪽 식품 찾기·수납 정리. 고정 situation의 선반 청소 맥락과 차이.|
|fridge-missing-manual|NEED-004|REVIEW-EVIDENCE-004|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-005|REVIEW-EVIDENCE-005|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-006|REVIEW-EVIDENCE-007|True|원문은 가족의 정리 표시 이해 차이. 선반 청소 맥락을 직접 뒷받침하지 않음.|
|fridge-missing-manual|NEED-007|REVIEW-EVIDENCE-008|True|원문은 빠른 청소를 바라는 문장. 실제 발생 불편·빈도·효과로 확대할 수 없음.|
|fridge-missing-manual|NEED-008|REVIEW-EVIDENCE-009|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|
|fridge-missing-manual|NEED-009|REVIEW-EVIDENCE-010|True|근거 ID·원문 일치. 요구의 의미 강도는 별도 판정.|

기능 설명·기존 기능 지지·잔여 불편·콘셉트가 비어 있어 그 의미 정확성은 이번 결과에서 평가할 수 없다. 정상/조건변경/설명서 누락의 적절한 accept/hold는 미완료다.

기존 27B GAP003/006의 unmentioned/unsupported 조합은 SUPPORT_BASIS_MISMATCH이며 계약상 insufficient_evidence로 구분한다. 원 고정 결과는 수정하지 않았다.
