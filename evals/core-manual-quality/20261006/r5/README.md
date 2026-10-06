# R5 — 추출하지 않은 불편 리뷰 ID의 수정 피드백

기준 main `fdb0ea2667c80ead07b38fbcf5ca58df292bc7e9`. 기존 `COMPLAINT_NOT_EXTRACTED` 거절 동작에 누락 리뷰 ID를 연결하는 작은 CORE 보완이다. 새 모델 실행이나 의미 채점 결과가 아니다.

모델이 리뷰를 `complaint`로 선언했지만 어떤 Need도 해당 리뷰를 인용하지 않으면, 현재 Agent는 이미 그 선언을 거절한다. 이전 피드백에는 그 리뷰 ID가 없었다. `stage_alignment_feedback`이 `unextracted_complaint_ids`를 계산해 다음 같은 Need 단계의 수정 요청에 전달한다. 원문 분류·니즈 작성·배열 수정은 모델이 수행하며 코드가 대신하지 않는다.

구체적인 질문과 보류 사유가 함께 있으면 니즈를 억지로 만들게 하지 않는다. 한 Need가 여러 불편 리뷰를 인용하는 경우도 허용한다. `positive`·`irrelevant`·`uncertain`·`conflicting` 선언을 `complaint`로 바꾸지 않는다. 판정 코드 이름·canonical 계약·공유 내부 수정 최대2회·PM 공통 어댑터는 그대로다.

[검사 manifest](checks/manifest.json)와 로그:

- [수정 전](checks/baseline.txt): 새6검사 중1실패·1오류. 거절/재시도 동작은 기존에도 있었으며, 누락된 ID 피드백을 재현했다.
- [관련 회귀](checks/targeted.txt): 297검사, 실패0·오류0.
- [전체 Python](checks/full.txt): 1,438검사, 실패0·오류0·건너뜀3.
- [정적·규칙·계약·하네스·원 기록·stdio MCP](checks/static.txt): 통과. MCP5호출은 fixture이며 실모델 의미 검증이 아니다.

모든 코드 실행은 고정 이미지의 인증정보 없는 Docker에서 source 읽기 전용·network none·UID65534·cap drop·no-new-privileges로 수행했다. 신규 실제 모델 호출0. R4 실제3건의 allfailed·9호출·39,726토큰과 독립 평가 원 결과를 다시 실행하거나 성공으로 바꾸지 않았다.

실모델의 올바른 니즈 추출·정상/조건변경 accept·적절한 자료부족 hold, 같은 run의 WEB/MCP 확인, 독립 품질·부모 과제의 최종 PM 인수는 남아 있다. PM 공통 필드 안내·고정 유한 검증 인계와 대조해서 이어간다.
