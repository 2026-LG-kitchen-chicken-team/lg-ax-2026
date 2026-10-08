# W3 고정 인계 근거와 적용 범위

기록 ID DATA-W3-01a108a8-0443-f472c9. 고정 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`와 새 W3 브랜치에 연결한다. [source-pins.json](source-pins.json)의13자료는 API가 반환한 고정 Git blob을 디코딩하여 bytes·SHA256·Git blob ID를 실제 비교했다. 다른 창의 working 파일이나 보고만으로 bytes 일치를 추정하지 않았다. 원 인증·메일/원자료는 새 private run에만 있다.

| 근거 | 받은 내용 | 아직 입증하지 않은 내용 |
|---|---|---|
| [PR267 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/267#issuecomment-6049909890) 및 고정 required-exports/7run 장부 | 기존 운영7항목·run 선언SHA·과거 수신 상태 | actual HTTP/MCP wire·원 public JSON·native usage·동일DB 전후 |
| [PR283](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/283) | 이전 archive/operation/followup/mail coverage 표 | 실제 ZIP 전달·수신·PM 승인·운영 원파일 |
| [PM284 serving-proof](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/02ba9913efc0c449aa4f3cb46727162f2057cd71/evals/pm-r9/20261008/shared-prototype/serving-proof.json) | 보고 자체4,387bytes/SHA·새run/선택6·배포source/model digest/원null | report SHA가 run output SHA라는 주장, 기존2run/DB와 동일성, 독립 의미 품질 |
| [CORE281 회신](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/281#issuecomment-6052144975) | W1의10파일 수신·범위와 부적절한 방법쌍 대입 제외 | canonical7 원출력/무Gold4·PM 승인을 신규 확인한 것 |
| [CORE282 회신](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/282#issuecomment-6052228755) | W2의21파일 수신·Q&A 전체 원문 위치/SHA·조건 보고 | W3 원 HTML 수신/정확구매SKU·당시판본/실제설치 가능·운영 소비 승인 |
| 자기 Gmail 기존 스레드 | SENT6개 읽기·새 누락 보완1메일 SENT exact/첨부0 | PM 열람·전송 승인·CORE ZIP 수신 |
| [CORE 수신0 관찰](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6051070034) | 2026-10-08T02:41:03Z의 폴더 관찰·받은 범위 | 그 시각 이후 CORE PC 전체/PM 전역에 파일이 없다는 주장 |

## 보고 일부를 W1에 인계할 때

[new-partial-fields.json](new-partial-fields.json)의 JSON pointer/value는 PM284 보고 파일의 정확 위치다. 새 run은 `run-f0ebcae46f5e4bbd8f087161fd801ce5`, 보고된 배포 source는 `0541ba02457055d28e3f7021fbaf907a2ca86bfb`다. 보고 head와 실행 source를 합치지 않는다. 보고된 model_name `qwen3.8:27b-q4_K_M`과 runtime.model null을 둘 다 보존한다. 모델 digest는 같은 보고의 서비스 manifest digest와 연결되지만 runtime.model null을 임의 채우지 않는다.

보고파일 SHA는 actual report SHA이고 actual output JSON SHA·wire SHA·운영 payload 동등·DB snapshot SHA/정체성은 null이다. 같은DB 기존 전후 캡처도 미수신이다. 다른 직렬화의 wire bytes와 해석 payload 동등을 섞지 않는다. report의 입력6개와 새 run ID를 과거 정상1f83·조건754268·canonical7/무Gold4에 대입하지 않는다. W1의 의미 검수/독립 점수 승인을 W3가 수행하지 않는다.

[선택 원자료6 연결](selected-source-bindings.json)의 bundle pin은 고정 main의 `data/research/r9-public-runtime-20261008/dishwasher.research-bundle.json`이다.6개 Source ID의 유일성·각 text SHA·문서 버전/locator를 확인했다.후기 페이지 모델은 DUE4BGL1E·DFE5BGE·DUE6BGL2E이고 설명서2개 page_model은 null·공용 DUE6 적용 조건이다. 후기 purchased_model/published_at은 null, 구매일과 게시일·현재 설명서 판본과 구매 당시 판본을 구분한다. 원문 문서버전 값을 보존했으며 이 candidate bundle이 실제 run에서 그대로 로드됐다는 원 snapshot/버전 보존 증거는 아직 없다. 실제 여러 모델의 혼입 오류 여부와 내용 적용은 W1의 받은 응답 필드 검수로 이어간다.

## W2의 부족 답변에 생긴 회신

[core-followup.json](core-followup.json)은 CORE282 댓글의 UTF-8 본문 SHA와 작성자/시각에 연결된다. CORE가 보고한 Q&A470877 원 HTML SHA는 `1941dbeb99f2cab9a595240f3fcbe0576a71437e4699204119296877b0c7f487`이고 위치는 `li[data-que-no="470877"] div.answer-content`다. 이 값은 producer-reported HTML SHA다. W3 actual HTML SHA는 null이다. 받은 부분은 W2가 읽을 수 있는 공개 회신이므로 같은 전체 답변 요청을 메일로 다시 보내지 않았다. 질문의119~120mm는 해석null을 유지한다. 내용·조건·구매/사용 여부 보완과 전면 적용 판단은 W2가 맡는다.

## 승인과 다음 단계

Gold의 [FR01만 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029600741)은 보존했다. 전체 Gold/독립성·최종 독립 채점자와 기존 결과 전달 승인으로 확대하지 않는다. 새 채점은0이고 지정자가 수행한 기존 결과의 인수 위치만 PM에게 확인했다.

ZIP 전송 범위가 확인되면 원 ZIP부터 전달한다. Gold·전체 raw/usage·자동 표·최종 채점은 그 전달의 추가 선행조건이 아니다. CI/메타데이터 PASS·SENT·공개 자료 수신과 ZIP 원파일 수신·운영 보존·PM 인수/부모Done을 각각 유지한다.
