# R5 원3응답 독립 대조 — CORE-R5-RAW-AUDIT-01a10729-01

황대겸 / unknownamed, 2026-10-07 KST. [PM 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/11#issuecomment-6028738057)과 [원본 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/11#issuecomment-6028757487)에 따른 독립 원문 대조다. PM 보조 CORE의 구현 파일은 편집하지 않았다.

[불변 원본·공개 경계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/814fe2fbcd3b752ff6400d8a08671dce7bdd2d80/evals/pm-integration/20261007/live-originals/README.md), [대조 JSON](comparison.json), [재현 대조기](verify_originals.py), [격리 검사 manifest](manifest.json)를 함께 읽는다. 원본은 실제 고정 Qwen3.5-122B 호출 결과이고 **입력 자료는 합성 냉장고 사례**다. 이번 작업의 신규 모델 호출은 0이며, 이전 15회·91,587토큰과 failed/failed/held를 보존한다.

## 판정 대조표

| 사례·위치 | 원본에서 직접 확인한 사실 | 독립 판정·수정 후 확인 조건 |
|---|---|---|
| 정상 / `model_calls[4].request_context` 및 반환 `quality_assessments` | NEED007→RE008, GAP007→NEED007, CONCEPT001→GAP001/007 및 RE001/008/MANUAL001이 이미 전달됐다. `mechanism`은 RE008을 인용했지만 `difference_from_current_features`는 RE001/MANUAL001만 인용했다. | 후보의 RE008 누락으로 분류하면 잘못이다. 차별점 **검수 항목별 인용 완전성** 실패이며 `difference_requires_review_and_manual` 거절은 유지해야 한다. 새 head에서 선택 Gap별 요구 인용과 해당 검수 항목의 범위를 대조한다. |
| 정상 / `model_calls[5]`, `trace`의 `review_revision` | 수정2 답변은 `status=held`, `questions=[]`, `hold_reasons=[]`. 이전 `violations`에는 CONCEPT001/GAP007/NEED007/RE008/MANUAL001 상세가 JSON 문자열로 전달됐다. 실제 guard는 `HOLD_WITHOUT_QUESTIONS`로 거절했다. | 질문 없는 보류를 이미 허용한 사례로 쓰지 않는다. 거절이 실제 유지됐고 원 최종 상태는 failed다. 새 head는 실제 자료 부족과 구체 질문을 연결해야 하며, 질문 자동 작성이나 forced accept는 허용하지 않는다. |
| 조건 변경 / `model_calls[3]`·`[4]` | CONCEPT002는 GAP002/009의 RE002/RE010만, CONCEPT003은 GAP005의 RE005만 인용하여 두 시도 모두 MANUAL001을 누락했다. 해당 Gap에는 MANUAL001이 전달돼 있었다. 수정2 `feedback`은 `[{"code":"CONCEPT_GROUNDING_MISSING","stage":"concepts"}]`뿐이었다. | 자료 자체가 없었던 것이 아니다. 후보별 누락 근거 ID를 제공받고도 반복 누락했고, 실제 재시도 피드백에는 대상 후보/Gap/누락 ID가 없었다. 새 head의 구조화 근거·피드백 전달을 대조한다. 이 원 실행은 의미 검수에 도달하지 않았다. |
| 설명서 부족 / `model_calls[3].request_context.judgement.needs`, `no_candidate_reviews[0].reviewed_output.needs`, 최종 `output.needs` | 세 위치에 NEED006→RE007이 동일하게 존재한다. 검수자는 `review_polarity=violation`과 “누락된 Need를 추가해야 합니까?”라는 질문을 반환했고, 최종 질문에도 그 주장이 남았다. | 검수의 Need 누락 주장은 원 입력과 모순이다. 이미 존재하는 Need에 대한 주장 오류와 수정 대상 누락을 구분해야 한다. 새 head에서 이 주장을 검증하되 실제 존재하는 다른 누락을 숨기거나 의미를 자동 치환하지 않는다. |
| 설명서 부족 / `input.features`·최종 사유 | 기능 배열은 비어 있고 최종 상태는 held다. 설명서/기능 명세 확인 질문도 있다. | 자료 부족 보류 자체는 적절하다. 위의 잘못된 Need 질문을 고친다는 이유로 근거 없는 후보 생성·accept 또는 보류 제거를 하지 않는다. |

원본 JSON의 모든 모델 답변 15개를 `raw_response` JSON과 `generated.data`에 직접 대조했고, 세 파일의 SHA·바이트 수·원 호출/토큰·모델 digest·수정 최대2를 검증했다. 상세 위치와 원문 발췌는 `comparison.json`에 있다. 모델 텍스트는 검수 자료이며 실행 지시가 아니다.

## 재현과 한계

원본 파일을 위 고정 커밋에서 내려받고 SHA를 확인한 뒤 인증·소켓 없는 Docker에서 다음을 실행한다. `/originals`는 세 원 JSON의 읽기 전용 마운트다.

```text
python3 -B verify_originals.py --originals /originals --output /result/comparison.json
```

실제 검사 환경은 고정 이미지, UID65534, network=none, root/source/originals 읽기 전용, cap-drop ALL, no-new-privileges였다. 결과 파일만 별도 쓰기 마운트했다. 대조기 초기 세 번의 경로 오류(평탄화 semantic 입력, revision의 previous.violations, concept의 skill_input.gaps)를 원 기록에 남기고 올바른 원 경로로 고친 뒤 통과했다. GitHub 큰 원본의 encoding=none 다운로드 오류도 Git blob 조회와 객체 SHA/SHA256 직접 대조로 복구했다. 원 결과는 수정하지 않았다.

**새 PM 수정 PR의 정확한 head는 아직 인계되지 않았다.** 이번 결과는 원 반례 확인이며 새 코드의 해결 여부·정상 실모델 완주·3제품 품질·기존 여섯 사례 새 채점·PM 승인/병합/운영 통합/Done을 입증하지 않는다. 다음 행동은 PM head를 인수하여 같은 원본과 좁은 코드/검사 결과를 독립 대조하는 것이다. 신규 모델 배치는 별도 유한 조건 인계 후에만 수행한다.
