# P2-DATA-002 — 황대겸 고정 결과 원문 대조

확인일: 2026-10-06 KST. 목표는 **기존 고정 결과**의 citation/source 의미 대조다. model job 재실행, 판단 코드 수정, 독립 답안/승인은 수행하지 않았다.

## 비교 기준과 무결성

황대겸이 #13에 16:54 KST 전달한 결과 commit `9c7188a29138f43b377c2cac763ab954bc802330`의 `original_input.sources`를 동일 commit `45fe0f23afb9c68e115088cef9e10cd122d181f1` 입력 자료와 대조했다. 각 source의 ID, source type, model ID, document version, source kind, source ID, locator, 한국어 text가 현재 canonical 데모 dataset과 정확히 일치하는지 읽기 전용으로 비교했다.

| 입력 파일 | 입력 SHA-256 | 모델 / digest | 상태 / 실제 호출 / 수정 | 정확 일치한 source | 주요 인용·기능 대조 |
|---|---|---|---|---|---|
| [8b-bounded12/fridge-normal.json](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/9c7188a29138f43b377c2cac763ab954bc802330/evals/pm-prototype/20261006/finite-model-study/8b-bounded12/fridge-normal.json) | `91bbb9aa695d298b80b0e10c1f0abc5e643ca0f6790ec1194f5303c7230747d6` | `qwen3:8b` / `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | failed / 9 / 2 | 11/11. `FRIDGE-A`, 문서 `1.0`, synthetic; `MANUAL-001` p.1 §선반 분리와 `REVIEW-EVIDENCE-001~010` 행2~11 | 명시적 불편 8개(001~005,007,009,010)를 polarity `positive`로 분류했다. 계약상 불편은 `complaint`, 불편 없는 칭찬은 `positive`다. REVIEW-006의 긍정 평가는 맞지만, 명시 불편 009·010이 NEED/GAP에서 빠졌다. NEED-006은 아직 불편을 진술하지 않은 REVIEW-008의 희망만으로 만들었다. 7개 GAP이 모두 선반 분리 FEATURE-001에 연결돼, 안쪽 식품 찾기·가족 간 식품 위치 표시·바구니 세척 같은 다른 내용을 같은 선반 기능이 지지하는 것처럼 보인다. 최종 실행은 `NON_COMPLAINT_AS_NEED`, `ASSESSMENT_COVERAGE` 위반으로 실패했고 independent quality는 null이다. |
| [8b-bounded12/microwave-normal.json](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/9c7188a29138f43b377c2cac763ab954bc802330/evals/pm-prototype/20261006/finite-model-study/8b-bounded12/microwave-normal.json) | `a0483657fef00979717bfa8b27ec0710c2314e748780e2d97e83043a188bea01` | `qwen3:8b` / `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | failed / 9 / 2 | 4/4. `MICROWAVE-A`, 문서 `1.0`, synthetic; `MANUAL-005` p.5 §설정 저장과 호출 및 `REVIEW-EVIDENCE-034~036` 행35~37 | NEED-001은 반복 입력 리뷰 034 하나만 인용한다. 그러나 GAP-001/002/003은 세 gap 각각에 034·035·036 전부를 붙여, 설정 저장 기능을 몰랐다는 035와 호출 버튼을 찾기 어렵다는 036을 같은 NEED-001에 연결했다. 035·036의 개별 NEED가 없다. MANUAL-005에는 시간·출력 저장 후 원터치 호출 기능이 명시돼 있어, 기능 부재와 저장 등록 조건·인지/버튼 발견 문제를 분리해야 한다. 세 리뷰 polarity는 모두 `positive`로 출력돼 명시 불편 034·036도 complaint로 반영되지 않았다. 결과는 `NON_COMPLAINT_AS_NEED`, `ASSESSMENT_COVERAGE`로 실패했고 independent quality는 null이다. |
| [27b-bounded12/fridge-normal.json](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/9c7188a29138f43b377c2cac763ab954bc802330/evals/pm-prototype/20261006/finite-model-study/27b-bounded12/fridge-normal.json) | `009c0bb2df3caeaf3c60b130fb5cbd7ea98b020dc17695d4e2a9a92a80b87803` | `qwen3.5:27b-q4_K_M` / `64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59` | held / 3 / 0 | 11/11. `FRIDGE-A`, 문서 `1.0`, synthetic; 냉장고 8B와 같은 고정 원문·ID | 명시 불편 8개(001~005,007,009,010)의 polarity가 모두 `positive`다. GAP-003(안쪽 찾기)·GAP-006(가족 간 위치 공유)를 `unsupported`로 둔 판단은 선반 분리 설명서와의 범위가 맞다. 반면 GAP-005는 REVIEW-005의 **바구니** 세척을 shelf-only `MANUAL-001`로 뒷받침하고, GAP-007은 식품이 많으면 청소를 미룬다는 리뷰와 선반 분리 전 위 식품을 옮기라는 설명을 인과 근거처럼 결합한다. 설명서 문구는 선반 **위** 식품을 옮기라는 뜻이며 냉장고 안 모든 식품 제거라는 뜻으로 넓히지 않아야 한다. 세 concept은 proposal로 표시됐지만 `concept_assessments.duplication=duplicate`와 그 사유의 “차별화”가 서로 모순된다. 최종 결과는 `NON_COMPLAINT_AS_NEED`, `SUPPORT_BASIS_MISMATCH`, `SUPPORT_UNKNOWN`, `CONCEPT_WITHOUT_CONFIRMED_GAP`, `DUPLICATE_CONCEPT`로 held; independent quality null이다. |

모델 digest는 각 고정 결과 summary의 원 값을 보존했다. 세 결과 모두 `source_kind=synthetic`; 이것들은 실제 LG 제품 SKU의 설명서 기능 또는 실제 고객 리뷰 검증 결과가 아니다. `rejected_output`이 validator가 거절하기 전 model 제안의 보존 위치이고, 최종 `output`의 failed/held 상태와 구분했다.

## 원문·파일 바이트 확인

| 원자료/manifest | 확인 SHA-256 | 결과 |
|---|---|---|
| `data/demo/dataset.json` 파일 bytes | `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0` | 고정 summary의 file hash와 일치. 이 36건은 manifest상 synthetic이다. |
| dataset canonical JSON | `8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03` | source summary와 일치. |
| `data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv` | `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9` | 36행·8열 그대로다. |
| 고정 출력 `source-manifest.json` | `d35f1741ab6cfcb197344439bfef791c9516bccbb22f7e44c40e6c5c4be9f1b0` | 세 표의 output bytes가 manifest의 불변 결과 SHA와 일치한다. |

본문/모델/버전/자료 성격을 교차 바꾸는 기능 검사는 별도 DATA collector 회귀에서 오류 거부했다. importer의 NFC/NFD 회귀도 둘의 UTF-8 표기를 각각 보존하고 CSV 원 bytes/hash 불변을 확인했다. 이는 fixed-output semantic audit와 구분한다. 실제 업로드→검색→서비스 재시작 경로와 real-SKU 자료 대조는 별도 검증으로 남는다.
