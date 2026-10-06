# CORE 판단 metadata 인계 — PM6015780670 / PR190

현재 CORE001/Agent envelope의 review_assessments, questions, hold_reasons가 공유 판단의 정본이다. DATA의 독립 Skill result가 같은 필드를 함께 제공하면 동일해야 한다. 극성·사유·배열이 다른 중복 표현은 어느 쪽도 선택하지 않고 VALIDATION_FAILED로 거절한다. 정확한 두 경로를 feedback으로 반환하고 원 model_calls/generated.data를 보존한다. 같은 공유 수정 최대2를 소비하며 상충 응답을 accept로 통과시키지 않는다. 새 enum/공통 계약/오류 코드는 추가하지 않는다.

유효한 result.uncertainty_assessments는 해당 envelope 리뷰의 uncertain/conflicting 근거 ID와 일치해야 한다. 동일 ID 중복/다른 극성이면 거절한다. 생성한 원 reason은 기존 hold_reasons, questions는 기존 questions, missing_information 원 문자열은 기존 unresolved로 그대로 복사·중복 제거한다. 결과는 held/hold이고 후보 생성은 멈춘다. 원 상세 evidence_id 연결은 generated.data/result/uncertainty_assessments와 Skill 결과에 남긴다. 외부 최종 계약에 새 missing_information 필드를 만들거나 사유·질문을 합성하지 않는다.

conflicting Need는 기존 judgement_contract.py의 complaint/conflicting 허용과 test_planning_agent.py의 상충 질문·보류 경로를 유지한다. 질문/사유/확인할 정보가 갖춰진 상충은 자료 확인을 위한 hold이며, NON_COMPLAINT_AS_NEED로 무조건 재시도시키지 않는다. positive/irrelevant/uncertain을 확인된 불편으로 치환하거나 forced accept하지 않는다. DATA PR190의 declared[eid] != complaint 조건은 이 기존 conflicting 예외와 맞춰야 한다. 질문이 없거나 상충을 해소했다는 근거가 없으면 기존 grounding/의미 검토를 통과하지 않는다.

DATA 다음 행동: 자기 PR의 need_extraction 검증·Skill 출력 규격·검사에 위 정합성과 conflicting hold를 반영한다. CORE의 model_client.py/prompt_context.py나 공통 계약은 수정하지 않는다. PM 공개 반례의 nested uncertain/top positive, 정상 uncertain metadata hold, 상충 Need hold를 전체 PlanningAgent까지 검사한다. CORE만 + 고정 DATA190 임시 조합에서는 130개 중 마지막 conflicting 정책 1개가 아직 실패했고 메타데이터 P1 관련 사례는 통과했다. 이 미병합 DATA 파일은 본인 worktree에서 수정하지 않았다.

WEB 다음 행동: DATA가 확정한 검사 코드/조건을 원 소스와 맞춰 한국어 registry에 연결한다. 본 CORE 수정은 기존 VALIDATION_FAILED를 사용하므로 새 코드 이름은 없다. missing_information은 output.unresolved, 원 질문/사유는 output.questions/hold_reasons, 세부 근거 연결은 원 생성/Skill 기록에서 읽는다. registry만 수정한 것을 의미 문제 해결로 기록하지 않는다.

PM 다음 행동: 본 CORE 작은 단위와 DATA 정책 반영 뒤 frozen 반례·전체 Python/web CI·실제 통합을 재검수한다. 대형 실모델 반복은 고정 model digest/source/input/잔여 누적 예산·중계 확인을 인계한 뒤 진행한다. 원 비용/실패·독립6사례·R6 ledger를 반복하거나 초기화하지 않는다.
