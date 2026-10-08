# R9 최신2 선언 해시·변경 주장 발췌 추가 인수

신진하 / ginaginaring · `DATA-R9-COMPACT-01a114f6` · 2026-10-08 KST.

첫 [PR269](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/269)의6원문/14인용·수신 경계는 보존한다. 추가 확인한 PM PR264의 새 report를 별도 완료 단위로 인수했다. 시작 main은 `eab85d48385f965eef48c07a6cdd8f6fd9851c62`다. 자료에 새로 선언된 값과 실제 원출력 수신을 구분한다.

## 새로 받은 범위

| PM의 최신2 report | 선언된 public output SHA256 |
| --- | --- |
| 정상 `run-1f83d846191941aea21153897b944ec1` | `4e84728d07aedff38cc30c26f839abce2ae54719e341954f27dff353c79ed3d2` |
| 조건 `run-754268c6b0cb41bba50c5b8d713332d9` | `0fd3a2047a7fd884af1c89e6d87ef46e83a446f5b277d18c838876bf63427c1d` |

원 report SHA `f7d69e6fbd9ac43cd08754c7c7dfd51032b02472df90be37db160f17cb2f55fa`, Git blob `33e9c6c04e3e91a2c8437cf0e272a8a676dda759`. PM의 정상/조건2run metadata·parent/조건·모델 trace 선언과10새 findings/23선택 발췌 문자열을 실제 파일로 받았다. 원 모델 JSON/원 native trace·usage·HTTP/MCP는 받지 않았다.

조건 run의 보고된 parent는 정상 run 및 `brief-fe7412d6635c4822988f8d42ae6acddc`다. 조건5개와 정상 기본조건1개가 달라 순수 통제 A/B가 아니다. `complete`, 2call/0repair, source-facts exact, 정상 echo/truncation 해소는 **PM 실행/검수 보고**로 인수하며 DATA의 전체 원응답 대조/의미 승인으로 변경하지 않는다.

## 원문 대조와 한계

[compact-intake.json](compact-intake.json)에10finding→원source ID→기존14anchor의 대응을 보존했다. 첫14anchor 검사는 재실행하지 않고 고정 PR269 파일SHA·현재6 source의 본문SHA/판본을 확인했다. 같은 p49의 조건/순서/성분 역할을 위한 신규3인용만 exact 문자범위/SHA로 고정했다. 자동 추출 숫자/기능 승인이나 실사용 안내 승인이 아니다.

- CG-N-01/C-01: 배우자의 다리 불편을 구매자의 질환·관절 부담 재발로 확정하지 않는다.
- CG-N-02/C-02: 청소 언급·어느 순간 냄새·총 약3달 사용을 냄새 치료 실패/분해/매뉴얼 사용 실패/지원전화 이력으로 강화하지 않는다.
- CG-C-03: 사용기간1개월은 원 청소 언급과 총사용 약3달을 구분해야 한다. 새 상담 payload를 실제 수신한 것은 아니다.
- CG-N-03/C-04: 구매 기대와 실제 긍정 성과, 칭찬+당황 문구, 설치기사 의도의 고객 인식을 구분한다. report에 직접 summary 전체가 없어 분류/누락 여부는 PM reported finding으로 유지한다.
- CG-N-04/C-05: 80~100ml 및3초는 원문에 존재한다. **80~100ml보다 많은 경우**, **전원 켜기→전원버튼3초→취소선택**을 빼거나 모두에게 의무화하지 않는다. 다른 청소 절의 참조를 미취득 상세 절차로 생성하지 않는다. 공용판/정확 구매SKU·구매시점판 미확인을 유지한다.
- CG-N-05: 실제 고객의 청소 행동과 공식 조건별 권고를 구분한다. 제조사 문구의 식품 성분/세제 역할도 모든 세제 특성이나 이 고객의 원인으로 확정하지 않는다.

발췌23문자열은 PM가 선택한 예시이며 일부는 줄임표가 있다. raw output에서 연속 인용인지 확인할 수 없어 해당 flag는 false다. 출력 전체의 모든 주장·summary 누락·actual parent/facts/coverage·지침 효과를 DATA가 새로 채점한 결과가 아니다. 직접 받은 bytes는 report이며 실행 출력의 두 SHA는 declared 값이다.

## CORE 후속과 DATA 범위

PM `core-next-actions.json`의 CORE-NEXT-01 고객 관찰/주체/시점, CORE-NEXT-02 공식 조치 조건/순서, CORE-NEXT-03 field→claim 의존 수리를 인수했다. DATA는 원ID·quote/span·판본·조건 경계를 제공한다. CORE 생산 code/새 Schema·수리 한도·승인 상태는 변경하지 않았다.

## 자기검수와 실제 다음 인수

[verify_compact_intake.py](verify_compact_intake.py), [verification.json](verification.json), [invocation](history/invocation.json), [exit0로그](history/check.log)를 보존한다. 이전과 같은 pinned image의 network none/read-only·UID65534/auth/Gold mount0에서4fixed input blob/SHA,6원문 버전, 새2run/10source links/23발췌/parent선언·조건차이·신규3원인용 PASS. 모델/OCR·기존14anchor/16finding·생산검사 재실행0이다.

이제 두 선언 SHA와 일치하는 실제 원 JSON·승인 읽기 범위·generation commit·source/input/model/usage·같은 HTTP-MCP/부모자료가 필요하다. 받을 때 변한 필드만 원문 대조한다. #14 graph/adapter 및 #15 승인 전송/Gold/독립 채점자는 PR269 인수 조건 그대로다. 자동 정확도/독립평가 점수/부모Done은 미확인이다.
