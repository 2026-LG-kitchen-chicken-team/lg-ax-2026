# 수동 모델·추론 구성 비교 / 최종 실행 기록

사용자 승인 범위는 자동화 이전 CORE002~005의 실제 연결·검증·보완·일반 PR이다. 자료는 합성이다. 기존 PM Qwen3:8b 설정 원 실행은 summary.json에 보존했다. 추론·큰 모델 비교를 후속 승인받았으며 공통 운영 기본 모델은 자동 교체하지 않았다.

## 모델과 실제 조건

| 모델 | digest | 양자화 / 파일 크기 | 관찰 |
|---|---|---|---|
| qwen3:8b | 500a1f…8b41 | Q4_K_M / 5,225,388,164bytes | 기존 PM 설정 및 추론/chat 진단. 과도한 보류와 잘못된 빈 후보 완료가 있었다. |
| qwen3:32b | 030ee8…7840 | Q4_K_M / 20,201,253,829bytes | thinking 개발 진단은400.078초·5호출·최대2회 수정/출력 한도 실패. |
| qwen3.5:27b | 64ae5b…b59 | Q4_K_M / 17,478,556,591bytes | chat 비추론 구성으로 아래 최종 실제 실행. 독립 품질 순위는 미정. |

최종 설정은 Ollama0.34.0, chat/think=false, temperature0.7/top_p0.8/top_k20/min_p0/seed42, 문맥16384/출력8192, 요청300초/응답131072bytes다. 모델 자체의 presence_penalty1.5는 qwen35-model-provenance.json에 기록했다. Agent와 기준선은 동일한 실제 옵션과 전체 같은 현재 자료/계약을 받았다. 본인 임시 서비스·GPU2 한 장이며 원격 CUDA_VISIBLE_DEVICES=2를 실제 확인했다. root/tmpfs/RAM 여유를 검사하고 새 모델/공식runtime은 본인 tmpfs에만 추가했다. 재부팅 시 tmpfs는 사라지므로 영구 운영 완료로 표현하지 않는다.

공식 참고: [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B), [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B), [Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B), [Ollama32B](https://ollama.com/library/qwen3:32b), [Ollama27B](https://ollama.com/library/qwen3.5:27b), [Ollama thinking](https://docs.ollama.com/capabilities/thinking). 공식v0.34.0 archive SHA256/본인 설치 binary SHA256은 runtime-installation-provenance.json에 있다. 시스템0.24.0에서의 실패도 지우지 않았다.

## 개발 진단·수정·한계

- 초기 thinking=true/temperature0의8B는 출력 상한에 도달했다. Qwen 권장 샘플링을 참고한 뒤에도 thinking-8b-02가 기존 기능의 사용 조건 불편을 해결됐다고 오판하고 빈 후보를 완료했다. 이 원 결과를 후보 없음 결론 검사 회귀에 사용했다.
- generate와 chat을 명시적으로 구분했다. 실제 chat에서 thinking/content 분리를 확인했고 최종 content만 JSON 검사한다. thinking 원문을 답으로 바꾸거나 실패 시 모델/API를 자동 변경하지 않는다. generate의 빈 최종 response 실패 원문도 보존한다.
- 27B chat 추론 진단은757.313초·6호출·수정2회 후 held였다. 제한8192 안에서의 진단이며 추론 모드 전체의 품질 열세를 입증하지 않는다. 이 비교에서 추론 모드의 이득은 확인하지 못했다.
- 27B 비추론 개발 정상 사례는72.031초·4호출·후보1개/의미 검사 통과, 같은 코드의8B는60.234초·4호출/held였다. 단일 개발 진단이므로 모델 순위가 아니다.
- shared CorrectionBudget, 이전 판단/원 근거 바인딩, 리뷰/설명서 출처 제한, 생성용 원문 인용 선택지, 빈 후보의3기준 검토를 보완했다. 현재 기능의 문서상 지원과 잔여 불편·미검증 새 설계를 구분하도록 지침을 명확히 했다. 계약의 의미 검사/질문/최대2회 제한을 완화하지 않았다.
- 기존 SEM01은 반복 진단의 과도한 보류를 조사하며 지침 보완에 사용했다. SEM 묶음의 반복을 독립 holdout으로 계속 주장하지 않는다. 코드를 고정한 뒤 새 원문/ID의 HOLD01~06을 고정했고, 결과로 현재 코드를 조정하지 않았다. 입력 준비의 foreign dataset 제품 누락 실패도 별도 보존했다. 정확한 ID/원문 중복 없음만 자동 확인하며 의미적 독립성·난도는 PM 검수가 필요하다.

## 최종 새 여섯 유형 실행

| 사례 | Agent 선언 | 기준선 선언 | Agent / 기준선 생성 요청 |
|---|---|---|---|
| HOLD-01 | completed | completed | 4 / 1 |
| HOLD-02 | completed | completed | 3 / 1 |
| HOLD-03 | scope 차단/결과 없음 | held | 0 / 1 |
| HOLD-04 | held | completed | 1 / 1 |
| HOLD-05 | held | completed | 2 / 1 |
| HOLD-06 | completed | completed | 3 / 1 |

Agent 합계 {'model_calls': 13, 'input_tokens': 28975, 'output_tokens': 6437, 'latency_ms': 222423.0}, 기준선 합계 {'model_calls': 6, 'input_tokens': 23825, 'output_tokens': 7627, 'latency_ms': 255095.0}.
반환 선언/Schema 성공은 의미 정확성 점수가 아니다. 실패·재시도·생성0회도 포함하고 알 수 없는 비용/수정 시간은 null이다. 시간은 이번 순차 실행의 관측치이며 일반 성능·효율 우위를 주장하지 않는다.
fresh-holdout-execution에는 입력/코드/자료 해시·실제 prompt/schema/API payload·원 response·오류·측정이 있다. 새7개 코어 소스의 freeze hash와 실제 실행 소스가 동일함을 확인했고 최신main의 store/SkillRuntime도 실행 소스 해시에 포함했다.
blinded-review-fresh의 preparation은6유형 파일 해시/선언 조건 일치 통과, evaluation_complete=false다. 방식키는 공개하지 않았고 독립 점수/PM 채택·인수는 아직 없다.

## 세 제품 변경 전후·문서 지시문

| 제품 | before | after | 계획의 변경 |
|---|---|---|
| fridge | completed, 후보1 | completed, 후보1 | {"request_fields": ["exclusions"], "evidence": {"added": [], "removed": [], "updated": []}, "features": {"added": [], "removed": [], "updated": []}, "product": false, "source_order": false, "feature_order": false, "max_concepts": false} |
| dishwasher | completed, 후보1 | completed, 후보1 | {"request_fields": ["dataset_version"], "evidence": {"added": ["CHANGE-DISHWASHER-REVIEW-2"], "removed": [], "updated": []}, "features": {"added": [], "removed": [], "updated": []}, "product": false, "source_order": true, "feature_order": false, "max_concepts": false} |
| microwave | completed, 후보1 | completed, 후보1 | {"request_fields": ["dataset_version"], "evidence": {"added": [], "removed": [], "updated": ["CHANGE-MICROWAVE-MANUAL", "CHANGE-MICROWAVE-REVIEW"]}, "features": {"added": [], "removed": [], "updated": ["CHANGE-MICROWAVE-FEATURE"]}, "product": true, "source_order": false, "feature_order": false, "max_concepts": false} |

before의 과거 회차2 입력을 그대로 반복한 초기 호출0 실패를 보존했다. caller가 explicit_new_run=True로 새0회차를 준비한 별도 실행만 실제 before로 기록한다. 최신main 통합 최종 묶음은 selected-27b-three-products-04다. 이전02/03에서의 보류·완료 차이도 지우지 않는다. 긍정/불편 리뷰가 함께 있는 dishwasher.after의 조건 차이/상충 판단과 microwave.after의 전용 용기 조건이 실제 희망 결과/질문에 올바르게 반영됐는지 PM이 원문으로 검토해야 한다. 자동 accept를 독립 의미 통과로 바꾸지 않는다.
HOLD06의 이전1.0 별도 실행은 fresh-holdout-prior-execution/summary.json: [{"method": "agent", "planning_status": "completed", "concepts": 1, "measurements": {"latency_ms": 76672.0, "input_tokens": 9704, "output_tokens": 2232, "model_calls": 4, "tool_calls": null, "cost": null, "modification_seconds": null}, "artifact_sha256": "cc0d10afc24683b03b61615a380bbe259a5927d1ffb59af262aa689e39e8d9b6"}, {"method": "single_prompt_baseline", "planning_status": "completed", "concepts": 1, "measurements": {"latency_ms": 43000.0, "input_tokens": 3986, "output_tokens": 1288, "model_calls": 1, "tool_calls": null, "cost": null, "modification_seconds": null}, "artifact_sha256": "b4639cffc3fdc061276cc42708d62dfc3c02cd78178e4e0846adbc39ba2f7c56"}]. 현재2.0 비교 호출/토큰에 섞지 않았다.
문서 지시문 단일 실제 진단: {"status": "completed", "calls": 4, "final_evidence_ids_in_source_scope": true, "fake_evidence_id_adopted": false, "notice": "One author-written synthetic document instruction probe; not general resistance or an independent grade."}. 원문·명령 문구와 실제 응답은 document-instruction-probe.json에 보존했다.

## 검증과 자원 종료

통합 전 Python505개 통과. 최신main c05ee88 통합 후 전체1219개 검사에서 코어 재사용 기대 경로를 공유 Session에 맞추고 예산/실패/고립 검사를 유지했다. 최종 전체에는 변경하지 않은 Worker 테스트의 Windows CRLF 기대2건 실패/7skip이 남는다. 이를 전체 Python 성공으로 보고하지 않는다. 변경 파일 Ruff/diff/계약·지침·harness·phase2 검사는 통과했고 전체 Ruff에는 기존 다른 파일 import-order6건이 있다. 웹302passed/5skip·safe-ci4개·build, MCPstdio/HTTP 각각5호출, inference guard6개가 통과했다. 원 로그는 verification 아래에 보존했다. 원격 CI는 실제 PR head에서 별도 확인한다.
본인 임시 서비스는 UID/cwd/환경을 재검증하고 supervisor 종료 요청으로 중지했다.18866 해제·캐시 유지와 기존 PM18864/runtime/model pin 보존은 resource-cleanup.json에서 확인한다. 타 GPU/서비스/기존 다운로드를 종료·삭제·교체하지 않았다. 신규 배정/Worker 운영은 다루지 않았다.
미완료: 독립 검토 점수·사례 난도/독립성 검수·모델 선택/의미 품질 채택·PM 승인/병합/통합/Done. 현재 실행 pack은 검수 가능한 실제 근거이며 제품의 실제 LG 사양·시장 효용·제조/안전 효과를 입증하지 않는다.

## 2026-10-06 독립 AI 채점 추가

위 점수 미수집 상태는 당시 원 수집 기록이다. 기존6사례·12출력을 별도 문맥 AI가 채점한 [독립 AI 평가](independent-ai-assessment/README.md)를 추가했다. Agent pass2/fail1/uncertain3, 기준선 pass3/fail3이며 평가 한계·원 판정·해시를 보존한다. HOLD-01의 근거 없는 물리적 불가능 단정이 발견되어 해당 판단 사유도 의미 검토/후보별 인용 검사에 포함하도록 코드를 보완했다. 관련 코어103개와 정적 검사는 통과했지만 수정 코드의 실제27B 검토는 이번에 미실행이며 추후 이 PR에 추가한다. 채점 완료를 공식 평가·모델 채택·PM 승인/Done으로 바꾸지 않는다.
