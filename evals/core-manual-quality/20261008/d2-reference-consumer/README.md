# D1·D2 실제 자료 소비와 공식 참고자료 출력

`CORE-X1-D2-CONSUMER-01a10729-01`, 2026-10-08 KST, 황대겸/unknownamed.

[DATA PR254](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/254)의 고정 head `94b560de72f91795cfd50aada9e17d6773383ae1`을 소비했다. P0 계약은 `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`, 본인 수정 전 head는 `d1ce2f9dfb60e8179daadf1c566f097228aba594`다. 새 자료의 공식 FAQ·설치 안내와 모델 미확인 관리 절은 기존 모델별 설명서 출력에 들어가지 않았다. 별도 `official_reference` 출력으로 원문과 적용 범위를 함께 제공한다.

## 확인한 입력과 출력

| 제품군 | canonical sources | 실제 개발 후기 | 공식 참고자료 | 기존 모델별 manual 출력 |
| --- | ---: | ---: | ---: | ---: |
| 냉장고 | 58 | 48 | 10 | 8 |
| 식기세척기 | 73 | 48 | 24 | 7 |
| 전자레인지 | 53 | 45 | 8 | 6 |
| 합계 | 184 | 141 | 42 | 21 |

[consumer-audit.json](consumer-audit.json)에 고정 입력 SHA, 선택한 42개 source ID, 새 관리 절14개의 canonical ID→원 audit ID→문서 ID·판본·쪽·native 범위/SHA 대응을 남겼다. 3개 ResearchBundle을 현재 계약으로 검증했고, 후기141개 source 객체는 기존 고정 R8 입력과 전체 필드가 같다. membership238의 개발141/평가36/시연49/격리12 구분, 구매 SKU·후기 게시일 null과 입력 보류를 유지했다. 독립 평가/시연/격리 자료를 기획 입력에 추가하지 않았다. `.producer.json` checkpoint는 runtime 입력으로 쓰지 않는다.

[공식 참고자료 ZIP](official-references.zip)은 실제 자료의 JSON·HTML·Markdown 3종씩이다. JSON도 [냉장고](references/fridge.json), [식기세척기](references/dishwasher.json), [전자레인지](references/microwave.json)에 별도로 고정했다. 새 source나 실제 기획안을 생성하지 않는다. 원 source 객체·본문·facts·metadata·locator를 깊은 복사로 보존한다.

`scripts/export_research_guide.py --bundle <canonical ResearchBundle.json> --source-id <공식 source ID> --source-id <다른 공식 source ID> --output-prefix <새 경로>`로 명시적으로 선택한다. `--page-model`의 기존 설명서 선택과 `--concept-id`의 기존 실제 기획안 출력은 유지한다. 빈/중복/누락 ID, 고객 질문·후기, 공식 도메인 위장, 입력 덮어쓰기와 기존 출력 덮어쓰기는 거절한다. 고객 질문 `D2-DW-QA-470877-Q`는 제외하며 공식 답변 `...-A`만 선택한다.

## 원문·적용 경계

새 관리14개는 DATA가 생산 ResearchSource로 등록했지만 `page_model=null`이다. 기존 `build_official_guide(bundle, "DUE6BGL2E")`에 자동 편입하거나 구매 모델을 채우지 않는다. 공용 DUE6 판본 `MFL71959117 Rev.07_030626`, PDF SHA `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5`와 PR252의 원 native 발췌가 일치한다. 감사 레이어의 원 `audit_only_not_registered_ResearchBundle_source` 역할과 새 canonical `official_document` 역할은 각각 보존한다.

HTML·Markdown에 공식 문서/답변 역할, 모델 미확인, 적용 범위·선택 기능·연속 페이지·원문 숫자 추출 주의와 조건을 표시한다. 배열/바구니 높이/간섭 원문을 청소법으로 전이하지 않는다. p43 native `50 7`을 고치거나 자동으로 50℃ 사실을 생성하지 않는다. DATA의 원 시각 검수 문구는 그 출처의 metadata이며 본인의 새 PDF 원문 검수로 기록하지 않는다. 고객 원인·호전·정확 구매 SKU/구매 당시 판본은 미확인이다.

설치 Q&A의 600mm 표준, 문 앞 공간590mm, 기사 확인·배관 압축 가능성의 조건부567~600mm는 서로 다른 조건으로 보존한다. 선택 인용 바깥 원문 대조가 포함됐다는 안내도 출력해 한 연속 인용처럼 표시하지 않는다. 567mm를 무조건 설치 승인으로 바꾸지 않는다.

## 실제 검증

- [verification.json](verification.json), [7개 관련 검사](tests.log), [Ruff](ruff.log), [실제 자료 소비·CLI 대조](consumer.log): source-only Docker/UID65534/network none/read-only/인증 mount0에서 통과했다. 새3검사는 적용 범위·질문/답변·도메인/메타데이터 escaping 거절 경계다. 기존 실제 후기837305·공식 M11 자료를 재사용하며 새 고객 후기나 모델 응답을 만들지 않는다.
- 새 공식참고자료의 직접 함수와 CLI JSON/HTML/Markdown 출력이 바이트까지 같다. 같은 새 canonical 입력에서 기존 모델별 안내3종의 JSON·HTML·Markdown은 수정 전 코드와 같다. 모델 미확인 care14의 자동 편입은 없다.
- [화면·인쇄 수신](visual/render-receipt.json), [PDF 텍스트 대조](visual/pdf-text-audit.json): 화면3종, 인쇄33쪽(6/21/6), 원 source42건의 ID·본문을 확인했다. 모든 쪽의 contact PNG와 화면을 직접 봤고 겹침/잘림은 관찰되지 않았다. QA 조건 블록·native `50 7` 주의도 확인했다. JS off/외부요청0. PDF는 private QA 중간 파일이며 ZIP의 HTML로 인쇄할 수 있다.
- 첫 감사에서 `read_text`가 원 CRLF를 정규화해 renderer 대조가 실패했다. 원 출력·입력·실패를 보존하고 더 엄격한 `read_bytes == expected UTF8 bytes`로 대조했다. 제품 코드의 강제 수락·원문 변경·검사 완화는 없다.
- [재현기](verify_d2_consumer.py)는 source-only snapshot 루트에 복사해서 실행했다. snapshot에는 위 DATA head의 canonical3/input-index/manifest/current-delivery, 위 CORE 수정 전 head의 계약·기존 R8 baseline3·`baseline/before_guides.py`, DATA PR252 고정 native 발췌 `baseline/audit252.json`, 본인 후보 코드·CLI를 둔다. 출처별 Git 파일을 정확한 바이트로 복사하고 `/src` read-only, 새 `/out`만 writable로 마운트한다. 인증·전체 checkout·사용자 파일을 마운트하지 않는다. [artifact manifest](artifact-manifest.json)는 공개 산출물 SHA·크기를 연결한다.

## 남은 필수와 다음 인수

DATA의 새 생산 자료 전달은 받았다. 실제 PM runtime 등록/공용 자료의 적용 결정, 기존 LG27B raw 응답·usage·pin·동일 HTTP/MCP 저장 run, native 후보 metadata 전달과 C2 복구 경계, C3 실제 단계·원인/대안 비교·구체 기획, C4 혼합 요약/분모, X1 정확 구매 모델 적용·실제 콘셉트 설명서 및 기존 input-only/noGold/graph 잔여는 미완료다. WEB PR253의 같은 버전 표기와 PR255의 스토리보드 준비는 별도 담당 결과로 읽었으며 실제 C3 brief 인수를 대신하지 않는다. 새 모델·OCR·DB/runtime 실행·여섯 사례 AI 재채점·PM 승인/병합/Done0. 사용자 추가 판단 질문은 없다.
