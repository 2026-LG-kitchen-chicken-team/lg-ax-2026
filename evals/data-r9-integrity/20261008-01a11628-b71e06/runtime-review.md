# R9 실제 수신·운영 증빙 대조

기록 ID: DATA-R9-RUNTIME-20261008-01a11628-b71e06 · 신진하/ginaginaring.

게시 후 확인: PR265와 PR266이 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`에 병합됐다. 이 감사가 받은19파일 및 PR266 제출12파일 모두 원바이트가 같다. [통합 관찰](integration-observation.json)에 고정했다. 아래 이전 조회의 open/미병합 상태는 당시 기록으로 유지하며 운영 export 수신·승인은 여전히 별도다.

기준 main **6aa300a6bb0ba07f7812bf96297da834a61cbd33** (PR264 병합). PR266의 입력 검수 pin `dc0ccc05916c637b2e0c2cc268a061dfa655c0b7` 이후 변경을 읽었다. 이전 감사의50개 Git blob 대조 항목은 현재 main에서도 원바이트가 같아 238건/184 Source/141 후기/인용19 검사를 재실행하지 않았다.

## 확보한 범위

| 구분 | 직접 확인 | 한계 |
|---|---|---|
| 파일 준비 | PR262/264 통합, R9 원3묶음·참고5, CLI 등록10개 선언 | 새 김치/광파2묶음은 별도 입력. 원184/141에 합치지 않음 |
| DATA 실제 수신 | PR265 고정 `f1e0f587dd99813f54490471e9ac0fe64e636cf3`의 CORE guide ZIP8024bytes 및 JSON/manifest 등6파일을 Git blob으로 읽음 | CORE 생성기 산출물 수신. 운영 서버에서 직접 받은 envelope가 아님 |
| 출력 bytes 대조 | ZIP4개 파일의 목록/크기/SHA 일치. JSON의5 Source 전체/순서가 참고 bundle과 같음 | 모델 기획 결과나 실제 DB 저장을 뜻하지 않음 |
| 운영 적용 보고 | PM E057에서 API/MCP/브라우저 guide 동등·정상/조건 저장·같은 DB 재시작 후 public 동일을 보고 | 원 HTTP/MCP·DB row·restart 쌍은 이 감사에 미수신 |
| 의미 검수 | 기존5case와 최신 정상/조건2case의 고정 보고·SHA·parent 관계·6 Source pin 일관성 확인 | PlanningBrief/raw response/usage 원파일 미수신. 의미 품질 승인 false 유지 |
| PM 승인 | PR262·PR264 실제 merged. PR263도 PR264로 통합 확인 | 본 DATA 운영 감사·#13 부모 Done·독립 의미 승인과 별도 |

**판정: 받은 아카이브/보고 pin 대조 PASS, 운영 무결성 독립 검수 UNCONFIRMED.** PM의 실제 실행 보고를 부정하지 않는다. 수신하지 않은 운영 원응답을 검증했다고 기록하지 않는다.

## CORE 안내서 원출력

| 파일 | bytes | SHA256 |
|---|---:|---|
| ZIP | 8024 | e6baebf957e96d82736d5b136a797edf4a2c5eea96ce5990dc4767e082d13443 |
| HTML | 11256 | 7de2567f66101e12496475009c6634cbbe57efdb54332a93c377389b6a8804d6 |
| Markdown | 8481 | 96aefc393fe52f853f9eef04b0d676297591ed102c9a9be21cde20eb84f18673 |
| JSON | 15571 | c47cea5c9ae77e30a33788fc0cacf497e36692ce51ef36ee72ee637c006dd12d |
| intake JSON | 2471 | 9be62367e3e9d8a04c9726a576abd580a708018091c1f2a74234248fbc50052b |

실제 받은 HTML SHA/크기가 PM E057의 API/MCP/브라우저 보고 값과 같다. 이 상관은 확인됐다. 그러나 CORE intake는 `same_live_API_MCP_verified:false`이고 실제 전송 envelope가 없으므로 DATA의 운영 API/MCP 동등 판정으로 승격하지 않는다. 새 안내서를 다시 생성하거나 서버를 호출하지 않았다.

## 저장 run·사용량

[7건 수신 장부](run-receipt-ledger.json)에 run ID, 보고된 public SHA, revision/parent, 보고 파일 SHA, 원출력·사용량·DB·restart 수신 여부를 보존했다.

- 최신 정상: `run-1f83d846191941aea21153897b944ec1`, SHA `4e84728d07aedff38cc30c26f839abce2ae54719e341954f27dff353c79ed3d2`.
- 최신 조건변경: `run-754268c6b0cb41bba50c5b8d713332d9`, SHA `0fd3a2047a7fd884af1c89e6d87ef46e83a446f5b277d18c838876bf63427c1d`; 이전 brief `brief-fe7412d6635c4822988f8d42ae6acddc`.
- 최신 두 실행은 보고상 같은27B digest·각2호출/수리0이다. 조건변경 보고의 생성 토큰 [619,1729]만 그대로 기록했다. 입력 token·원 usage 미수신을0으로 만들지 않았다.
- 기존5case의 성공/차단/출력 잘림/의미 오류 이력과 원 보고 SHA `9bbc412a06002c53b4cf3935442a5a8488b869c867167b8d3862b51d223d157f`는 유지됐다.
- CORE의6 Source 본문 SHA/판본/null이 현재 식기세척기 bundle에 일치하고 최신 보고의 Source ID 집합도 같다. 실제 run snapshot의 selected_source_ids/facts 전체는 원출력 수령 뒤 비교한다.

## 실제 원증빙 수신 범위

고정 main/관련 PR 산출물, 현재 workspace의 알려진 정상·조건 run ID 포함 JSON, `*research.sqlite3` 파일을 조회했다. 발견된 JSON은 큐/검수 보고/별도 DATA spec이었다. 유일하게 찾은 research SQLite는 10/8 02:06의 **PR254/ef29aa8 격리 검사** 파일이며 research_runs가0행이다. 원 보고는 production_server_changed=false, model_adapter_configured=false다. 이를 R9 실제 저장 DB로 쓰지 않는다.

PR226/227의 과거 격리 HTTP/재시작51쌍 독립 결과와 PR259의 운영 export 요구는 재사용한다. 과거 pin·원 raw wire/SQLite 미수신 한계가 현재 R9 운영 성공으로 바뀌지 않는다. PM PC/원격 비공개 저장소까지 검색한 것이 아니며, 그곳에 파일이 없다고 주장하지 않는다.

## 남은 인수

[정확한 export 항목](required-exports.json)은 **기존에 보존된 증거**의 제공 요청 명세다. 새 모델 실행·서버 재시작 요청이 아니다.

1. 운영 소비 commit·DB 식별자·bundle ID/SHA·모델 pin과 캡처 시각을 묶는 manifest.
2. 실제 bundle list/GET, 공식 안내서 POST, stdio MCP tool 인수·응답·원 bytes/SHA/size. HTTP와 MCP 직렬화 바이트가 다를 수 있으므로 wire SHA와 해석된 payload 동등을 구분.
3. 최신 정상/조건의 저장 public JSON 및 research_runs/research_attempts 관련 행. 원 실패/usage가 보존된 위치와 접근 범위를 명시.
4. 같은 DB의 기존 재시작 전후 raw GET/MCP·논리 행 snapshot·재시작 receipt. DB 파일 SHA와 논리 행 hash를 구분.
5. 인수 가능한 범위에 대한 PM 명시 확인. 자료 준비·실제수신·운영·의미검수·승인 각각 유지.

PR264에서 D4의 오래된 미실행 follow_up이 정정됐다. PR266의 당시 관찰은 보존하고 이 항목을 현재 미해결로 남기지 않는다. 새 김치/광파 입력 독립검수와 다른 DATA 창의 source-semantic 작업은 이번 범위로 인수하지 않았다.

## 자기 검수·재현

[artifact-receipt.json](artifact-receipt.json)의 commit/path를 `git show`로 읽어 `.scratch/input/{staged_path}`에 배치한다. [audit_exports.py](audit_exports.py)를 [execution.json](execution.json)의 zero-auth/network=none Docker에서 `python -B /audit.py /input /receipt.json /out`으로 실행했다. 입력과 스크립트는 읽기 전용이며 출력만 별도 폴더다.

[48개 대조 결과](export-checks.json) PASS. 기존 테스트34·12·WEB7을 새로 실행하지 않았다. 새 모델/OCR/운영 HTTP/DB 변경/서버 시작·재시작/자동화 ON은0이다. 원자료/생산 코드/공통 계약/공유 README 변경0. 두 개인 고유 기록과 전용 evals만 추가한다.
