# DATA-W2-01a1100e-r2-76097b75 — 후기 날짜·토픽·제품 적용 범위 부분 검수

최신 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`와 PR293의 완료 수신증을 재사용했다. 새 공식 목록의 제품 카드/정확 SKU 연결을 독립 검수했다. 기존 자료·코드·개인 README·PR290/타창 파일은 변경하지 않았다.

| 범위 | 이번 실제 처리 | 상태/한계 |
|---|---|---|
| 후기 게시일 | 새 목록의 제품 후기 총계는 원 리뷰 ID·게시일·개발 membership이 없어 기간 분모/새 후기 합산에서 제외 | 게시일 근거 미수신; 기존 날짜 검수 재사용 |
| 승인 토픽 | 기존 unclassified metadata와 draft 승인 false 유지 | 새 승인 pin/대상 ID 미수신; 승인 분자/비율 null |
| 제품 적용 | 새 공식 HTML의 정확 카드/SKU/MD ID 4행 확인; 다른 모델/파생형 연결 후보 3건 거절 | 실제 파이프라인 오류/자동 성능으로 계산하지 않음; 출고 BOM/구매판본/운영 소비 미확인 |

[공식 목록](https://www.lge.co.kr/business/care-solutions/refrigerators)의 2026-10-08T09:57:27Z HTTP200 본문512379bytes/SHA `c6f24b3a5da78a80b867d35ebe7c25871b2300bdc2a63298aa796a5a69419e55`를 고정했다. 공개 파일은 필요한 모델 binding과 locator metadata만 담고 원 HTML은 private에 보존했다. 본문 SHA는 받아 저장한 HTTP entity의 해시이며 wire/DB/모델 입력 전달 증명이 아니다. 상세 값은 catalog-bindings.json, 판단은 applicability-review.json에 있다. T876 정확 alias를 새로 받아도 기존 SKU-F03/F04의 기본 구성품 판정은 승격하지 않았다.

초기 li-only source reader는 실제 div 카드와 달라 0개를 반환했다. 같은 고정 body의 class/role 경계를 확인해 정정했으며 제품 부재로 해석하지 않았다. MW 현재 페이지의 web Internal Error도 기능 미지원 근거로 사용하지 않았다.

새 제품 테스트/모델/OCR·225회/11문항·109HTTP/51재시작/기존70·날짜6 검사는 수행하지 않았다. AI 의미 검수는 W1, 원파일/DB·ZIP·메일 인수는 W3 범위로 유지했다. 기존 #14/6050704556·#148/6052081322 요청을 재사용하고 미래 실행 목록은 private에만 보관했다. 새 원문과 검수표의 metadata만 확인했으며 PM 품질 승인·실제 소비·전체 Done은 미완료다.
