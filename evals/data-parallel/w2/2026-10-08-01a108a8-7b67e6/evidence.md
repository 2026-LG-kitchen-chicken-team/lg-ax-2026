# DATA-W2-01a108a8-7b67e6 검수 근거

기준 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`. PR270 `33b6312721c79f234f035fbe408f7d570fa6c36d`와 PR272 `0a811ffa6d07f7cf8f5590ef86e3174dd7936108`은 읽기만 했으며 병합/인수 완료로 처리하지 않았다. 입력별 SHA·바이트·경로는 [input-pins.json](input-pins.json)에 있다. 이 문서와 상세 자료는 게시되는 동일 PR head에 귀속된다.

## 표: 수동 근거와 자동 출력의 구분

- DUE6BGL2E 설명서 `MFL71959117 Rev.07_030626`, p57, PDF SHA `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5`. DFE 열의 598×845×600mm, DFE 상판 제거 조건의 598×815×567mm, DUE 빌트인 열의 598×815×567mm를 구분했다. DUE 정확 구매 SKU에 DFE 상판 제거 조건을 옮기지 않는다.
- MW23FDI 설명서 `MFL68822538 Rev.00_120925`, p37, PDF SHA `3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc`. 소비전력1570W와 고주파 출력 Max.1000W*1을 구분했다. *1의 짧은 시간/조리 경과에 따른 출력 변화는 M06에 연결되며 소비전력만 포함하는 M07로 출력·각주를 입증하지 않는다.
- 기존 수동 sidecar `table-grounding.20261008.01a114f6.v1`, source commit `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`. 기존 canonical dataset SHA `d4649f1cd48db49277b0556c3fd8243b64dc748cca6631bf1e9441279aab81be` 및 D03/M06/M07의 연속 인용 구간·모델·판본·locator·빈 feature_ids를 대조했다.
- 기존 OCR 요약과 144수동 검수 count를 재사용했다. 이번 OCR 실행0. 표 검수54행은 6항목을 9개 관점으로 펼친 점검표이며 54개 독립 셀 정확도 표본이 아니다. 숫자 셀이 아닌 각주의 셀·행·열·숫자·단위5축은 미확인으로 둔다. 셀 bbox는 받지 못했다.
- producer graph commit/version/config/receipt 및 승인 adapter commit/version/config/매핑은 모두 null. 자동 출력과의 일치·오류는 판정할 수 없어54행 모두 **검증 불가**다. R9 기획 근거 graph를 입력으로 대체하지 않았다.

## 후기: 원ID·격리·분모와 분자

초안 `r8-development-topic-draft.20261008.01a114f6.v1`, taxonomy `r8-topics-draft.20261008.01a114f6.v1`을 그대로 사용했다. `annotation.draft.json` SHA `871c4618737f380e24725854aa8f37c665c3a8de8eca9775c3e65ca679211409`, development source SHA `e47f77303b83597a9c146e96f10cd1ff505d480e9f53abb80448178e481a1162`다.

238개 원ID의 partition은 development141, demonstration49, independent_evaluation36, quarantine12이며 서로 겹치지 않는다. 비개발97개 제외 후 선택된141개에서 게시일 미상141개를 제외하므로 날짜 유효 분모0이다. 두 제외 단계를 같은 분모에서 중복 차감하지 않는다. 제품군 membership은 냉장고48/식기세척기48/전자레인지45다. 주제별 양·음 극성에 같은 후기ID가 있어도 주제 분자는 union으로1회만 센다. 원문/인용292개는 Unicode codepoint의 end-exclusive 구간과 SHA로 연결했다.

36개의 기존 저장 집계 결과를 읽어 월/계절 bucket 분모0·주제 분자0·membership빈값·ratio null을 확인했다. collector를 다시 실행하지 않았다. 초안의 positive106/negative13/mixed16/uncertain3/neutral3 및 24주제 count는 미승인 development 분포이며 고객 수요율/계절 추이로 발표하지 않는다. PM 승인·지적 Source ID가 없어 분류 수정0, 의미 정확도 null이다.

## 15모델 후보 및 새 후기 후보

이미 확보한15모델·19문서 참조·15고유 PDF SHA를 원 저장 파일에서 다시 확인했다. 새 PDF 수집/추출/OCR0. PR270의 문서 범위 확정5/공통·패턴 조건부10, 선택 기능 미확인15, 설치 분기5는 정확 구매 SKU/구매 시점 판본의 근거와 구분했다. 구매 SKU와 구매 당시 판본은 모두 미확인이다. 제조사 사용 FAQ3은 고객 개별 Q&A/불편 사례/후기 분모0으로 유지했다. 공용 광파오븐과 정확 모델 MW25B/MW23FDI 청소 안내의 범위 차이2개도 임의로 한쪽을 정답 처리하지 않았다.

| 별도 후보 ID | 페이지 표시 모델 | 후기 날짜 표시 | 기존 참조 판본과의 관계 |
|---|---|---|---|
| [W2-THEBESTLG-3001-9737](https://thebestlg.com/board/product/read.html?no=9737&board_no=3001) | DUE5BGL1E | 2026-09-17 | `MFL71959118 Rev.08_030626`의 날짜 표기 뒤이지만 구매 시점 판본 연결은 미확인 |
| [W2-THEBESTLG-3001-4943](https://thebestlg.com/board/product/read.html?no=4943&board_no=3001) | DFE5BGE | 2026-01-28 | 후기 표시일이 2026-03-06 판본 날짜 표기보다 빠르다. 그 판본을 당시 사용 판본으로 연결할 수 없다 |
| [W2-THEBESTLG-3001-4211](https://thebestlg.com/board/product/read.html?no=4211&board_no=3001) | D502MEE33 | 2025-12-12 | 기존2023/2021 판본 후보와 구매 시점 연결은 미확인 |
| [W2-THEBESTLG-3001-4465](https://thebestlg.com/board/product/read.html?no=4465&board_no=3001) | DUE5BGL1E | 2025-12-31 | 후기 표시일이 2026-03-06 판본 날짜 표기보다 빠르다. 그 판본을 당시 사용 판본으로 연결할 수 없다 |

판매처의 공개 후기 게시판 원ID와 날짜 필드, 상세 페이지 날짜·본문 일치를 확보한 **고객 경험 후보**다. 판매처가 고객 후기라고 표시한 사실과 실제 독립 구매자/정확 구매SKU 인증은 구분한다. 표시일이 최초 게시일인지 수정일인지, 시간대는 미확인으로 `published_at=null`을 유지했다. 기존238개 원문 및 새 후보끼리 NFKC/공백 정규화 전문 일치 비교에서 같은 전문은 없었지만, 더 넓은 재게시/구매자 독립성을 입증하지 않는다. 이전 제품 고장과 새 제품 만족을 다른 모델 결함으로 합치지 않는다.

원 응답6건의 URL·조회시각·HTTP상태·SHA를 남기고 새 후보4개는 기존238/141행·승인 집계와 격리했다. 원 HTML·작성자·사진·후기 전문은 private 원 응답에만 보존한다. Git에는 ID·해시·날짜·위치·짧은 발췌와 요약만 둔다. 이번 신규 날짜 승인0·정확 구매SKU0·구매 판본0·사용 Q&A0·승인 분모 증가0이다. 공개 초기 MW20GDN 페이지는 연결된 개별 고객 질문/답변/게시일을 제공하지 않아 검증 불가로 기록했다.

## 검수 방법과 한계

[inspection-builder.py.txt](inspection-builder.py.txt)는 저장 자료만 읽는 독립 검수 유틸리티의 소스 보존본이며 배포/제품 코드가 아니다. private 원 응답과 intake pin이 필요하므로 저장소에서 바로 실행되는 프로그램으로 취급하지 않는다. [inspection-result.json](inspection-result.json)의 정적 자료 연결 검사1,101개는 PASS다. 이번 제품 코드·모델/OCR·collector 실행0이며, DB/API·ZIP·모델 결과 검수·독립 평가·PM 승인·병합·부모 Done을 수행하지 않았다.

막힘과 PM 인계 요청은 [#14](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6050704556) 및 [#148](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/148#issuecomment-6050704880)에 `DATA-W2-01a108a8-7b67e6`으로 남겼다. 2026-10-08 11:30 KST 재조회 시 이후 댓글0이며 실제 graph/adapter/분류 승인 미수신을 유지했다. 메일은 사용자 지시대로3창 담당이다.
