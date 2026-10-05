# 2026-10-06 원본 6사례 실모델 출력 대조 검토

2026-10-06 오전 KST, PM이 별도 실행한 원본 6사례를 고정 입력·설명서·리뷰·실제 호출 기록과 대조했다. **완료 0, 보류 1, 실패 5이며 후보 생성에 도달한 사례는 0이다.** 잘못된 결과를 승인하지 않고 최대 2회 수정에서 멈춘 것은 확인되지만, 상품기획 의미 품질·세 예시 정상 처리·조건 변경 준수의 완료 근거가 아니다. 확인된 수요·효과 측정은 0건이며 모든 사례의 제품·설명서·리뷰는 합성 자료다.

이 검토의 수행 AI는 실행 담당 PM AI와 별개로 출력을 읽었지만 CORE 인수·수정에도 참여했다. 따라서 실행과 분리한 반대 근거 검토이며, 개발과 분리된 맹검 평가자·사람 패널·강한 일반 LLM 기준선 평가를 충족했다고 주장하지 않는다. 모델을 추가 호출하거나 원 실행·원 입력·개인 기록·운영 상태를 수정하지 않았다.

## 고정 조건과 근거

- 원 실행 source: `37f7e3fd0e76eff8115941e7d456ffdf6424d0d4`.
- 모델: `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- 설정: temperature 0, seed 42, num_ctx 16384, num_predict 8192. 모델 크기·설정을 바꾼 재시도는 아니다.
- 합성 dataset: `evals/pm-intake/20261006/core/synthetic.dataset.json`, SHA256 `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`, dataset version `0.1.0`, 문서 version `1.0`.
- 입력: 같은 source의 `core/cases/{fridge,dishwasher,microwave}-{normal,changed}.input.json`. 각 출력의 `original_input.request/sources/features`가 고정 파일의 같은 필드와 일치함을 읽기 전용으로 대조했다. changed는 제외 조건만 변경한 새 요청이며 내부 회차 0에서 시작한다.
- 원 증빙: Git 제외 영역 `private/runtime/live-intake-37f7e3fd0e76/{case_id}/output.json`, 각 `relay.json`, 공통 `summary.json`. 아래 출력 hash는 원 JSON 전체 파일 기준이다. 비밀·접속 정보·원 전송 base64는 이 문서에 옮기지 않는다.
- summary의 격리 경계는 모든 사례에서 source_unchanged=true, network=none, publisher_credentials_mounted=false, ai_profile_mounted=false, uid1000, readonly_root=true, stop=null, relay_failed=false이다. source 코드의 성공 종료/프로세스 exit 0과 Agent의 held/failed를 구분한다.

| 사례 | Agent 결과 | 실제 생성 호출 | 보고 토큰 합 | 내부 수정 회차 | 직접 종료 원인 |
|---|---|---:|---:|---:|---|
| fridge-normal | held | 2 | 11,550 | 0 | GAP_MANUAL_MISSING + UNSUPPORTED_WITHOUT_MANUAL |
| fridge-changed | failed | 4 | 22,100 | 2 | GAP_MANUAL_MISSING 반복; 중간에는 GAP_REVIEW_MISSING |
| dishwasher-normal | failed | 5 | 17,370 | 2 | NON_COMPLAINT_AS_NEED 수정 후 GAP_REVIEW_MISSING 반복 |
| dishwasher-changed | failed, output=null | 5 | 16,684 | 2 | NON_COMPLAINT_AS_NEED → HOLD_WITHOUT_QUESTIONS → Need/희망 결과 대응 누락 |
| microwave-normal | failed | 4 | 12,542 | 2 | Need/희망 결과 대응 누락 수정 후 GAP_MANUAL_MISSING |
| microwave-changed | failed, output=null | 3 | 8,308 | 2 | 세 Need에 희망 결과 한 개만 반환하는 오류를 세 호출 모두 반복 |

합계는 실제 생성 23회, 보고 토큰 88,554이며 summary에서 usage_unknown=false이다. 강한 기준선과 동일 조건 비교·사람 수정 시간·수요/효과를 측정하지 않았으므로 절감률·우월성·사업 효과를 계산하지 않는다.

| 사례 | 고정 입력 파일 SHA256 | 원 출력 파일 SHA256 |
|---|---|---|
| fridge-normal | `52440224ab725391c2677383b6aab4b5a9a0cdde1b450d76efe74af7b59e9aea` | `547a637b3d6278a7a0831fad0b7cdf01f3e0733c9d5f56458c8a761491f0ecd1` |
| fridge-changed | `74dd4e2b4dbbbfc4c4cd43c24777e1415c57072d972967e9090e6a9ca2f3d67d` | `7cbe2b3d35950b155303115c8e93759011aa17dd832ea6cb6af362f2b5095c34` |
| dishwasher-normal | `d70d7cb19291a646d5e30e00739df5ace9924a5c680d3ff97a3273d98468257b` | `88a1275cf44de7794fcefcad059b8ec8085fa4af7b5f888e72c2bf94908ab4b5` |
| dishwasher-changed | `0f43c972b71a849d6d3d12b9a06514ad1dcf84954a717ddd396302a0359c1d99` | `a2e4e5b2a23bf99a48ad39cb92699b62ca4db86dc2d8a8068173de9613b09fa1` |
| microwave-normal | `01aa87a43018e6d213be988da17ddf212553e0733bf5a46cb202bc0414196a7e` | `9502ed736ca54a739f31c3b78f75878828f11c5aa555701f749e26489ca95851` |
| microwave-changed | `138b895caf1945f9faf6c41610b67c1d169f3ff49d523bcf3b8576ce56127d87` | `f0fcd37829d621f15e13e05e920b2cf568a7f55b94d5b641e01f3a68fe10b887` |

## 제출 예시와 평가 입력의 정렬

[제출제안서 원고](../../../기획/제출제안서_원고.md)의 세 예시를 원 source에서 읽었다. 특히 식기세척기 설명 59~70행은 **기본 적재 그림과 실제 식기 조합 차이 → 조합별 배치 안내**이며, 식기 종류·크기 입력, 적재 순서, 큰 식기와 회전 날개 간섭 확인을 결과로 설명한다. 그런데 이번 dishwasher 두 입력은 `use_situation=오염 정도에 맞는 세척 코스를 선택할 때`, `improvement_task=세척 코스 선택과 결과 확인을 돕는 안내 서비스 기획`이다. 제공된 세 리뷰는 모두 적재 위치·식기 조합·긴 손잡이 간섭에 관한 것으로 코스 선택 문제를 직접 입증하지 않는다. 이 요청/자료 불일치는 다음 평가 입력에서 바로잡아야 한다. 원 입력·실패는 역사 근거로 보존한다.

냉장고 원고는 선반 분리 기능이 존재해도 식품 전체 이동이 남는 불편을 구조 개선 가설로 다룬다. 전자레인지 원고는 이미 있는 설정 저장·호출 기능의 단순 재제안을 제외하면서 인지·등록·호출 불편을 해결됐다고 지우지 않고 확인 질문을 반환한다. 향후 세 제품의 corrected case는 이 세 예시 각각에 정렬하고, 특정 정답 트레이·안내 UI를 고정 출력하도록 강제하지 않는다. 식기 입력 정렬 문제만으로 아래 모델 인용·극성·희망 결과 대응 오류를 면책하지 않는다.

## 역할별 대조 판단

### 냉장고 정상

Need 추출은 REVIEW-EVIDENCE-001/002/008/009의 청소·식품 이동 불편을 리뷰 ID로 연결했고, 긍정 원문 006을 신규 불편으로 만들지 않은 점이 맞다. 그러나 원문 007의 정리 표시 이해 차이를 `conflicting`이라고 한 사유는 다른 근거와 실제로 충돌한다는 대조를 제공하지 않는다. 안쪽 식품 찾기(003), 바구니 세척(005), 선반 높이 조절(010)까지 한 청소 상황으로 넓혔으며 각각을 FEATURE-001과 동일하게 비교할 관련성은 입증되지 않았다.

MANUAL-001은 “선반은 분리하여 세척할 수 있습니다. 선반을 분리하기 전에 위의 식품을 모두 옮겨 주세요.”라고 명시하고 FEATURE-001과 양방향 연결된다. 따라서 현재 선반 분리 기능의 문서상 지원과 전체 식품 이동의 잔여 불편은 별개다. 실제 비교 응답은 여덟 Gap 모두 리뷰만 인용하고 MANUAL-001을 빠뜨렸으며 `unsupported/explicit_unsupported`로 분류했다. “선반 분리 방법이 설명서에 명시되어 있지 않아 위치 파악이 어렵습니다.”라는 unresolved도 제공 원문/locator의 존재와 구분하지 못한다. 제공 텍스트가 상세 분해 동작을 전부 설명한다고 확대할 수는 없지만, 현재 기능과 이동 조건을 대조할 자료 자체가 없다는 판정은 맞지 않는다.

검사기는 잘못된 미지원 판정을 승인하지 않아 안전하지만, 원 source에서는 UNSUPPORTED_WITHOUT_MANUAL을 즉시 hold로 분류해 수정 예산을 0회에서 닫았다. 청소 핵심 Need001/002/007/008은 설명서 미확보보다 모델 인용·지원/잔여 불편 구분 오류가 먼저 해결할 문제다. 모든 여덟 Need를 자동으로 충분하다고 바꾸거나 MANUAL-001을 삽입해 자동 승인하는 것은 정당하지 않다.

### 냉장고 조건 변경

변경 조건은 “자동 세척 하드웨어를 필수 전제로 삼지 않는다”이다. 비교는 현재 기능을 supported로 바꾸고 잔여 불편을 남겨 정상보다 지원/잔여 불편 구분 일부가 나아졌다. 다만 여전히 모든 Gap의 설명서 인용이 없었다. 첫 재시도에서 설명서 쪽을 고치면서 리뷰 근거를 누락해 GAP_REVIEW_MISSING이 발생했고, 다음에는 리뷰만 남겨 GAP_MANUAL_MISSING으로 돌아왔다. 원 요청에서 인용 두 종류를 모두 요구하는데도 둘을 동시에 보존하지 못했다.

Need 단계는 008/009를 complaint로 분류했으나 여섯 Need에는 이 두 청소 리뷰가 빠졌다. 결과가 held였기 때문에 completed일 때의 complaint 전체 인용 검사로 이 누락이 드러나지 않았다. 세척 하드웨어 제외를 의미적으로 지킨 후보는 생성되지 않았으므로 조건 준수 성공은 미검증이다. 자동 세척 하드웨어를 제안하지 않았다는 사실만으로 정상 조건 변경 처리에 성공했다고 판정하지 않는다.

### 식기세척기 정상

제공 MANUAL-004는 기본 적재 그림·자동 세척 코스가 존재하며 큰 식기는 회전 날개를 막지 않도록 배치한다고 설명한다. 고객 원문 031/032/033은 적재 안내의 부족·자기 식기 조합 차이·간섭 확인 희망이다. 기존 일반 안내가 제공된다는 기능 지원 사실과 자기 조합 안내가 부족하다는 잔여 불편을 구분할 수 있다. 실제 첫 Need 응답은 서로 명백히 모순하지 않는 리뷰를 conflicting/uncertain으로 표시하면서 그대로 Need로도 포함해 NON_COMPLAINT_AS_NEED로 다시 수행했다. 재추출은 세 리뷰를 complaint로 정리했다.

마지막 비교는 MANUAL-004만 인용하고 원 Need의 리뷰를 모두 빠뜨려 GAP_REVIEW_MISSING을 반복했다. 기본 안내 기능 자체를 모두 unmentioned로 분류한 것은 원문에 기능이 명시된 사실과 맞지 않는다. 특정 큰 접시/냄비 치수와 집별 간섭을 확정하려면 추가 조건이 필요할 수 있지만, 이것이 일반 적재 안내 기능 부재나 안내 서비스 기획 자체의 불가능을 뜻하지 않는다. 별도로 코스 선택 요청을 뒷받침하는 리뷰가 없는 입력 범위 문제를 사용자에게 명확히 돌려줄 필요가 있다.

### 식기세척기 조건 변경

변경 조건은 “사용자의 확인 없이 세척 코스를 자동 변경하지 않는다”이다. 첫 추출의 conflicting/uncertain과 Need 포함 오류, 첫 비교의 설명서 인용 누락은 실재한다. 첫 비교 질문은 원문에 없는 “식기 조합에 따른 세척 코스 자동 조정 기능의 정확성”으로 확대해 확인을 요구했다. 해당 기능이 제공되거나 필요하다는 사실은 이 자료에서 확인되지 않는다.

재추출 뒤 비교는 보류 사유를 남기면서 질문을 모두 비워 HOLD_WITHOUT_QUESTIONS로 다시 수행했다. 마지막 Need 응답은 세 Need에 desired_outcomes=[]를 반환했고, 다시 모든 리뷰를 uncertain이라고 하면서 근거별 해석 대신 일반 지침 문장을 reason으로 복사했다. 결국 VALIDATION_FAILED로 output=null이다. 이 마지막 대응 누락은 자료 부족이 아니라 출력 계약을 지키지 못한 실패다. 검사는 이를 성공으로 저장하지 않았다. 자동 코스 변경 조건의 의미 준수도 후보가 없어 미검증이다.

### 전자레인지 정상

MANUAL-005/FEATURE-005는 설정 저장과 원터치 호출이 이미 있음을 명시한다. 034는 반복 입력, 035는 기능을 몰랐음, 036은 호출 버튼 찾기의 어려움이며 기존 기능 존재와 양립한다. 신규 저장 기능의 단순 재제안은 제외해야 하지만 인지·등록·호출 불편까지 해결됐다고 간주할 수 없다. 실제 Need 응답은 세 불편을 리뷰에 연결했으나 처음에는 희망 결과가 하나뿐이었다. 첫 수정에서 세 Need와 세 희망 결과의 대응을 회복했다. 두 번째 희망 결과가 “설정 저장 기능을 사용하지 못해 불편함”처럼 불편을 반복하는 수준이고 첫 희망 결과를 “자동으로 저장”으로 좁힌 점은 과제보다 특정 해법을 앞당긴다.

후속 비교는 MANUAL-005를 인용하지 않고 035 관련 Gap만 unmentioned로 두었다. 기능 인지 부족은 설명서에 현재 기능이 명시되지 않았다는 뜻이 아니다. “설정 저장 기능이 사용자에게 충분히 안내되지 않았습니다.”는 한 사용자의 몰랐다는 경험에서 전체 안내 효과를 단정한 것으로 제한을 남겨야 한다. 교육 자료·버튼 위치를 확인할 질문은 구체 UI 검토에는 유용할 수 있지만, 명시된 저장 기능 존재와 기존 기능 단순 중복의 대조를 막는 자료 부족으로 모두 처리할 필요는 없다. 실패로 끝나 신규 기능 중복 제외·적절한 질문 반환의 실제 의미 검토는 완료되지 않았다.

### 전자레인지 조건 변경

변경 조건은 “설명서에 이미 있는 자동 데우기를 새 기능이라고 제안하지 않는다”이다. 세 번의 Need 응답 모두 세 Need를 작성하고 Need-001의 희망 결과만 한 개 반환했다. Need-002/003의 대응이 끝까지 없었으며 product_compare에도 도달하지 못했다. 따라서 보류 질문이나 중복 제외가 성공한 사례가 아니다. 이 실패는 원 자료가 모자라서가 아니라 모델 출력의 대응 누락이다. 명시적으로 가진 원 기능은 설정 저장·호출이며, 원문에 없는 모든 자동 데우기 동작을 지원 사실로 확장해선 안 된다.

## 검사와 수정 경로에서 확인한 한계

잘못된 인용·극성/Need 모순·희망 결과 대응·보류 질문 누락을 실제 검사했고 five failed 사례가 각 stage_retry 두 회에서 종료했다. 모델 출력이 외부 도구·모델·자료 권한을 선택한 흔적이나 실제 source 변경은 summary/기록에서 관측하지 않았다. 이는 이번 경계 검사 사실이며 일반적인 prompt injection 방어 성능의 측정값은 아니다.

원 source의 `skill_runner.py:470~472`는 Need/desired_outcome 집합 불일치를 “각 니즈에 대응하는 희망 결과가 필요합니다.”라는 VALIDATION_FAILED로 거부한다. 그러나 `planning_agent.py:473`은 모델 재시도 feedback에 code/stage/details만 넣고 message를 넣지 않는다. 실제 microwave-changed의 두 feedback은 모두 `VALIDATION_FAILED`, `details={}`이며 누락 Need-002/003 ID·기대 대응 개수·원 오류 설명이 없었다. 비교 인용 오류의 feedback도 GAP_MANUAL_MISSING/GAP_REVIEW_MISSING 코드만 있어 어떤 Gap에서 어느 리뷰/설명서 ID를 동시에 보존할지 빠진다. 이 점은 반복 실패를 설명할 수 있는 구체적인 개선 후보이며, 단독 원인이나 개선 효과를 실측했다고 단정하지 않는다.

여섯 기록의 `skill_trace.records`에 실제 관측된 reasoning Skill은 need_extract와 product_compare뿐이다. concept_draft, review_revision, semantic_review, no_candidate_review는 0회이다. 직접 frozen source 조회를 수행한 사실을 evidence_lookup Skill의 호출 증거로 대체하지 않는다. 최대 2회 소비는 관측됐지만 stage_retry와 review_revision이 함께 쓰이는 실모델 경로·다섯 Skill 전체 의미 품질은 이번 6사례로 검증되지 않았다.

원 source의 semantic/no_candidate 검토 진입 조건은 구조 검사 valid + action=accept이다. 구조상 유효한 held 응답은 이 의미 검토에 들어가지 않는다. 예를 들어 설명서가 있는데 없는 것으로 만든 보류 사유, resolved가 아닌 다른 불편으로 전체 실행을 막는 해석을 새 의미 검토로 판정하지 못할 수 있다. 이는 별도 후속 설계/재현 항목이며 이번 인용 누락의 좁은 수정으로 해결됐다고 기록하지 않는다.

## 좁은 수정 후 냉장고 두 실제 실행

원본 6사례는 덮어쓰지 않았다. 좁은 수리 branch `c3d716061fec13ce23773af339d583b475dc7ebb`는 정확한 기존 설명서 원문에서만 인용 누락을 같은 예산으로 모델에 다시 요청하고 ID 자동 추가/자동 승인을 하지 않는 구현·회귀 검사 근거다. PM이 이를 통합한 source **`a748b663d9c371f38b12f0e0ab5eb66ab3f4b877`**의 정상/변경 두 실행은 완료됐으나 둘 다 held이며 후보는 0개다. 원 input hash·dataset·모델 digest·설정은 같고 원 증빙은 별도 `private/runtime/live-intake-a748b663d9c3/`에 있다.

| 사례 | 원 37f 결과 / 호출 / 토큰 | 후속 a748 결과 / 호출 / 토큰 | 후속 판단·수정 |
|---|---|---|---|
| fridge-normal | held / 2 / 11,550 | held / 4 / 26,025 | decision valid=true, violations=[], 내부 수정 1회 |
| fridge-changed | failed / 4 / 22,100 | held / 4 / 23,535 | decision valid=false, SUPPORT_UNKNOWN, 내부 수정 2회 |

후속은 생성 8회, 보고 토큰 49,560이다. 원본 정상/변경의 합계 6회·33,650토큰보다 호출 2회·토큰 15,910이 늘었고 완료 결과가 새로 생기지 않았다. 반복 횟수 1개의 대응 실행이므로 효율 개선률이나 모델 일반 성능을 추정하지 않는다. 실패 타입이 바뀐 것과 정상 상품기획 성공을 구분한다.

정상 최종 응답은 여덟 Gap에 MANUAL-001과 열 리뷰 전부를 일괄 인용했고, 구조 검사상 인용 누락은 사라졌다. 그러나 여덟 Gap의 지원 판정은 여전히 unsupported/explicit_unsupported이다. 선반 분리 기능의 지원과 식품을 옮겨야 한다는 잔여 조건을 혼동했고, “설명서 위치가 명확하지 않아 확인이 어려움”으로 unresolved를 남겼다. 실제 입력 locator에는 page=1, section=선반 분리가 있으며 선반 분리·전체 식품 이동 원문도 있다. 모든 리뷰를 모든 Gap에 넣어 인용 존재 검사만 맞춘 것이 개별 판단의 관련성을 입증하지 않는다. 구조 검사 valid=true인 hold가 의미적으로 올바른 충분성 판단이라는 뜻은 아니다. semantic/no_candidate review와 concept_draft는 여전히 실행되지 않았다.

정상 trace의 재시도 원인은 NON_COMPLAINT_AS_NEED이고 Need 추출부터 다시 수행했다. 두 번째 비교가 구조상 유효한 held가 되어 종료했다. **새 compare_citation_retry 이벤트는 실제 두 후속 기록 모두 0회**다. 인용 요구 prompt가 강화된 source에서 최종 인용 누락이 감소한 관측은 남길 수 있으나, 새 전용 재시도 분기가 이번 실제 실행에서 작동했다고 주장하지 않는다. 그 분기는 별도 89개 격리 회귀 검사에서 검증됐다.

변경은 SUPPORT_BASIS_MISMATCH → GAP_MANUAL_MISSING+SUPPORT_BASIS_MISMATCH → SUPPORT_UNKNOWN 순으로 두 수정 뒤 끝났다. 마지막 모든 Gap에 해당 리뷰와 MANUAL-001을 넣어 최종 인용 누락 자체는 사라졌으나, Gap001을 explicit_unsupported로 하고 나머지를 unmentioned로 남겼다. “식품을 옮기지 않고 청소하도록 설계됐는지 확인할 자료가 없다”는 질문은 이미 명시된 이동 조건을 현재 기능 대조와 잔여 불편으로 읽는 데 실패한 부분이다. 바구니·안쪽 식품 찾기 같은 무관/덜 직접적인 Need에는 추가 원문이 필요할 수 있으므로 모든 보류를 자동으로 해제할 근거도 아니다. “임시 보관 공간이 제공되지 않아 식품 손실 위험이 있습니다”라는 reason은 원문에 없는 손실 위험을 덧붙였다. 제외 조건에 따른 실제 후보와 검토 경로가 없어 변경 준수는 미검증이다.

두 후속 원 출력 SHA256은 정상 `8ec25bdc5d52b1b36a789403cfaf80c5057851929bf47a01f2f821f5136da3d1`, 변경 `00be2951d8ad7339ed691a3dabbcb7a5a157c6b782e68ef9ebb663db02c7c40d`이다. 실제 결과 저장/API/MCP readback은 PM이 별도 검사할 수 있지만 같은 run ID/held 상태 전달 성공이 후보 품질 성공으로 바뀌지는 않는다.

## 다음 의미 품질 검토 기준

다음 실행을 새 원본·source·입력·출력·모델·모든 호출/비용과 연결한 후 아래 기준을 대조한다. 현재 두 실행의 반대 근거는 유지한다.

1. MANUAL-001과 각 원 Need의 리뷰 ID를 동시에 실제 생성 결과가 인용했는가. 시스템이 누락 ID를 채운 것은 아닌가.
2. 선반 분리 기능은 지원됨, 전체 식품 이동 불편은 남음으로 구분하는가. 무관한 Need나 특정 물리적 불가능을 원문 사실로 확대하지 않는가.
3. 명확한 청소 불편은 확인된 자료로 진행하고 실제 미언급·상충·불확실한 비교는 설명 가능한 질문과 보류로 남기는가.
4. 정상은 실제 구체 후보/요구사항/검증 가정 또는 정당한 무후보·보류 판단까지, 변경은 원 제외 조건을 의미 검토까지 전달하는가. 값이 채워졌다는 규칙 검사만으로 판정하지 않는다.
5. 내부 수정 2회가 stage_retry/review_revision 합으로 유지되는가. 원 최초 실패와 두 회 비용을 보존하고 새 source의 실제 결과를 따로 비교했는가.

정렬된 세 예시 새 입력, 성공/보류 각각의 근거 대조, 수정/조건 변경의 전체 의미 경로, 다섯 Skill 실제 연결, 개발과 분리된 평가와 강한 일반 LLM 기준선, 호스트/API/MCP/웹 전체 사용자 흐름은 남아 있다. 이 기록은 R01~R28/E01~E03의 정답 6개나 전체 31요구 완료 판정으로 사용하지 않는다.
