# CORE 수동 큐 인계 — 기존 27B 재사용과 실제 자료 계약

기록 ID: `CORE-MANUAL-QUEUE-PREFLIGHT-01a10729-01`. 황대겸의 수동 작업이며 제품 코드·모델 서비스는 변경하지 않았다.

## C1: 이미 실행한 정확한 27B 버전

2026-10-05의 실제 실행 결과가 남아 있다. [역사 결과 대조 JSON](historical-27b-reuse.json)의 12개 원 파일을 보관 commit `e7005f7cc0a6bb56bb6abb411dd9d48014c828fa`와 바이트/SHA256로 직접 대조했다.

| 항목 | 당시 실행 기록 |
|---|---|
| 모델 | `qwen3.5:27b` — Qwen 3.5 27B |
| 모델 revision/digest | `64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59` |
| 양자화·런타임 | `Q4_K_M`, Ollama `0.34.0` |
| 호출 방식 | Chat API, `thinking=false`, native JSON Schema와 로컬 검증 |
| 입력 문맥·최대 출력 | `num_ctx=16384`, `num_predict=8192` |
| 샘플링 | temperature `0.7`, seed `42`, top_p `0.8`, top_k `20`, min_p `0` |
| 요청 timeout·응답 상한 | `300`초, `131072`바이트 |
| 당시 통합 main | `c05ee880b160353414180e689f32a42dd23c2d64` |
| 원 실행 소스 | 각 summary의 `source_sha256`; 현재 코드와 같다는 주장은 하지 않음 |

- [3제품 변경 전후 실행](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/e7005f7cc0a6bb56bb6abb411dd9d48014c828fa/evals/core-live-completion/20261005/selected-27b-three-products-04/summary.json): 냉장고·식기세척기·전자레인지 각각 before/after, 총6실행/24모델 요청. 모두 런타임 `completed`, 각1후보. 입력은 합성 자료다.
- [새 HOLD-01~06의 Agent/일반 LLM 기준선 비교](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/e7005f7cc0a6bb56bb6abb411dd9d48014c828fa/evals/core-live-completion/20261005/comparison-summary.json): Agent13요청, 기준선6요청. 이전 SEM-01~06 비교와 별도 실행이며 합산하지 않는다. Agent HOLD-03의 실행 실패도 보존한다.
- [기존 독립 AI 평가](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/e7005f7cc0a6bb56bb6abb411dd9d48014c828fa/evals/core-live-completion/20261005/independent-ai-assessment/provenance.json): Agent PASS2/FAIL1/UNCERTAIN3, 기준선 PASS3/FAIL3. 평가를 다시 실행하지 않았다. 정식 평가·PM 인수는 미완료이며, 당시 수정 후 실모델 회귀도 미완료다.

위 결과는 과거의 정확한 모델 식별과 결과 재사용 근거다. 새 실제 리뷰·FAQ 기반의 문제 발견/시각 기획 경로 검증이나 현재 27B 연결의 가용성을 증명하지 않는다. 현재 LG 중계의 읽기 전용 모델 목록에서는 `qwen3:8b`만 확인됐다. 다른 환경의 27B 존재 여부는 확인하지 않았다.

사용자는 **PM에게 준비된 LG 전용 27B 연결·고정 버전을 인계받기**를 선택했다. PM은 기존 digest와 같거나 다른지를 표시하고 정확 모델/digest·런타임·LG 전용 연결 설정·고정 실제 입력·허용된 작은 실행 범위를 인계해야 한다. 접속 비밀은 공개 기록에 넣지 않는다. 기존 연구실 서비스 변경·27B 재설치·새 모델 실행은 수행하지 않았다.

## C2~C4/X1: 최신 배정과 소비 계약의 차이

지시 출처는 [#234](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234), [CORE 상세 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/4#issuecomment-6037771600), [P0/DATA 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-6037771036), [X1 #238](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/238)이다. [소스 대조 JSON](source-contract-comparison.json)은 최초 main58fe/PR2335533와 최신 main `c2d840ab13140809c404ee239b3c08d01cbe771c`/PR233 `0c82d81a06d4ec81712b175a89891ac5c2328460`의 관련5파일 SHA가 각각 동일함을 확인한다. 최신 main에 `docs/pm/manual-queue-20261007.json`은 없어서 Issue 큐를 배정 원문으로 연결했다.

| 실제 관찰 | 필요한 인계와 다음 행동 |
|---|---|
| `Evidence.source_type`은 review/manual뿐이고 `Product.model_id`는 null 불가 string이다. P0는 qa/faq/spec/installation과 정확 모델 미확인을 구분하도록 배정했다. | PM P0의 버전 고정 계약과 DATA D1/D2의 원문 위치·정확 SKU/미확인 처리 인계 뒤 CORE 소비에 반영한다. 미확인 구매 SKU를 제품군 ID로 대신 확정하지 않는다. |
| 기존 `held` 출력은 후보0 계약이다. `planning_agent`는 보류/미해결 또는 비완료 때 후보/평가를 비우지만 `rejected_output` 원본은 보존한다. | C2의 유효후보 보존과 진짜 자료부족 held를 함께 표현할 P0 계약이 필요하다. 부분 유효 결과·실패 항목을 구분하는 합의 없이 가드 삭제/forced accept를 하지 않는다. |
| `Concept`에는 구조화된 개선 전후 단계·작동 방식·기획 장면 필드가 없다. | C3의 같은 실제 자료·조건 변경 revision과 WEB W1이 소비할 버전을 PM P0에서 연결한 뒤 좁은 CORE 구현을 한다. |
| 기존 `ReviewTrendMetadataRow`에는 양면/혼합 평가 및 제품/배송/설치/케어 맥락 필드가 없다. | C4의 건수·분모는 원 데이터로 계산하고 LLM 의미/반대근거와 구분하는 출력 계약을 인계받는다. 합성 리뷰로 채우지 않는다. |
| X1은 실제품 공식 안내와 미래 제안 설명서를 구분하는 D2/C3 의존이다. | 고정 공식 원문/정확 모델과 채택할 기획 출력이 도착하면 CORE 안내 생성만 연결하고 WEB/API/MCP는 해당 담당에게 인계한다. |

이번 단위에서 완료한 것은 원 결과/정확 모델 버전 회수, 현재 LG 모델 목록 확인, 최신 소스와 배정의 차이 대조 및 담당 인계다. 기존 검사97개·독립 평가6사례·새 모델 실험을 반복하지 않았다. PM의 CORE 지원 편집과 공통 계약을 중복 수정하지 않았다. 위 의존과 관계없는 필수 작업은 이어가며, 새로운 모델/비용/사람 판단이 필요한 항목은 해당 의존만 보류한다.

상세 기록: [작업기록](../../../../docs/작업기록/황대겸/2026-10-07/CORE-MANUAL-QUEUE-PREFLIGHT-01a10729-01.md), [근거](../../../../docs/작업근거/황대겸/2026-10-07/CORE-MANUAL-QUEUE-PREFLIGHT-01a10729-01.md).
