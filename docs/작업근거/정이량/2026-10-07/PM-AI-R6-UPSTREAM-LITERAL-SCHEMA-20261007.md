# PM 보조 AI — R6 upstream 판단 인용의 native schema 고정 준비

- 수행자: 정이량 PM의 보조 AI. 황대겸의 구현·기록을 대신하지 않는다.
- 기준 source: `1f25e547f46ef155798fbc27f35aa2c7098ae912`. 새 live 호출·배포·자동화·외부 게시0.
- 범위: CORE의 upstream native JSON schema와 관련 회귀. 기존 canonical 검증·의미 통과 기준·공유 수정2회·24000문자/45000UTF8바이트·ctx16384/output8192 정책은 변경하지 않는다.

## 실제 실패와 준비 변경

정상1 합성10 입력의 고정 실험은 완전 응답6회/47202토큰 뒤 재검수 요청20에서 남은17798토큰이 dispatch 전 예약24576보다 작아 중단됐다. 신규불명0, 기존 보수적259840을 유지해 누적307042다. API 최종 run/semantic 품질 승인은 없다. 전송의 일반 OFF 문구를 실제 운영 OFF나 새 IncompleteRead로 해석하지 않는다.

의미 검수 응답14는 Need9·Gap9를 모두consistent, 후보 기준12를 모두satisfied로 선언했다. 그러나 Need9의 judgement_quote가 해당 Need pain/situation이 아닌 리뷰 원문이어서 canonical의 첫 NEED001 literal 검사가 올바르게 거절했다. Gap004에는 연결 리뷰 RE004도 빠졌다. 다음 review_revision 응답17은 Need/Outcome/Gap/각 평가/후보의7개 부분을 그대로 반환하면서10575토큰을 사용했다. 이 수정 경로의 효율 개선은 별도 제안이며 이번 작은 패치에서 바꾸지 않는다.

`literal_choices=True, include_upstream=True`의 native schema에 entity_kind/entity_id별 판단 원문 전체 필드 선택을 추가한다. Need pain/situation, Gap remaining_pain 또는 해당 gap_assessments.reason에 바인딩하며 resolved의 빈 remaining_pain은 빈 인용 허용으로 바꾸지 않는다. 기존 semantic native의 evidence_id/원문 전체 선택 schema를 upstream source_quotes에도 사용한다. 의미 verdict/reason은 모델이 계속 판단하며 source의 의미 관련성이나 근거를 코드가 대신 작성하지 않는다.

기존 literal_choices=False 경로와 canonical substring 검증은 그대로다. 공개 계약·판단 출력 shape·모델 설정·시행 순서·budget 정책도 그대로다. 새 schema의 선택은 복사 형식만 제한한다. 문서 존재를 발견성 해결로 읽은 GAP004, 선반 매뉴얼을 바구니 지원으로 읽은 GAP005, RE008의 욕구에 전체이동 경험을 추가한 NEED007의 원 의미 FAIL은 별개로 보존한다. 이 패치를 실제 의미 품질 해결로 표시하지 않는다.

## 원바이트와 회귀 준비

- [고정 반례](../../../../evals/pm-prototype/20261007/r6-core/normal-1f25-upstream-literal-counterexample.json) SHA256 `3ca94273f3829df13899a677608c92467305d6f47afbe80da3fde4fa8021a00b`. 원 request14/response14/request17 파일 SHA와 provider wire/raw response SHA를 포함한다.
- request17의 previous/previous_declarations에서 재구성한 검토 대상 output SHA는 응답14의 `1b5662a54e8c5771473a99184922f00e1efec3f321e2dccaf235216f386255a8`와 정확히 같다. payload도 응답14의 `6ecdf80f37318948b7c99e90ccb500ba25fbdec3700bfdda87db07a99965b601`과 같다. 원 모델 선언·원 raw·ledger는 수정하지 않았다.
- 새5회귀는 실제18개 검수 중 Need9 인용 오류의 native 거절, 다른 entity 인용 거절, resolved의 실제 reason/빈 인용, source ID/quote 바인딩, 형식 PASS와 원 의미 FAIL 분리를 확인하도록 준비했다.
- 기존 upstream 실제 formatted prompt/모든 선언의 손실 없는 복원·공유 수정2회·원3 replay·semantic/recorded 회귀를 같은 고정 zero-auth/networknone/readonly source Docker에서 검사할 예정이다. 부모의 소스/validator 검토 전 제품 검사 실행0이며 검사를 통과했다고 미리 기록하지 않는다.

독립 메타데이터 진단은 별도 private scratch `r6-normal-1f25-canonical-routing-review-v2.json`, SHA256 `26b9891a0e61d250fa58cc3fa72372c4997da697f05366dd9b11d3b219a076d3`로 고정했다. 본인의 메타데이터 대조43항목 PASS는 제품 코드 테스트나 새 의미 품질 인수가 아니다. 자기 수정의 독립 소스 검수와 실제 격리 회귀 인수는 부모 PM/별도 AI가 맡는다.

## 첫 격리 검사와 wire 압축 보완

원 draft `80cf8b259db034e97fe5a0273335794eae43a67b`의 고정 Docker186검사 중 기존 실제 formatted prompt 준비1개가 `schema_too_large`로 실패했다. Ruff7은 PASS, source_changed[]/networknone/authnone/모델0이었다. 원 영수증 `private/runtime/pm-r6-upstream-core-a6ca3ae7305542ccadba743b13174be5/receipt.json`과 실패 로그는 보존한다. 기존 schema UTF8바이트 한도16384를 변경하지 않는다.

세 평가 배열에 반복한 evidence_id/원문 전체의 동일 schema를 한 local `$defs/literal_source_quote`와 세 `$ref`로 묶는 후속 수정만 준비했다. entity별 판단 원문 enum·18coverage·실제 source ID/text·모든 verdict/reason·canonical guard는 유지한다. 기존 native 단계의 계약에도 local `$defs/$ref`가 사용되며 원 모델 응답은 완전 수신됐지만, 이 새 schema의 실모델 효과를 검증했다고 표시하지 않는다. 실제1f25 정상9Need·9Gap·3후보에서 직렬화 schema≤16384와 native preparation guard, 한 source definition의 모든 원문 쌍·세 reference를 검증하는6번째 회귀를 추가했다. 부모가 후속 정확 source를 읽기 전 새 검사 실행0이며 의미 FAIL 세 건은 미해결이다.
