# CORE001 계약 사례

development는 개발 계약 예시 6개, heldout은 원문·ID가 겹치지 않는 독립 사례 6개다. 모두 직접 작성한 synthetic 입력이며 공개 리뷰/실제 제품 성능의 증거가 아니다. heldout은 냉장고·식기세척기·전자레인지 사례를 포함한다.

- *.input.json: 원 요청·제품·모델/버전·원문/기능 snapshot. 실제 모델 평가 때 제공할 입력.
- *.fixture-output.json: 검사 경로를 재현하는 직접 작성한 판단 선언. 실제 모델 결과가 아니며 모델에게 전달하지 않는다.
- cases.json: 여섯 유형의 입력/fixture 파일 목록.
- expected.json: 예상 accept/hold/revise와 재실행 단계/위반 코드. 모델 프롬프트와 분리한다.
- schemas/: canonical 계약을 참조한 판단 입출력 Schema.
- check_cases.py: 입력/fixture 응답만 검사기에 전달하고, 계산한 결정과 별도 기대값을 대조한다.

정상 사례에도 기능의 존재와 남은 불편을 분리한다. 기능 중복은 concepts 단계 수정, 다른 모델의 원문은 hold, 상충 리뷰는 보류/질문, 누락 인용은 해당 단계 수정, 명세 변경은 옛 출력의 재사용을 거절한다.

실제 실모델 의미 판단·네 handler 등록·독립 강한LLM 비교·전체 E01 완료는 후속 작업이다. 이 폴더의 결과는 CORE001의 deterministic/fixture 검사 근거다. 재현 명령과 연결 규격은 docs/core/judgement-contract.md를 따른다.
