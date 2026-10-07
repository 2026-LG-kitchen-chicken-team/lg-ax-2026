@jeongiryang @unknownamed 식기세척기 냄새·관리·문제 해결 공식 설명서의 독립 검수 결과입니다. 기존 D1/D2 생산·D3/D4 표본/split·PR246 수정과 겹치지 않는 새 audit-only 폴더에서 수행했습니다.

- 소비 source `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`, 설명서 `MFL71959117 Rev.07_030626`, PDF SHA `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5`.
- 기존 R8 DUE manual6개의 원문·facts·locator·모델·판본·SHA·producer 연결36항목은 일치합니다. 하지만 위치20/23/24쪽은 배열·높이·노즐 간섭 조건이므로 청소법/냄새 해결 근거로 전이하면 미지지입니다.
- 원본에는 실제 내부/음식물필터39~40쪽, 세척조41~42쪽, 노즐42~43쪽, 보관43쪽, 냄새49쪽/성능50쪽의 절이 있습니다. 새 검수용14범위와14쪽 렌더를 대조했습니다. 기존 고정 R8 DUE manual6개에는 이 관리·냄새 구간이 없습니다.
- 49쪽의 제품 냄새/세척 후 비린내와 조건별 질문·조치,50쪽 배열/노즐/필터 조치를 수동 확인했습니다. 공식 지침의 존재는 해당 고객의 원인 확정·호전·지원 약속을 증명하지 않습니다. 구입 SKU/구입시점 판본도 미확인입니다.
- 원본 추적파일4,232개 원바이트 불일치0, 모델/OCR/운영HTTP0, 기존 코드·자료·개인 README 수정0입니다. 수동 표 검수는 자동 셀·행·열·각주 출력 검증이 아니며 자동 구조 출력은 미수령입니다.

필요한 인계:

1. DATA D2 담당: 필요한 새 관리/냄새 절을 원문·조건·쪽·판본·SHA를 보존한 별도 자료 버전으로 생산/인계. 이번 검수는 생산 파일을 수정하지 않았습니다.
2. CORE @unknownamed: 배열/높이 경고와 필터/세척조/노즐 관리 절을 구분해 소비한 고정 결과와 원 source ID 매핑을 제공. 원인 확정·해결 약속은 실제 근거를 별도로 연결해야 합니다.
3. PM @jeongiryang: 공용 DUE6 계열 적용 범위를 인수하고 새 runtime shorthand를 full source ID·판본·쪽·SHA로 연결. 공개 registry의 `MW23FDI-MANUAL-M11`은 전자레인지 출력 조절 p25여서 식기세척기 근거로 전이할 수 없습니다.

산출물: `evals/data-dish-manual-audit/20261007-01a1100e/README.md`, `audit-table.md/json`, `manual-native-excerpts.json`, `source-inspection.json`, `visual-review.json`, `original-preservation.json`. 새 검수 PR 번호·고정 head와 링크는 게시 조정 창에서 연결합니다. 부분 원문 검수이며 실제 냄새 해결·최종 의미 품질·부모Done 승인은 아닙니다.
