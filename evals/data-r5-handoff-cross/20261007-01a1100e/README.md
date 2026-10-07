# R5 고정팩·승인 11문항 교차 검수 — 20261007-01a1100e

사용자 요청한 실제 후기 검수·자동표 인계·승인 검색 재채점의 후속이다. 진행 중인 두 창의 수집/본 검수·평가/집계 작업과 별도 고유 폴더에서 **고정 공개 산출물의 bytes·계보·재채점 산술**을 대조했다. 원문/원 Gold/원순위·모델/OCR·DB·수집 코드는 변경하지 않았다.

## 1. 실제 후기 팩 대조

| 항목 | 독립 확인 | 한계 |
| --- | --- | --- |
| 고정 원본 | PM218 head `0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d`의 공개파일19개 SHA 일치 | private SQLite/원 DOM은 미제공 |
| 후기 수 | v1 179＋v2 60−ID중복1＝고유238 | 수집 표본으로 시장 전체를 대표하지 않음 |
| 제품 | 18페이지·제품군별6모델 | 페이지 모델이 구매 SKU의 확인은 아님 |
| v2 원문 | 공개 DOM snapshot60행의 body·fragment SHA·ID·rating·구매일/페이지 MD 대조 | 원 private DOM/작성자 정보는 읽거나 복사하지 않음 |
| 판본 | v1 record의 manual/document 판본이 제공 products와 일치 | 현재 참고 판본이며 구매 당시 판본 확인 아님 |
| 분할 | development141 / evaluation36 / demonstration49 / quarantine12. ID·공개 NFKC본문 교집합0 | 과거 전체 노출·Gold·독립성 승인이 아님 |
| 과거 노출 | 기존 문서화3군:848850은development,776453·842682는demonstration. 이3군은evaluation에 없음 | 문서화한3군만 대조, 모든 과거 노출을 소거한 것이 아님 |
| 구매SKU/게시일/모델투입 | 제공 기록의 확인값0·0·적격0을 유지. 실행 dataset reviews0/evidence21/features9 | 숨은 구매SKU/게시일을 채우거나 확인된 제품 사실로 사용하지 않음 |

[238행 위치/ID/SHA 검수표](238-record-provenance-review.csv) · [파일 인계 대조](file-handoff-review.csv) · [과거 노출](past-exposure-cross-check.json) · [팩 결과](R5-handoff-cross-result.json).

위 대조는 제공된 공개 bytes/metadata와 공개 DOM의 일치다. 고정18 원 HTML 및 private 원 캡처 bytes가 없어 모든238건을 원 UI와 독립 재확인했다고 표시하지 않는다. 실제 구매SKU·게시일 확인과 독립평가 인수는 남아 있다.

## 2. 승인된 기존 225회 검색 재채점

[PM 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029600741)에 따라 **FR01만 F10-FOOD로 사후 정답 정정**했다. 다른10 Gold·원 F10·21원문·질의·모델·설정·225순위는 보존했다. 실패행은0이며 버리지 않는다. 5회 반복은 각 질의 안에서 처리하고 분모는11개 고유 질의다. 이번 추가 검색/모델 호출은0이다.

| 방법 | Hit@1 | Recall@3 | MRR@3 | FR01 순위 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 7/11 =63.6364% | 19/22 =86.3636% | 25/33 =0.757576 | 3 |
| BGE-M3 | 7/11 =63.6364% | 100% | 53/66 =0.803030 | 2 |
| BGE-M3＋재정렬 | 7/11 =63.6364% | 10/11 =90.9091% | 25/33 =0.757576 | 2 |

원225·고유225·실패0·45그룹×5·630반환 근거의 scope/text SHA를 대조했다. 채점 대상 반복165행과33방법/질의행을 별도 보존한다. 이 결과는 공개 개발 질문의 사후 Gold 정정이며 새 독립 성능·제품 품질·시장 효과가 아니다. 기존10문항 점수·null 파일을 덮어쓰지 않았다.

[승인/새11문항 요약](approved11-summary.json) · [질의별](approved11-per-query.csv) · [원165시도 채점](approved11-attempt-scores.csv).

## 3. 남은 검증과 팀 인계

- 자동표: 현재 main8ec/PM218에도 실제 cell/graph/header/unit/footnote 출력·승인 adapter 없음. accuracy/error count는null, 검증 불가. PM이 producer/adapter 범위를 고정하고 실제 출력/원 PDF SHA·개정·페이지·셀/단위/각주·Evidence ID 대응을 제공해야 한다. 새 비용/모델/OCR 호출 승인으로 해석하지 않는다.
- 무Gold4: FR04/FR05/DW05/MW05의 저장 순위는 있으나 실제 답변/보류/질문 의미 검수는 미실행. 기존 고정 결과가 있다면 PM/CORE가 원 입력·응답·trace·code/data/version/SHA를 인계해야 한다.
- R5: source/capture에서 구매SKU/게시일 확인 근거가 없으므로 held 유지. private 원문이 필요한 대조는 승인된 최소 인계·원/공개 SHA mapping을 요청한다. 원 개인정보를 PR에 옮기지 않는다.
- #15/#16: 후보/Gold·독립성·최종 검수자 및 실제 동향 인수는 담당 창과 PM의 별도 후속이다.
- #13/6번: PR219 준비와 실제 DB/API·재시작 캡처 대조는 별도 범위로 유지한다.

[자동표 상태](automatic-table-status.json) · [무Gold4](no-gold-semantic-pending.csv).

## 4. PR217 수정

별도 좁은 branch에서 승인근거4필드를 `user_request_basis`로 바꿔 PR217에 정상 fast-forward로 올렸다. 생성기도 해당3출력에만 정리하고 기존 패키저로 원3차단/새3통과를 확인했다. 원 JSON 값·9원문/SKU/날짜 판단·private/PDF/개인README·패키저 규칙은 보존했다.

[수정 head9448 근거](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/9448c7995c0b5c57db54dd11a90796954fca88e6/data/research/r5-public-independent-20261007/20261007T104222-01a10f51/pm217-field-fix-20261007-01a1100e.json) · [재검수 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/217#issuecomment-6029851265). 해당 필드 스캔 통과와 완성 ZIP/PM 인수는 구분한다.

## 보존·재현

source main `8ec1e8a51faabd6db032e52245680bef4229f93f`, frozen retrieval PR200 head `a26b6458118157fa0513218414f24abd6eae4b2a`. [source pins](source-pins.json)·[현재 확인](verification.json)·[작업 기록](work-record.md)·[보존](preservation.json)·[manifest](artifact-manifest.json).

새 own helper `python cross-audit.py`만 실행했다. 첫 checker는 제품군을mw/dw로 가정해 실패했으나 공급 label은microwave/dishwasher였다. 입력을 보존하고 checker를3군각6 기준으로 정정해 최종2,801확인 PASS. [원 실패](failed-checks.json)와 [진단](execution-diagnostic-01.json)은 보존하며 이를 제품 회귀로 표시하지 않는다. 저장된 metadata/산술 확인 수는 성능 표본 수가 아니다.
