# PM-R5-SEMANTIC-PROMPT-20261007 근거

원 study source는 `4f897394ae224e43dc4c7f0c9d224f4dfa92c0a2`이고 실제 정상 output 원SHA는 `5cafe37097fb21ace6b9fafb74ba05f86405a43f93b59fa843c1c0d375ef756f`다. 다섯 번째 model_calls 행의 로컬 오류·payload/current_output/request_context/기존 prompt/schema만 그대로 복사한 `semantic-prompt-counterexample.json` SHA는 `85d30432f624e988b9ab0dd2b834723ac92887bb0f7845fd92377a6b12850a69`다. 그 행에는 모델 raw response가 없으며 원 output은 수정하지 않았다.

검사 source `0df1f384ebb1f44d13744b8f3b35df821bcfd00e`, execution ID `pm-r5-semantic-prompt-d1999daa6da34663bd31a51f435b68e7`, archive SHA `440852a305f908e2bc90f85a46835ebf019b9959228e94ca82933224c140edbe`, source manifest SHA `abd693be04478b06d82a85d0b4a7b93813461a09801dd61e12dafc2259c99245`다. receipt SHA `651be0be67f6ff67eb4473a5e3c0fb98caf03a0cd8cb0fd31fdd33bd82730a55`와 원 JSON바이트를 그대로 보존한다.

검사 wrapper는 저장소 밖 `work/r5_semantic_prompt_validator.py` SHA `c803805a593ee747ef7fb43f67cfa199320e689993e969267798ddfc53ec5751`다. 기존 root 검토 wrapper에서 실행 ID 접두사와 의미 문맥/모델 요청 회귀 모듈만 추가했고 고정 orchestration source-proof 전체 대조, Docker image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`, validator uid1000, auth/profile 없음, network none, readonly root/source, source_changed[]를 유지했다. host에서는 inert Git archive와 stdlib metadata만 다뤘고 저장소 코드는 Docker에서만 실행했다.

197건 PASS에는 원 MANUAL001/REVIEW008 누락·질문 없는hold·NEED006 모순 회귀, 새로운 실제9Need/9Gap/3후보 요청 준비, links19필드 전부 zip 복원, 모든 원문·선언·필수근거/schema 보존, submitted projection과 model_calls.prompt_context 일치, full request_context와 trace 보존, 기존 prompt/modelclient 검사가 포함된다. 출력23,793자/33,142바이트는 capturing adapter에 전달된 완성 formatter 결과다. 기존 상한24,000/45,000 및 ctx16384/output8192/seed42를 유지한다.

새 모델 생성0·네트워크0·자동 재시도0·품질 승인false다. 실제 모델이 표를 정확히 해석한다는 검증, 변경/부족의 중단 의미 검수, 더 큰 문맥 적합성, 독립 최종 인수·운영 반영은 완료되지 않았다. 과거155 PASS 및 원 실패·중단 사용량·unknown 예약 자료는 보존한다.
