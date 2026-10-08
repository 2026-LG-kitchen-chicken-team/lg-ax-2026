# X1 공식 발췌 안내 — 인쇄 배치 보완

2026-10-07 황대겸 / unknownamed. [#238](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/238)의 실제 제품 안내 범위에서, PM PR245 고정 `e04f42b5de37b2d1cad606f2f06a3f7fe6a91f30`의 renderer를 보완했다.

## 바뀐 동작

기존 인쇄는 첫 페이지에 제목·근거 heading만 남고 큰 카드가 다음 페이지로 밀렸다. print CSS의 크기/간격과 heading의 다음 본문 연결을 조정하고, 인쇄에서는 중복 fact JSON 직렬화만 숨긴다. 공식 원문·사실 문장·문서판·출처ID/URL·locator는 계속 인쇄된다. 화면의 전체 JSON과 내보내기 JSON/Markdown은 그대로다. source 선택·정확 모델/공식 도메인 guard와 기획 코드는 변경하지 않는다.

## 실제 고정 입력과 검수

[고정 입력·renderer SHA/해시](official-guide-audit.json) · [생성 코드](export_official_intake.py) · [인쇄 원문 대조](visual/pdf-text-audit.json) · [브라우저 수신](visual/render-receipt.json)

- 세 모델의 정확 원문 HTML/Markdown/JSON은 [내보내기 ZIP](official-excerpts.zip)에 보존했다. 공식 원문에 있던 줄 끝 공백도 바꾸지 않는다. 저장소의 일반 코드/문서 공백 검사를 완화하지 않는다.
- MW23FDI 공식 발췌3개: [JSON](official-excerpts/MW23FDI.json), [인쇄 판독](visual/MW23FDI.contact.png).
- DUE6BGL2E 공식 발췌6개: [JSON](official-excerpts/DUE6BGL2E.json), [인쇄 판독](visual/DUE6BGL2E.contact.png).
- T876MEE1H1 공식 발췌6개: [JSON](official-excerpts/T876MEE1H1.json), [인쇄 판독](visual/T876MEE1H1.contact.png).

무인증·network=none·readonly 소스 Docker에서 생성하고 고정 기존 결과와 guide JSON/Markdown·HTML본문·화면 CSS의 정확 동일을 확인했다. 스크립트0/JavaScript OFF/외부요청0의 실제 Chromium 화면·A4 인쇄를 확인했다. 3/4/4쪽 전체 PNG 판독에서 첫 heading의 본문 동반·글자/수치·출처 가독성·잘림/겹침 부재를 확인했다. PDF 텍스트에서도 원문15개와 ID15개를 대조했다. HTML은 기존 화면과 동일한 본문이다.

## 남은 범위

공식 발췌는 전체 정식 설명서가 아니다. 고정 FAQ의 page_model=null은 그대로 두며 계열 안내를 정확 SKU 적용으로 바꾸지 않는다. 쉬운 안내/정확모델 FAQ의 추가 자료 인수와 실제 저장된 신규 콘셉트 설명서·의미 품질·PM 통합은 미완료다. 모델/신규 리뷰/기획 placeholder/독립 AI 재평가0. C2의 수정·부분 보존 검수는 별도 PR242/PM245 인계이며 이 CSS 수정으로 통과 처리하지 않는다.
