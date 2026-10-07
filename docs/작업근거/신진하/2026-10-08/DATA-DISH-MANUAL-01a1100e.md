# DATA-DISH-MANUAL-01a1100e: 고정 입력과 검수 근거

## 원본 및 소비 고정값

- 소비 commit: `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`
- 원본: `data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf`
- 문서: `DUE6BGL2E-manual-ff60f78ab832` / `MFL71959117 Rev.07_030626`
- PDF:60쪽 /5,946,269 bytes / SHA256 `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5`
- 적용군: 공용 DUE6****E 등. 정확SKU/구입시점 적용은 기존 승인 source mapping 소비 및 별도 미확인 상태.
- [입력6파일의 고정 commit 원바이트 비교](../../../../evals/data-dish-manual-audit/20261007-01a1100e/source-inspection.json)
- [기존 추적파일4,232개/178,400,766 bytes의 원바이트 Git blob 비교, 불일치0](../../../../evals/data-dish-manual-audit/20261007-01a1100e/original-preservation.json)

## 실제 검수

- 기존 R8 DUE manual6개: native 원문 문장(공백만 정규화), ResearchBundle source 전체, dataset/plan 원문·쪽, facts·locator, 모델·판본·SHA의36항목 일치.
- 새 검수용14개 native 범위: 안전5; 내부/음식물필터39~40; 세척조41~42; 노즐42~43; 보관43; 냄새49; 성능50; 노즐 회전 진단48.
- 렌더/육안 확인14쪽:1,2,5,20,23,24,39,40,41,42,43,48,49,50. 렌더 합계2,055,202 bytes. 원PDF 전체 중복은0.
- 49쪽 제품 냄새/세척 후 비린내의 조건별 표 행,50쪽 배열/노즐/필터 조치 행을 수동 확인. 실제 자동 구조 출력은 없어서 검증 불가.
- 최초 새 script anchor오류 exit1과 후속 수정 exit0, native43쪽의50℃ 문자 깨짐을 원이력/정본 렌더와 구분해 기록.

## 산출물 연결

- [연결별 구조화 표](../../../../evals/data-dish-manual-audit/20261007-01a1100e/audit-table.json)
- [원문 범위·쪽·문자 오프셋·SHA](../../../../evals/data-dish-manual-audit/20261007-01a1100e/manual-native-excerpts.json)
- [시각 검수 및 각 PNG SHA](../../../../evals/data-dish-manual-audit/20261007-01a1100e/visual-review.json)
- [실행 오류와 수정 이력](../../../../evals/data-dish-manual-audit/20261007-01a1100e/execution-history.json)
- [작업기록](../../../작업기록/신진하/2026-10-08/DATA-DISH-MANUAL-01a1100e.md)

이 결과는 독립 원문 검수다. 제품 모델/OCR 호출·운영 HTTP0, 공통 코드/생산 자료/개인 README 수정0. 고객 원인·호전·시장 효과·자동 표 성능·PM 인수/부모Done은 증명하지 않는다. GitHub 게시·PR·push는 root 조정 창에서 수행한다.
