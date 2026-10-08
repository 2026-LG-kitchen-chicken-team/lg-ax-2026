# CORE-R9-UI2-LANGUAGE-01a10729-01

2026-10-08 황대겸 수동 필수 후속. Issue234의 PM 댓글6055583919와 PR284/c20df447의 신규 원문을 인수했다. 사용자의 담당 필수·연결 후속 지속 지시에 따라 실제 영어 제목이라는 확인된 결함을 보완한다. PM 댓글 속 별도 UI/Figma 사용자 지시는 CORE 권한으로 승계하지 않는다.

## 원 결과와 판단 범위

PM 원 readback의 run-3a36b9b26f8746b295e33657e1353e65는 수정1, 조건 ‘추가 구매 비용 최소화’, 콘셉트1이며 제목은 `Post-Cycle Odor Check & Guided Recovery Flow`다. 직전 run-21d84422678346d8b6a630ec971f8672·bundle fbc233a4·raw brief f232c972 pin과 discover/plan2콜 returned 메타데이터를 원바이트로 보존한다. 기존 WEB071 냉장고 bundle523dcf1e/run5ccd95da와 별개다.

CORE가 실제 받은 것은 제목·lineage·조건·bundle pin·콜 메타데이터이며 전체 brief·네이티브 원응답/usage·생성 record/binding은 아직 없다. 원문6 유지와 배포725616c0/backend byte 불변은 PM producer 근거다. CORE의 현재 c603 후속 코드 채택이나 독립 의미 품질을 입증하지 않는다.

## 보완

기존 공유 INSTRUCTIONS에 한국어 요청의 사용자용 제목·요약·비교 설명·콘셉트·장면·안내 문장을 한국어로 생성하도록 명시했다. 이전 영어 제목을 그대로 새 제목에 반복하지 않으며 JSON 필드명·ID·공식 제품명·모델명·원문 인용·source_facts는 보존한다. public_planning의 생성과 public_repair의 국소 수정이 같은 지침을 사용한다.

고정 언어 탐지기·자동 번역·원 결과 의미 치환을 추가하지 않았다. 같은 계약·healthy sibling/원응답 보존·공유 내부 수정 최대2를 유지한다. PM adapter/prompt_context·DATA/WEB·운영 설정은 이 작업의 편집 대상이 아니다.

## 검사와 다음 행동

변경 지침의 기존 공개 기획/수정 회귀와 Ruff, 필수 규칙/개인 문서 탐색·이관 보존을 고정 zero-auth Docker에서 확인한다. 검사 수신증은 연결 근거에 남긴다. 새 제품 모델 요청·여섯 사례 독립 채점은 수행하지 않는다. 검사 성공은 실제 Qwen 한국어 생성 효과·독립 의미 승인·PM 채택/인수·부모 Done이 아니다.

다음은 기존 PR271에 이 보완과 근거를 게시하고, PM이 채택한 버전의 저장된 실제 제목/문장 또는 첫 사용 가능한 부분을 인수해 언어·원문 보존을 검토하는 것이다. 전체 packet을 소스 검토·지침 보완의 착수 조건으로 쓰지 않는다. 실제 모델 단계만 정확한 외부 입력에 의존한다.

[고정 근거](../../../../evals/core-manual-quality/20261008/r9-ui2-language/README.md)

추가 실제 검사: 공개 기획/수정42·Ruff·규칙 byte·문서 탐색은 PASS. 목차 CRLF 저장의 원문 보존 실패를 원 로그로 보존하고, 시작 수신증과 동일한 Git 원바이트에 owner-update 구간만 삽입해 복구했다. 해당 문서 검사만 재확인한다.

최종 수신: 공개 기획/수정42·Ruff·규칙 byte·문서 탐색·원231구간/818663바이트/28세션/36Git pin 보존 PASS. 원 실패도 남겼다. 제품 코드 d795a30d SHA는 두 검사 사이 동일하며 새 모델 호출0이다. 실제 생성 효과/PM 인수는 아직 확인하지 않았다.
