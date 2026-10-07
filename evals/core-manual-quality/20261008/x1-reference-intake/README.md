# X1 후기 참고자료 버전 표시와 DATA 관리 절 인수

기록 ID `CORE-X1-REFERENCE-01a10729-01`, 2026-10-08 KST, 황대겸/unknownamed.

[DATA PR252](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/252)의 고정 head `78a1906369479eb2336cecc3a134895a814f95b1`을 읽고 본인 X1 설명서의 출처 표시를 대조했다. 후기의 `document_version`은 페이지 모델에 연결된 참고자료 버전이다. 후기 본문 판본이나 구매 당시 설명서 확인값으로 표시하지 않는다. 공통 basis 계약 결정은 PM 범위로 남긴다.

`guides.py`의 HTML·Markdown에서 후기 카드만 **페이지 모델의 연결 참고자료 버전**으로 표시하고 참고값의 의미를 함께 설명한다. 원 버전 값·출처 ID·본문·facts·locator·구매 모델/게시일 미확인 값·JSON은 보존한다. 값의 prefix로 설명서/제품 페이지 종류를 추정하지 않는다. 공식 설명서의 기존 표기는 유지한다.

## 실제 확인

- [검증 결과](verification.json): 기존 설명서 검사4·Ruff PASS. 고정 실제 자료의 후기141건(전자레인지45/식기세척기48/냉장고48)의 HTML·Markdown 표기와 원 source 필드 보존을 대조했다. 기존 `TEST_ONLY` 계약 표시 프레임을 재사용한 렌더 검수이며 실제 기획안·모델 품질 승인이 아니다.
- DATA가 고정한 기본/공식확장 묶음6개·생산 코드/공통 스키마2개의 원 SHA8개가 본인 소비 파일과 같다. 새 자료나 계약을 생성하지 않았다.
- 이전 PR248 head `1d6bddce784a9d9a1b8c9a10e581cea0ca08cb1f` 대비 공식 안내3종의 JSON·HTML·Markdown 출력이 모두 바이트까지 같다. 기존15발췌·A4 11쪽/화면3종 검수는 그대로 재사용하며 다시 렌더하지 않았다.
- source-only 고정 Docker, UID65534/network none/read-only/무인증에서 실행했다. 모델·OCR·새 고객 후기·실제 기획 생성·여섯 사례 재채점0.

## 관리 절의 소비 경계

[인수 경계·원문 pin](intake-boundaries.json)에 DATA 새 검수 발췌14개의 문서 ID·판본·쪽·PDF/native excerpt SHA를 고정했다. 기존 PDF SHA 및 받아 읽은 audit 파일5개의 manifest 일치도 확인했다. 원 PDF의 전체 시각 검수는 DATA의 기록을 소비하며 본인이 다시 수행한 것으로 기록하지 않는다.

현재 등록된 식기세척기 설명서20·23·24쪽은 배열/바구니 높이/간섭 근거다. 관리39~43쪽·냄새49쪽·성능50쪽 등의 새 발췌는 **검수용이며 생산 ResearchBundle 등록 전**이다. DATA D2 새 자료 버전과 PM의 공용 DUE6 판본 적용 범위 인수 후 소비한다. 정확 구매 SKU·구매 당시 판본·고객 냄새 원인·호전은 미확인이다. 43쪽 native `50 7`은 원문 문자열로 보존하고 검증된 숫자/단위 지침으로 쓰지 않는다.

공개 `MW23FDI-MANUAL-M11`은 전자레인지 p25 근거다. PM 실제27B runtime shorthand `M11`의 매핑은 미수신이며 둘을 자동 연결하거나 실제 잘못된 연결이 관찰됐다고 판정하지 않는다.

## 남은 필수

PM native 후보/data/usage 전달 경계와 기존 실제27B/동일 HTTP·MCP 저장 run, C3/C4 원문 의미·단계·혼합/분모, X1 정확 모델 FAQ·실제 기획 설명서 및 기존 noGold/input-only/graph 잔여는 계속 필요하다. 표시 검수/자료 검수 수신을 PM 승인·병합·전체 Done으로 확대하지 않는다. 새 사용자 판단 질문은 없다.
