# #14 독립 보존 개선·연결 fixture·누락 근거 등록안

사용자 지시로 PM 정이량과 #12를 우선하고, #12의 기존 실행 예약이 정상 해제된 뒤 별도 예약에서 세 작업을 수행했다. 이 결과는 준비/fixture 범위이며 #13 실제 세 제품 문서 처리·실모델/독립 평가·#14 전체 완료가 아니다.

## 결과

| 작업 | 이번 완료 범위 | 실제 적용/통합 |
|---|---|---|
| 결과 보존 코드 개선 | 스크립트4개의 검토용 수정 소스/patch, 보존시험10 PASS | PM 원래 scripts 경로 인수 전이며 활성 코드 변경0 |
| 연결 사례 검사 | 고정 main의 실제 ASGI evidence handler와 소비자/합성 provenance fixture20 PASS, 기존 helper17 PASS | 실제 문서 등록/파싱·Qwen·BGE/Paddle 호출0 |
| 누락 근거 등록안 | 6개 정확한 페이지/문자 범위·원문/문서 hash·조건 준비 및 유일 범위 검사 | 제안만; API 등록0·현재 plan/gold 수정0 |

최종47시험 PASS, 새 준비 산출물188검사 PASS. 첫47시험 중 fixture의 `locator.line` 오사용1건은 원 소스와 attempt-1에 보존했고 스키마의 `row`로 수정한 별도 복사본의 attempt-2에서 재검사했다. 과거 공개 산출물75개의 바이트는 같았다. Ruff는 Windows mount 실행비트 EXE002 진단 뒤 같은 소스 bytes의 Linux 복사본0644에서6파일 PASS; 규칙을 끄지 않았다.

## 보존 개선

`preservation.patch`와 `proposed-source.json`은 기존 PR131의 source-review 원본에 대한4파일 수정이다. `scripts/prepare_data003_benchmark.py`는 기존 출력 폴더를 거절하고 `--output-directory`·`--dataset-version`을 제공한다. preparation verifier는 `--preparation-directory`·새 `--report`, followup verifier는 새 `--report`와 독점 생성으로 기존 기록을 보존한다. summarizer는 별도 `--report-directory`를 사용하고 실패/성공 보고도 새 폴더에 쓴다. 기존 소스/입력 hash 검사를 생략하거나 old manifest를 현재 소스로 통과시키지 않는다. Scoring/tokenization/모델 pin/gold를 바꾸지 않았다.

`test_preservation.py.txt`는 existing 폴더/보고 거절, 새 output·자료 버전,188검증의 별도 보고, 경로 이탈 거절, 오류 시 원 보고 보존을 검증했다. 실제 scripts 경로에 대한 중앙 policy를 바꾸지 않고 no-auth source copy에서만 제안 코드를 적용했다.

## 연결 fixture의 범위

`test_connections.py.txt`의 C01~C20은 실제 현재 DocumentStore/documents_server ASGI 코드에 canonical15근거를 seed한 fixture와 별도 합성 provenance fixture를 사용한다. 제품·설명서 개정·자료팩 버전·public/synthetic·근거/문서 ID·페이지·문자 범위·raw quote hash·lexical 검색 부분 집합·검색0건·조건부 문구 보존을 검사한다. ID조회 API의 제품/버전 filter 부재는 소비자가 재확인한다. 현재 API 방식은 literal_token_count이며 BGE로 재표기하지 않는다.

합성 provenance의 offset/hash는 합성 텍스트에서 실제 계산하며 LG PDF의 실제 파싱/위치 검증을 대신하지 않는다. no-gold4개는 개발 기대 대응의 유지 검사이며 LLM 의미 평가가 아니다. 47개는20연결+10보존+17기존helper다. 실제 HTTP 서버/제품 upload/재시작 검증은 #13에서 남는다.

## 6개 등록 제안

| 기존 질문 | 제안 ID의 fact | 문서 페이지 | 보존 조건 |
|---|---|---:|---|
| FR-03 | F12 | T876MEE1H1 p22 | 벽면10cm·원문 설치 조건·지원문서5cm 충돌 C01 미해결 |
| FR-03 | F13 | T876MEE1H1 p22 | 제품 문 위쪽과 설치장 사이2.5cm |
| DW-03 | D03 | DUE6BGL2E p57 | DUE 계열 빌트인 오른쪽 열; 프리스탠딩 상판 제거 시 동일 치수와 구분 |
| MW-03 | M06 | MW23FDI p37 | Max1000W*1는 짧은 시간/시간 경과에 따라 변경될 수 있음 |
| MW-03 | M07 | MW23FDI p37 | 정격 소비전력1570W; 고주파 출력과 별도 물리량 |
| MW-04 | M13 | MW23FDI p17 | 모델별 차이·문 연 상태 시작/선택 약4초; 전원 분리 후 유지 미확인 |

`missing-evidence-proposal.json`은 기존 개발 gold ID6개를 proposed Evidence ID로 제시하고, 설명서 source_ref의 MFL 개정·PDF/cache hash·유일한 raw quote/start/end(Unicode codepoint, 끝 제외)·source ID를 묶는다. product-page의 unversioned 수집 태그로 설명서 개정을 대체하지 않는다. 관련 전체4페이지의 frozen300dpi 이미지를 시각 검토해 빌트인 열/각주/조건 문구를 확인했다. PDF/이미지는 Git에 포함하지 않는다.

현재 등록15근거는11gold 중7질문을 ID 수준에서 전부 포함한다. 제안6개가 승인·등록되면11질문의 ID coverage를 채울 수 있지만 새 검색 정확도11/11을 측정했다는 뜻은 아니다. 원27요약/질문/gold/실측을 수정하지 않고 새 plan/version/run으로 PM/#13가 인수해야 한다. feature_ids=[]의 standalone Evidence 제안이며 필요 시 PM이 reciprocal feature 연결을 별도 승인한다.

## 재현/근거

실행 pin `089ab16cc5c4fd727a2de904c516b62ea8ab493d`, Docker image `sha256:1bdbf6c2dd816f852d816d12e219ee1326febfa11d3f0f52d5eb1f6cc598bde3`, network none·uid1000·root read-only·caps dropALL·no-new-privileges·소스복사본만 mount. Git metadata/게시·AI 인증·독립 최종 답안은 복사/mount하지 않았다. 원 source-review를 복사본 scripts/tests에만 펼친 뒤4patch와 fixture를 적용해 Python3.11.17 unittest를 실행했다. 결과/원 실패는 attempt-1/2, fresh-preparation-validation, integrity-checks, lint-checks에 있다.

다음: PM의 scripts 수동 인수/코드 반영 → #13 새 문서 처리 결과 연결 → 승인한 추가 plan·근거 등록 → 새 실제 corpus로 검색/근거 부족 의미 검증 → PM 통합 검수. 이번3작업의 준비/fixture는 완료지만 #14의6단계와 공식 완료는 유지한다.
