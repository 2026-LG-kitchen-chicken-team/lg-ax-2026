# CORE R3 — 원문 대조와 단계별 선언 모순 보완

배정: [PM-20261006-CORE-QUALITY-R3](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/11#issuecomment-6011523496).
원 결과는 PM169가 보존한 합성 개발 자료다. 작성자의 원문 대조이며, 기존 여섯 사례의 독립 AI 채점을 반복하거나 새 독립 평가 완료로 주장하지 않는다.

## 고정 원본

- 제품 실행 코드: `45fe0f23afb9c68e115088cef9e10cd122d181f1`.
- 원 결과 인수 commit: `9c7188a29138f43b377c2cac763ab954bc802330`; PM169 최종 head `46df0ca176da6a6629b177f2358b935682770505`, 실제 병합 main `2636999be65012dbced6990628f9d65c40ac9fbc`에 포함됨.
- [원본 manifest](../../../pm-prototype/20261006/finite-model-study/source-manifest.json), [CORE→DATA 원문/ID 인계](source-handoff.json). 파일 SHA·입력 원문·product/model/version/source_id/locator·응답 위치를 함께 유지한다. 해시는 실행 코드 commit과 별개다.
- 원 실패3건 대조를 [Issue11](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/11#issuecomment-6011878264)에 먼저 제출했고, DATA 요청에는 [Issue13](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011902780)으로 연결했다.

## 원문·필드·기대 대응·실제 실패

| 반례 | 원문/필드 | 기대 대응 | 보존한 실제 실패 |
|---|---|---|---|
| 명시 불편과 긍정 선언 | 냉장고 REVIEW-EVIDENCE-001: “음료를 쏟으면 선반 위 식품을 모두 옮겨 청소해야 해서 번거로워요.” | 불편을 추출한다면 해당 리뷰의 불편 선언과 인용이 일치해야 함 | 8B 냉장고와 전자레인지 모두 review_assessments를 positive로 쓰면서 같은 리뷰를 Need 근거로 인용. 각각 9호출/수정2 후 failed, NON_COMPLAINT_AS_NEED |
| 긍정 정상 대조 | 냉장고 REVIEW-EVIDENCE-006: “나는 선반을 쉽게 꺼내서 청소하고 있어서 크게 불편하지 않아요.” | 긍정 리뷰에서 불편을 만들어내지 않음. 합당한 무후보 보류의 의미 검토 유지 | 코드가 원문을 보고 polarity를 complaint로 바꾸지 않는다. 기존 긍정/상충/불명/자료부족 보류 회귀를 유지 |
| Need↔Gap 의미 오연결 | 전자레인지 NEED-001은 REVIEW-EVIDENCE-034(시간·출력 반복 입력)만 인용. GAP-002는 035(저장 기능을 몰랐음), GAP-003은 036(호출 버튼 찾기 어려움)의 remaining_pain인데 둘 다 need_id=NEED-001 | 입력 Need와 인용 리뷰가 다루는 문제에 Gap을 대응. 다른 문제는 해당 Need에 연결하거나 먼저 Need를 재추출 | ID 존재/모든 근거 인용만으로 의미 일치를 증명할 수 없음. 단계 지시/Skill에서 문제 대응 명시; 코드의 자동 의미 재매핑 없음 |
| 희망 결과와 현재 지원 혼동 | MANUAL-001: “선반은 분리하여 세척할 수 있습니다. 선반을 분리하기 전에 위의 식품을 모두 옮겨 주세요.” FEATURE-001은 선반 분리. 27B GAP-003 등은 찾기/임시 공간 희망을 현재 기능 미지원으로 평가 | 선택한 선반 분리의 현재 지원과 별도 희망 결과의 미충족을 구분. 지원돼도 불편은 remaining 가능 | 기존 27B: SUPPORT_BASIS_MISMATCH/SUPPORT_UNKNOWN 및 후보 근거 거부. PM enum-guide 추가 실행도 미확인 Gap5개가 남아 held. 정상 자료부족 보류/품질 성공으로 확정하지 않음 |
| 빈 후보와 평가 불일치 | 8B rejected_output.concepts=[]인데 concept_assessments는 CONCEPT-001~003의 duplicate 선언 | 실제 반환 후보 ID 집합과 평가 ID 집합 일치. 후보0이면 평가0 | ASSESSMENT_COVERAGE. 단계에서 바로 재시도하며 제외한 가설을 실제 후보로 만들지 않음 |
| 새로운 작동과 중복 선언 | 27B CONCEPT-001 reason: 오염 구역만 청소하여 전체 식품 이동 조건 변경; CONCEPT-002: 분리 중 임시 공간의 새 구조. 둘 다 duplication=duplicate | 작동/사용 조건의 차이를 현재 기능 원문과 비교하여 선언. 새 가설의 실행 가능성은 후속 검증 | DUPLICATE_CONCEPT/CONCEPT_WITHOUT_CONFIRMED_GAP. distinct 강제 치환 없음; 기존 후보별 리뷰+설명서 의미 검토 유지 |

원3건: 8B 냉장고 9호출/44,387tokens failed, 8B 전자레인지 9호출/21,673tokens failed, 27B 냉장고 3호출/13,284tokens held. 실행 종료0·중계 실패 없음과 판단 품질 실패를 구분한다. 추가 enum-guide 27B는 다른 PM 실행이며 원3건 성적을 대체하지 않는다.

## 작은 보완의 범위

`stage_alignment`는 기존 NON_COMPLAINT_AS_NEED·ASSESSMENT_COVERAGE·DUPLICATE_ID 일관성 규칙을 현재 단계에서 검사한다. 극성/지원/중복 의미를 코드가 추정하지 않고, 실제 ID·선언과 누락/과다/중복 ID를 VALIDATION_FAILED.details에 전달한다. 생성 원문/필드·스키마·pin·최종 검사·의미 검토·공유 수정 최대2를 유지한다. 정상 자료부족 보류는 성공으로 바꾸지 않는다. PM model_client.py/prompt_context.py, 공통 계약, WEB/DATA 파일은 수정하지 않는다.

회귀는 원 응답을 MockTransport로 재생하는 fixture다. 원본 bytes와 원3회 need_extract 응답을 대조하고, 모순을 반복하는 동일 응답이 compare/concept로 진행하지 않는지 검사한다. 실제 모델 호출 절감이나 정상 후보 성능 개선을 측정한 결과가 아니다.

## 실제 개별 검증

[검사 수신/시도별 manifest](checks/manifest.json): 전체1426 tests, 실패0/오류0/skipped3; 새 단계 재생6건 포함. 제품 Python·Skill·입력 SHA를 실제 작업본과 전체/정적 snapshot에 대조했다. 규칙·기록 이관·하네스·계약·phase2·원본 해시·준비 입력3건·stdio MCP 도구5회·Ruff가 통과했다. 원 회귀 실패/격리 runner 수정 전 실패는 삭제하지 않았다. 실제 모델 신규 호출0이다.

## 미완료

고정 모델 정상1·조건변경1·적절한 보류1 실제 실행과 같은 실행의 WEB/MCP 확인, 독립 의미 품질 검수·PM 인수·부모 Done은 남아 있다. 준비한 [R2 입력/원본](../r2/README.md)을 보존한다. 중앙 잔여/토큰/STOP은 사용자 지시에 따라 미정이고 임의 cap·증액·비용 초기화를 만들지 않는다. 새 모델 선택이나 대형 반복 실험을 하지 않았다.
