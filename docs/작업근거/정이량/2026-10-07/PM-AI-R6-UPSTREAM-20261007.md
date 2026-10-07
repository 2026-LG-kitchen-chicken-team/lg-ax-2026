# PM 보조 AI: 원문 범위·Need/Gap 의미 검수 보완

사용자의 전체 수정 지시와 PM 배정에 따라 정이량 보조 AI가 구현했다. 황대겸의 수행·원 기록·공식 Done을 대신 갱신하지 않았다.

실제 `8ec1e8a51faabd6db032e52245680bef4229f93f` 정상 합성 개발 사례는 5회·33,237토큰으로 `completed`였지만 독립 검수에서 세 의미 오류가 남았다. 방법 설명문 존재를 방법 발견성 해결로 판단한 GAP-004, 선반 매뉴얼을 바구니 기능의 명시 지원으로 사용한 GAP-005/CONCEPT-003, 욕구만 있는 RE008에 식품 전체 이동 경험을 추가한 Need다. 기존 RE008 차별성 인용 누락은 이번 후보에서 재현되지 않았다. 전달 완주와 의미 정확성을 구분하며 원 실제 실행·비용·품질 FAIL은 보존했다.

수정은 CORE 내부의 새 active 의미 report에 모든 Need와 모든 Gap의 원문 대조를 필수로 넣는다. 후보에 포함되지 않은 resolved Gap도 검수한다. 모델은 원문의 경험/욕구, 자료 유형, 기능 대상·조건, 희망 결과의 충족 여부를 판단한다. 코드는 전수 ID·해당 객체의 원 문구·현재 자료의 인용 연결을 검사하고 자동 인용이나 의미 verdict를 생성하지 않는다. 수정 사유는 Need/비교 단계에 맞게 전달하며 기존 하나의 RevisionSession과 최대 두 번 수정 예산을 유지한다. 과거 고정 report는 기존 재생 모드로 읽고 새 active 경로는 검수 누락을 거절한다.

기존 한도 가까이에 있던 prompt에는 Need/Gap·판정·희망 결과의 반복 키를 columns/values로 전달한다. 원 필드·문장은 모두 정확히 복원하며 sources/features/후보와 필수 근거는 그대로다. 전체 request_context와 trace는 압축하지 않는다. 실제 원 9 Need·9 Gap·3 후보의 adapter 제출 prompt는 22,856자·UTF-8 33,140바이트로 기존 24,000자/45,000바이트 한도를 지켰다. ctx16,384·출력8,192·고정 모델·seed42·max2 정책은 바꾸지 않았다.

검사 대상 코드 `297c65a48c81137adddd317e194a68b335ae27c1`에서 고정 Docker, network=none, zero-auth, readonly source로 181 unit 검사와 변경 Python Ruff 7개 파일이 통과했다. 소스 3,762개 전후 변경은 없고 모델/네트워크 호출은 0이다. 첫 검사에서 새 active report를 기존 재생 모드로 읽던 테스트 두 곳과 import 정렬 두 곳이 실패했으며 원 수신증을 보존하고 명시 모드와 정렬만 보완했다. [고정 검사 근거](../../../../evals/pm-prototype/20261007/r5-core/upstream-validation.json)를 따른다.

원 반례는 새 [파생 regression fixture](../../../../evals/pm-prototype/20261007/r5-core/normal-8ec-upstream-counterexample.json)로 보존했다. 인간이 표시한 세 오류와 검수 누락·전수 coverage·원 인용·단계별 feedback·보류 질문·max2 종료를 검사한다. fixture의 다른 consistent 행은 protocol 시험용이며 그 의미를 승인한 결과가 아니다. 새 구현의 실모델 의미 품질은 아직 미검증이다. changed/missing-manual 재평가, 독립 평가 표본 성능, 실제 구매 SKU·수요·운영 배포·참가작 31요구 완료는 주장하지 않는다. 독립 코드 검수·병합·새 유한 실모델 인수는 PM이 별도로 처리한다.
