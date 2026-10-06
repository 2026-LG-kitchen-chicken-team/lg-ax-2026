# CORE 메타데이터 상충 거절·보류 전달

PM #11 댓글6015780670 / PR190 독립 blocker의 후속 작은 CORE 단위다. 원 PM JSON은 형식만 정규화해 복사했고 decoded object 동일·원 SHA·고정 DATA 소스를 sources.json에 기록했다. 원 바이트는 private에 별도 보존한다. 반례 운송에서 no_candidate_reasons=["No verified pain"]를 명시해 무후보 설명 누락이 원 P1을 가리지 않게 했다.

- 수정 전 고정 CORE + DATA190: nested uncertain/top positive가 completed/accept로 재현됨. 6개 신규 회귀 중 실패4/오류1, 원 실패 보존.
- 수정 후 본인 CORE: 관련130/전체1475·실패0/오류0(skipped3). 실제 모델 호출0이다. 최초 전체 MCP 경로 오류와 임시 checker 구문 실패는 private에 남겼다.
- 수정 후 CORE + 고정 DATA190 임시 조합:130 중 실패1·오류0. 메타데이터 상충/보류 전달은 통과, DATA의 conflicting Need 무조건 거절이 남아 전체 통합 PASS가 아니다.
- 기존 외부 계약·공유 수정2회·원 모델 입력/응답/기존6평가·PM 어댑터/다른 담당 파일은 보존한다. 독립 평가·실모델 효과·PM 승인/병합/Done을 주장하지 않는다.

[검사와 경계](checks.json) · [원 반례](pm-original-blocker.json) · [소스 고정](sources.json) · [DATA/WEB/PM 인계](handoff.md)
