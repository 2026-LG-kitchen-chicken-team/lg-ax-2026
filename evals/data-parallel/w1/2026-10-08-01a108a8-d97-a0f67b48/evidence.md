# DATA-W1-01a108a8-d97-a0f67b48 근거

확인일 2026-10-08 KST. 검수 base `eab85d48385f965eef48c07a6cdd8f6fd9851c62`; 원응답 publication `a90196b439702f059bf8f080e5770c293ea90c79`; 원응답 generation process commit은 null.

- 입력 원본: [변경97dbc 전체 공개 JSON](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/a90196b439702f059bf8f080e5770c293ea90c79/evals/web/20261008/w1-shared-prototype/run-97dbc649.job-response.json), Git blob `5deaa681c2ddb3959b558d5d9faba828de41f007`. W3 수신증의7,425bytes/파일SHA `e008c91fd9d1de097e6b377f0d546ce021bb686dbf23f49ed0504dcca060b6aa`/result canonical `bc72af4bc89943d89783c3a8f8c9dab0820578b6fa53c2a7d0ac8a0696f3c592`를 재사용. W1은 원파일SHA를 다시 계산하지 않았다.
- 비교 원문: main 고정 냉장고 bundle와 [PR292 Source anchors](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/2af0601caa527e1d2389d2f0a302daf9e1943783/evals/data-parallel/w1/2026-10-08-01a108a8-0823-9b837714/source-anchors.json). 페이지 모델 T876MEE1H1, 정확 구매SKU/구매시점 판본/게시일은 미확인이다.
- 기존 판정: [정상17행](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/2af0601caa527e1d2389d2f0a302daf9e1943783/evals/data-parallel/w1/2026-10-08-01a108a8-0823-9b837714/normal-semantic-review.json)·[변경8행](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/2af0601caa527e1d2389d2f0a302daf9e1943783/evals/data-parallel/w1/2026-10-08-01a108a8-0823-9b837714/changed-semantic-review.json), [CORE 전체 검토](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/291#issuecomment-6056456435)·[CORE292 인수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/292#issuecomment-6056753310). 원17/8행은 수정하지 않았다.
- 조건·입출력: public runtime 모델 qwen3.8:27b-q4_K_M/digest25b84361…·context16384/output4096·call2/repair0는 원응답 필드다. 정상 조건에 하드웨어 변경 금지가 추가돼 동일 조건 방법 비교로 인정하지 않았다. 생성 prompt/wire·sampling/전체 native usage는 미수신이다.
- 수행 검사: 새 54 JSON pointer 값·기존 행ID/anchor 참조·새 의향 Unicode span 하나, 변경 부모/revision 및 수행 경계 직접 대조. Python 관리 스크립트의 parse/location 확인이며 제품 코드·모델·OCR·과거 검사/채점/운영 재호출은 실행하지 않았다. [검사 기록](verification.json), [산출물 SHA](artifact-manifest.json).

지지하는 주장은 이 공개 전체97dbc 필드의 수신과 원문 위치/기존 판정 연결이다. 지지하지 않는 주장은 현행 CORE 수정 효과·모델 전체 입력/운영 보존·동일7 비교/무Gold4 평가·고객 수요·PM/Gold/최종 Done이다.
