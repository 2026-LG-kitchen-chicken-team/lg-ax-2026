# #16·#148 고정 R5 후기팩의 집계·원문 연결 대조

확인 시각: 2026-10-07T11:43:43.862923+09:00. [PM 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6029600260)의 PR218 고정 head `0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d`를 읽었다. 최신 main 조회 `8ec1e8a51faabd6db032e52245680bef4229f93f`에서 PR218 병합도 직접 확인했다. 운영 서버에 배포됐다는 확인과는 별개다.

고정 v1 179행 + 비교 표본 60행 = 관찰 239행이다. 겹치는 원 후기 ID 1개를 제외하면 고유 후기 238개다. 두 버전의 같은 ID를 [차이 기록](fixed-pack-audit.json)에 남기고, PM 결합 규칙대로 v1과 신규 59개를 계산했다.

| 분할 | 고유 후기 수 |
|---|---:|
| 개발 | 141 |
| 평가 후보 | 36 |
| 시연 | 49 |
| 격리 | 12 |
| 합계 | 238 |

개발·평가·시연 사이 원 ID와 NFKC/공백 정규화 본문의 교집합은 0이다. 격리 12개를 제외한 연구용 ID 분모는 226이다. 구매 SKU 미확인/게시일 미확인/모델 입력 부적격은 각각 238개이며 서로 겹치는 제외 사유이므로 합산하지 않는다. 게시일을 구매일로 대신하지 않아 월별 비격리 분모는 0, 월별 동향과 승인되지 않은 토픽 분자/비율은 null이다. 표본 비율을 전체 시장 비율로 표시하지 않았다.

[238개 URL·원문 위치·원 ID·본문 SHA·버전·수집 시각 연결](review-source-joins.json), [집계](fixed-pack-audit.json), [고정 파일 SHA](fixed-pack-source-pins.json), [분할/노출](split-and-exposure-check.json)을 재현할 수 있다. 고정 PR217의 알려진 개발 노출 원문/발췌군과 27개 참조를 대조해 총 1개 노출 연결을 확인했지만 평가 후보에는 0개다. 이는 확인한 범위이며 전체 과거 튜닝/독립성 승인으로 확장하지 않는다.

첫 검사 exit1은 files.json에 선언된 `public-reviews.sqlite3`를 받지 못해 발생했다. 당시 코드·명령·로그·SHA를 [보존](preserved-validation-history/first-audit.execution.json)했다. 받은 JSON 검수와 미수신 DB를 구분한 수정 검사 및 같은 ID의 버전 차이를 기록한 최종 검사는 exit0이다. SQLite의 선언 SHA는 미확인으로 남겼다. private DOM·운영 DB·Excel의 재검수를 수행했다고 표시하지 않는다.

`audit_fixed_r5.py`는 독립 stdlib 검사기이며 network none/UID1000/readonly/zero-auth 기존 Docker에서 실행했다. 수집기·DB·Excel·판단/계약·운영 API·모델을 변경하거나 실행하지 않았다. 기존 운영 36개 합성/10집계 검증은 새 실제 R5 검수의 증거로 승계하지 않는다. 앞선 [팩 미수신 준비 기록](r5-intake-and-review-plan.json)은 당시 상태로 보존했다.
