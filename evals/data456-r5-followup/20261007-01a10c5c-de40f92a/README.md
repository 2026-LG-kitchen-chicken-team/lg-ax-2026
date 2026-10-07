# R5 입력 전송·날짜/토픽 추가 근거와 남은 인수 조건

2026-10-07 KST, 사용자 “남은작업 실행하자” 후속. [PR226](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/226)은 [PM 부분 승인](prior-PR226-PM-intake.json)·실제 병합을 확인했다. 이번 검사는 main `15c3529580a067c9b869af8b049b637280e912f9`의 새 고유 폴더이며 기존 입력·답안·결과·제품 코드·README를 변경하지 않는다.

| 항목 | 새로 수행한 범위 | 실제 완료에 남은 조건 |
|---|---|---|
| 독립 평가자료 | input-only ZIP의 7입력 스키마 확인. 6입력의 Agent 첫 need_extract와 기준선 전체 프롬프트가 generate/chat 클라이언트 POST에 요청·제품·기능·원문·스키마/설정 그대로 도달. 1입력은 SOURCE_SCOPE_MISMATCH로 양쪽 공통 호스트 gate에서 전송 전 보류. 513검사 PASS | Gold·독립성·최종 채점자·양쪽 PC가 접근할 승인 경로·CORE 수신. 실제 모델 서버/정확 tokenizer의 전체 입력 수신·문맥 적합, 후속 Agent 단계·실제 생성/채점 |
| 후기 동향 | 추가15페이지의 구매일149건을 같은 고정 ID/날짜에 연결, row MD 불일치8 보존. 제품 상세3페이지의 datePublished9건을 원문 NFKC/공백 정규화 hash로 연결(원UTF8 hash 직접 일치5). 공식 vendor AI 요약의 후보 주제명7 확보. 208검사 PASS | datePublished9 값은 모두 UI 구매일과 동일. 게시일 의미는 별도 확인 전 미확인으로 유지. 토픽 이름과 개별 후기 라벨/Gold는 다르며 PM 승인 필요. 월별 분모0, 토픽 분자·시장비율 null |
| 등록·조회 | 원 PR226 자체 HTTP109/584·DB 수신증의 PM 부분 인수·병합 확인. 저장/조회 소비 코드의 8ec→15c 바이트 대조 | 새 R5 운영 origin/source·DB record·metadata/original/evidence/scoped-search의 before/after·실제 restart 수신증 및 운영 PM 인수 미수신 |

[클라이언트 전송 원검수](input-transport-audit.json) · [14행 hash 대조](input-transport-matrix.csv) · [실행 경계/명령](input-transport-execution.json). HTTPX **in-memory fixture**만 사용하고 model POST 직전에 중단했다. 실제 모델 생성·답변·점수0이다. `audit-fixture:no-generation`/가짜 digest와 context16384/output2048은 검사 설정이고 실제 모델 권장값·PM 호출 승인·토큰 적합성 증거가 아니다. 기준선은 기존 [강한 프롬프트](../../phase2/baseline-prompt.md)의 전체 입력/자료를 채우고 같은 native format에 공통 출력 schema를 제공했다. SDK guard가 글자·UTF8 초과를 조용히 자르지 않고 wire 전 거절하는 반례도 확인했다.

원 ZIP은 producer head d5d33c46, rawSHA e73d3393ad43e0bb9cf5f19944cc6c23c3fa69c72a1a140d6d680037e89ffaa8이다. 새 validator에는 input-only ZIP만 바이트 고정 마운트했고 내부7입력을 **프로그램이 처리**했다. 입력/답안 본문·ZIP은 공개하지 않고 reviewer-only/Gold는 마운트하거나 읽지 않았다. 이 개발 대화를 최종 독립 채점자로 지정하지 않으며 위 처리·개발 노출 범위도 PM이 독립성 승인 시 검토한다. Source scope 보류를 고치거나 의미 Gold를 만들어 넣지 않았다.

[공식 후기 UI 관찰](public-ui-date-topic-observations.json) · [브라우저 전사 hash](browser-observation-binding.json) · [제품 페이지 JSON-LD](pdp-structured-date-observations.json) · [149행/9본문 연결](public-observation-audit.json). 후기 팝업에는 게시일/time/JSON-LD 표시가 없었고 날짜 라벨은 구매 일자였다. 제품 상세의 datePublished와 UI 구매일이 같다는 것은 관찰 사실이다. 이를 독립적인 실제 게시일 근거로 채택하지 않은 것은 날짜 의미 미확인을 보존하는 검수 판단이다. LG의 오류나 전체238건의 날짜 부재를 확정하지 않는다. 주제명은 vendor AI summary heading이며 각 후기의 확정 라벨/시장 분자는 아니다. 작성자·가구정보·연락처·원 본문·미디어는 내보내지 않았다.

[Git/작업/실행 source89개](Git-working-execution-source-binding.json) · [저장 소비 코드 대조](storage-consumer-source-bridge.json) · [검수 요약](validation-summary.json) · [최종 lint/관찰 검사](final-source-lint-and-observation-checks.json). 이전1f25 실행과 최신15c 재검사를 구분한다. 계약51정의/5모델/36합성리뷰/3요청·AGENTS/CLAUDE·문서 연결은 [이전 gate](earlier-contract-rules-navigation-checks.json)의 정확 버전으로 유지하며, 현재 관련 코드/규정 바이트 대조를 별도로 남겼다. 전체 제품 test suite 재실행이나 운영 배포로 표시하지 않는다.

재현은 같은 zero-auth/network-none/UID1000/read-only 실행 환경에서 `python evals/data456-r5-followup/20261007-01a10c5c-de40f92a/audit_input_transport.py --archive _private_audit/input-only.zip --archive-sha256 e73d3393ad43e0bb9cf5f19944cc6c23c3fa69c72a1a140d6d680037e89ffaa8`, `python evals/data456-r5-followup/20261007-01a10c5c-de40f92a/audit_public_observations.py`이다. input-only ZIP은 Git에 없고 승인된 로컬 validator resource로만 제공해야 한다. 실행 source는 Git manifest와 일치해야 한다. 실제 서버·credentials·Gold를 사용하지 않는다.

[원 실패·복구 이력](execution-history/resolutions.json)을 보존했다. 유료 모델/OCR·신규 설치/다운로드0, 자동화OFF, 운영 서비스 변경/재시작0이다. 공개 정상 UI 방문만 수행했다. 사용자는 별도 인계를 받지 않았다고 답했다. [구체 인수 조건](remaining-release-gates.json)의 Gold/최종 채점/경로·게시일/토픽 정책·운영 캡처는 PM/해당 producer의 다음 입력이며 이 준비·부분 검수로 부모 Done을 만들지 않는다.
