# 공식 비교·인덕션 사용 조건 검수

DATA-W2-01a1100e-r3-96b63eea · 신진하(DATA W2) · 2026-10-08 · 기준 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`

사용자의 #235 경쟁제품 조건 대조와 #240 다른 가전 자료 연결 요청을 수행한 부분 결과다.
원 자료팩·제품 코드·개인 README·다른 창 파일은 읽기만 했다.

## 실제 결과

| 범위 | 결과 | 근거 |
|---|---|---|
| 경쟁 냉장고 | 설치 여유의 방향·과거 비교 모델을 구분. 새 원 HTML은 HTTP500으로 미확인 | [공식 페이지](https://www.samsung.com/sec/refrigerators/french-door-rm70f63r231-d2c/RM70F63R231/) · [고정값](source-condition-pins.json) |
| 인덕션 BEI3HRBLE | 공식 문서 수신. 모델·조건 12구간의 위치·정규화 SHA 연결 | [공식 페이지](https://www.lge.co.kr/product/electric-ranges/bei3hrble?modelId=MD10666831&pdpType=PURCHASE) · [검수표](condition-review.json) |
| 계산 대조 | 표시 시간비와 광고 배수가 직접 일치하지 않음. 원측정 기준 미확인 | 검수표 I03 |
| 검수 집계 | 14항목: 확인9·상충1·미확인4 | 수동 공식문서 검수이며 AI 정확도·자동 표 정확도 아님 |

기존 D3 비교12근거와 [PR282](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/282)의 김치냉장고·광파오븐 설명서 검수는 재사용했다.
공식 문서 구간 수는 독립 후기 수가 아니다. 새 후기·게시일·승인 토픽 분모 추가0이다.

## 원문·해시의 범위

성공한 LG 수신 entity는 3,996,831bytes, SHA256
`c7514f921ea72ab55e4890bd262e897b93900aeac55049f92a82d889573fe30c`다.
HTML·전체 발췌는 비공개 원본으로 보존했고 공개 파일에는 위치·해시·자료형이 있는 값만 기록했다.
이는 wire hash·운영 DB 보존 증빙·매뉴얼 판본이 아니다.

Samsung의 HTTP500 응답239,696bytes/SHA는 실패 증빙이다.
웹 도구의 제품페이지 표기 관측과 원파일 고정 여부를 구분했다.
오류 응답 해시를 정상 제품 문서 해시로 쓰지 않았다.

새 Source ID는 이 검수의 지역 식별자이며 사이트 후기 ID·현재 CORE의 등록 Source ID가 아니다.
운영 등록·실제 run의 Source 소비·구매 SKU/BOM·정확 설명서 판본은 미확인이다.
4개 잘못된 연결 후보는 수동 진단이고, 현재 CORE의 실제 오출력이나 소프트웨어 자동 거절을 확인한 것은 아니다.

## 병렬 경계·기존 요청

ZIP·원실행 인수·메일은 W3, AI 답변 의미 검수는 W1이다.
[W3 실제 인수 보고6058317658](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6058317658)와
[ZIP 미전송·승인 경로 요청6058339000](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6058339000)를 인수했다.
그 보고에서 실제 ZIP 전송0·CORE 수신증 미확인이다. 이 창의 ZIP 전달·메일 발송0이다.
Gold·전체 packet·자동 표를 ZIP 전송의 추가 선행조건으로 붙이지 않았다.

#235 현행 냉장고 결과 요청 [6051788629](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/235#issuecomment-6051788629)은 재사용했다.
김치냉장고·광파오븐의 남은 고객 원ID·게시일·구매SKU·운영 소비는 기존 미확인을 유지했다.
검수표의 O01/O02와 [범위·실패 기록](scope-and-failures.json)에 이번 인수의 한계를 연결했다.

## 재현·검수 기록

공식 웹 읽기와 자기 수신 파일의 메타데이터·수동 대조만 수행했다.
`bs4` 미설치 오류를 보존하고 같은 LG 수신 파일을 표준 HTMLParser로 읽었다.
새 모델/OCR·운영 재호출·서버 재시작·과거225/11/HTTP109/재시작51쌍 재검사·수동 CI 재실행0이다.
[파일 수신·무결성 기록](verification.json) ·
[상세 작업기록](../../../../docs/작업기록/세션/신진하/DATA-W2-01a1100e-r3-96b63eea.md) ·
[상세 근거](../../../../docs/작업근거/세션/신진하/DATA-W2-01a1100e-r3-96b63eea-E.md)

자료 작성·부분 PR·인증된 보고와 PM 검수·병합·운영 소비·부모 Done을 구분한다.
