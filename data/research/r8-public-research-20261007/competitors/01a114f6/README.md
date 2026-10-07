# D3 공식 경쟁제품 비교 — 원문 고정 연구 단위

담당 신진하 / ginaginaring, 세션 01a114f6, Issue235, 기준 main 58feb9c.
이 폴더는 P0 공통 계약에 넣기 전의 연구 sidecar이며 실제 Agent 입력 승인이나 첫 문제 확정이 아니다.

## 비교할 문제와 근거

기존 development 후기848850에는 주방 돌출과 깊은 안쪽 공간에 손이 닿기 어렵다는 관찰이 있다.
원 후기와 SHA·표시모델·미확인 구매SKU를 comparison.json에서 연결했다. 이 후기를 특정 LG 모델 결함의 증거로 단정하지 않는다.
PM이 정한 first_problem_id와 P0 계약이 아직 전달되지 않아 후보 문제 연결로 남긴다.

| 비교 항목 | LG T876MEE1H1 | Samsung RM70F63R231 | 비교 한계 |
|---|---|---|---|
| 명목 전체 용량 | 870L | 640L | 230L 차이. 같은 용량 조건의 대안이 아니다. |
| 제조사 외형 치수 W×H×D | 914×1787×918mm | 후면핸들 포함912×1853×697mm, 미포함912×1853×683mm | LG 쪽 핸들 포함 기준을 별도 확인하지 않았다. 내부 깊이·팔 도달거리가 아니다. |
| 설치 타입 | 프리스탠딩 | 키친핏 Max | 삼성 공개 페이지의 좌우4mm·싱크대700mm 기준을 해당 모델의 설치 설명과 함께 보존한다. 전체 설치가이드 검수는 미완료다. |
| 시기 | 공식 제품페이지 출시월2026-04 | 정확 SKU의 출시월 미확인 | 현재2026-10-07 스냅샷을 과거 구매 시점 기능으로 소급하지 않는다. |
| 선반 | 제품페이지 접이선반 표현 | 공식 스펙 접이선반1개 | 이미 문서화된 기능의 재제안은 별도 대조가 필요하다. 인출식 선반 미언급은 기능 부재가 아니다. |
| 사용자/물리 시험 | 미수행 | 미수행 | 제조사 설치 연출과 외형 사양은 불편 해결·세척시간·신규성의 실측 증거가 아니다. |

## 공식 출처·재현

- [LG 공식 제품](https://www.lge.co.kr/product/refrigerators/t876mee1h1?modelId=MD10758826&pdpType=PURCHASE)
- [Samsung 정확 모델 지원 사양](https://www.samsung.com/sec/support/model/RM70F63R231/)
- [Samsung 정확 모델 제품·설치 조건](https://www.samsung.com/sec/refrigerators/french-door-rm70f63r231-d2c/RM70F63R231/)

official-sources.json은 실제 HTTP200 원문3개의 SHA·바이트·수집시각·정확 모델과 짧은 발췌의 정규화 문자 범위/HTML 경로를 보존한다.
원 HTML은 비공개 scratch에만 있고 Git에 넣지 않았다. 발췌 위치는 원 HTML 바이트 오프셋이나 canonical Evidence로 위장하지 않는다.
각 페이지의 총 직접 발췌는25단어 이하로 제한했다.

build_official_pack.py는 고정 원HTML과 capture-metadata.json을 받는 무네트워크 빌더다.
verify_comparison.py는 동일 기준main의 development 원 후기·JSON 값·출처 링크·보수적 상태를 대조한다.
검사는 별도 source 복사본의 network=none/auth=none Docker에서 실행하며 입력/검사 코드를 게시 인증 호스트에서 실행하지 않는다.

## 다음 인수

공식 경쟁제품 원문 단위와 비교 조건은 검토할 수 있다. P0/C3의 첫 문제 ID·선택 범위와 승인된 ResearchBundle 계약을 받은 뒤 해당 문제로 결합한다.
D1 생산 파일·공통 Schema/API/MCP·WEB 파일을 수정하지 않았고 Issue235/부모 Done은 요청하지 않는다.
