# CORE R9 내부 원문 레코드·조건부 문서·국소 수리

PM [#264](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/264)의 고정 `0e5757bcc5f732220c6b4bd847b0973da98b157f` [CORE-NEXT-01~03](../../../pm-r9/20261008/core-next-actions.json)을 구현 준비→코어 소비/검증→격리 검사로 진행했다. 전체 작업을 PM 원 응답 대기와 묶지 않았다.

## 구현한 경계

- `PublicEvidence(bundle, records)`는 정확한 Unicode 원문 구간·source 역할·주체 anchor·기간 역할/값·추정/희망과 경험 polarity를 검증한다. 실패 레코드만 제외하고 원 후보·정상 이웃·원문/facts를 보존한다. 잘못 태깅한 자연어 의미를 코드가 전부 판정하는 기능은 아니다.
- `summary_projection()`은 typed observation의 실제 polarity 후보만 세고 원문 표현으로 양쪽 요약을 반환한다. 희망/기사 의도 추정은 실제 만족으로 세지 않는다. 원 요약·coverage는 변경하지 않고 별도 private projection에 보존한다. 이 단계는 분류/품질 승인이 아니다.
- 공식 P49 action은 조건·전원 켜기→버튼3초→취소·수치/비교·버전·발췌·공용 적용·참조 장을 묶는다. 정확 SKU/적용 및 완전 절차 검수가 없으므로 상세 실행 안내로 승인하지 않고 전체 원문 참조를 출력한다. 세척조 참조 장의 미취득 세부 절차를 만들지 않는다. 상담을 구매/점검 실행에 종속시키지 않는다.
- 필드→claim 의존성은 해당 자리의 원문 인용·관찰/가정/문서 구분·가정 표시를 검사한다. `PublicPlanner(..., evidence=ledger).repair(..., field_claims=bindings)`와 `repair_public_brief(..., evidence=ledger, field_claims=bindings)`가 기존 최대2 수정 예산에서 검증한다. 미수리 장면과 이전 Problem 이슈는 후속 수리에도 남으며 기존 전체 상태를 의미 승인으로 올리지 않는다.
- opt-in planning source context는 private 후보를 포함하고 기존 native schema는 동일하다. ledger 원 bundle이 바뀌거나 binding이 잘못되면 모델 호출 전에 거절한다. 원본 summaries/coverage/source_facts/건강한 필드/관계는 보존한다. 공개 API는 내부 ledger/의존성/private 요약을 내보내지 않는다.

## 실제 자료와 출력 stub

[candidate-records.json](candidate-records.json)은 수집된 후기752651/853593/800073/645400 및 P49에서 가져온 정확 인용에 태그를 붙인 **검사 출력 stub**이다. 실제 모델 출력·새 고객 후기가 아니다. [artifact-verification.json](artifact-verification.json)의 실제6 출처·문자열/facts 해시·원 bundle SHA를 대조했다. [schema](private-record-schema.json), [요약 후보](candidate-summary-projection.json), [상담 문맥 후보](candidate-consultation-context.json), [조건부 원문 참조](conditional-official-reference.zip)를 제공한다. 의미·분류·상담 전달 승인은 모두 미확인이다.

## 검사

- 코드 고정 `fd06a3edd5f6f0f29f3b5b544c3e77bb8088e432`: 새 실제-source 경계11 + 기존 관련51 = **62 PASS**, [원 수신](check-0.log). [Ruff PASS](check-1.log).
- network=none, read-only, uid65534, 인증 mount0. 실제 모델 호출0, 기존6사례 재채점0. 원 실패/세팅 누락 및 복구는 [수신 문맥](verification-context.json)에 보존했다.
- 주체/시간의 exact span 불일치, 다른 후기 연결, 명시 order anchor 누락, 중복 ID, malformed record, 희망의 경험 polarity, 문서/고객 혼선, 역순 절차, 원 bundle 변경, 가정 표시 누락, 두 항목 국소 수리 후 잔여 장면·Problem 보존과 budget 재사용 거절을 확인했다.

## PM 인계 및 정확한 다음 행동

1. PM의 `public_generation_stage`는 기존 discover/plan의 완전한 schema만 신뢰한다. CORE가 record를 새 native envelope에 단독 추가하면 item-local recovery가 사라진다. PM 어댑터 파일은 수정하지 않았다. **같은 기존 discover/plan 호출에서** 위 record schema를 반환하도록 trusted envelope/recovery와 private runtime 저장을 함께 연결해야 한다. 추가 critic/재생/예산 초기화는 필요 없다.
2. 새 native record/field binding이 저장되면 CORE는 첫 받은 일부부터 quote/span·source 역할·국소 수리/잔존 이슈를 소비한다. 그때 실제 summary 투영 적용 경계를 PM/API와 연결하고 원 summary/coverage/raw/usage를 유지한다. 현재 별도 projection을 실제 요약 수정 완료로 표현하지 않는다.
3. 기존 normal `run-1f83d846191941aea21153897b944ec1` / condition `run-754268c6b0cb41bba50c5b8d713332d9`의 원 응답·저장 출력·failure/usage와 동일 HTTP/MCP 자료는 별도 인수한다. 새로운 모델 실행은 이 PR에 포함하지 않는다.

검사·준비 완료와 실제 모델 의미 개선·통합·PM 인수·전체 Done은 분리한다. CF1/CF2/CF3 내부 구현/검사는 진행했고 native 생성/저장·실제 효과는 남아 있다.
