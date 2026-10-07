### CORE-MANUAL-QUEUE-PREFLIGHT-01a10729-01 — 고정27B 결과와 새 계약 의존의 근거

- 담당자 황대겸 / 확인일 2026-10-07 KST / [연결 작업기록](../../../작업기록/황대겸/2026-10-07/CORE-MANUAL-QUEUE-PREFLIGHT-01a10729-01.md).
- 근거 종류: 사용자 직접 선택, native GitHub 배정/소스, 현재 LG 읽기 전용 수신, 고정 commit의 역사 실제 모델 실행 기록. 신규 제품 실행/모델/평가가 아니다.

#### 기존 모델 버전과 결과 원본

모델은 `qwen3.5:27b`, revision/digest `64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59`, 양자화 `Q4_K_M`, 기록된 Ollama 런타임 `0.34.0`이다. Chat/thinkOFF/16,384문맥/8,192출력, temperature0.7/seed42/top_p0.8/top_k20/min_p0, timeout300초는 [대조 JSON](../../../../evals/core-manual-quality/20261007/manual-queue-preflight/historical-27b-reuse.json)에 원 경로와 SHA를 연결했다. 버전은 이름만 기록하지 않고 digest와 실행 소스 해시로 식별한다.

- 원 결과 보관 head: `e7005f7cc0a6bb56bb6abb411dd9d48014c828fa`; 당시 통합 main: `c05ee880b160353414180e689f32a42dd23c2d64`.
- 실제 대조: stdlib 파일읽기/JSON/SHA와 `git show <고정SHA>:<원경로>` 바이트 비교, 원12파일 모두 동일. 원3제품 before/after6 raw의 SHA는 summary와 일치했다. 원 파일·원 점수 수정0.
- 3제품 총6실행/24모델 요청: 런타임completed/각1후보. HOLD01~06 Agent13/기준선6요청: 실행 실패 HOLD03도 보존. SEM01~06/과거 prior는 별도이며 새 HOLD6 합계에 넣지 않는다.
- 기존 독립AI 평가: Agent PASS2/FAIL1/UNCERTAIN3, 기준선 PASS3/FAIL3. 평가 재실행0. 평가자는 인간이 아니며 고정 평가 모델ID/OS격리 노출이 없다는 원 한계를 유지한다.
- 당시 수정 코드의 실모델 회귀·정식 평가·PM 인수는 원 provenance에서 false다. 합성 자료 실행을 현재238실제리뷰 기획 검증으로 승격하지 않는다.

#### 현재 모델과 배정/소스 대조

현재 LG 중계의 모델 목록 GET200은8B만 노출했다. 모델별 전역 설치 유무나27B 서비스 소실을 단정하지 않는다. 인증/endpoint는 비공개 수신에만 남겼다. Worker/PM운영 OFF, 서비스/모델 생성/다운로드/호출0이다.

최신 main `c2d840ab13140809c404ee239b3c08d01cbe771c`, PR233 head `0c82d81a06d4ec81712b175a89891ac5c2328460` (열림/미병합·리뷰0/줄별댓글0 관찰)의 관련5파일 SHA는 최초 main58fe/PR2335533 대조와 각각 동일하다. [소스 비교 JSON](../../../../evals/core-manual-quality/20261007/manual-queue-preflight/source-contract-comparison.json)에 최초 관찰과 후속 확인을 함께 보존했다.

- 계약 원본: `Evidence.source_type` review/manual, `Product.model_id` string/null불가.
- `Concept` 필드는 id/title/kind/gap_ids/evidence_ids/differentiation/requirements/assumptions/status. 구조화된 before/after/scene은 없다.
- 기존 trend metadata 필드는 review/evidence/source/model/document/text/date/topic/classification/dedup 묶음이며 mixed/context 소비 필드가 없다.
- PR233 `planning_agent`의 output/terminal과 `judgement_contract`는 held후보0; 원 `rejected_output`은 복사보존. C2 유효후보 보존을 위해 이 가드를 먼저 없애는 것은 현재 계약 위반이다. 부분 유효 상태/실패 항목·진짜 자료부족 표현의 P0 인계 뒤 좁은 수정을 한다.
- [PM CORE 원 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/4#issuecomment-6037771600), [P0 원 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-6037771036), [#234](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234) 및 [#238](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/238)과 직접 대조했다. Issue의 예정 queue파일은 확인 main에 없었다. 배정/코드 검증을 인수 완료로 바꾸지 않는다.

#### 자기 검수·한계·후속

이번 diff는 본인 기록/근거/README marker 내부와 대조 산출물뿐이다. 공유 코드·소스·Worker/PM 설정·옛 원 결과를 변경하지 않았다. 개인README marker 밖 바이트/기존 링크를 보존하고 새 상대링크·JSON 및 문서 탐색을 검증한다. [검증 수신](../../../../evals/core-manual-quality/20261007/manual-queue-preflight/validation.json)은 해당 실행 결과를 기록한다.

기존97검사/6AI평가/소스 검수는 다시 수행하지 않는다. 이번 증거가 지지하는 것은 과거27B 실제 실행과 정확 버전, 새 소비 계약의 차이, PM 연결 인계 필요다. 현재 실제자료 기획 품질·모델 채택/운영·PM 승인/부모Done은 미완료다. 다음은 PM이 P0/27B를, DATA가 D1/D2를 고정하고 본인이 관련 CORE 수정/검증을 이어가는 것이다.
