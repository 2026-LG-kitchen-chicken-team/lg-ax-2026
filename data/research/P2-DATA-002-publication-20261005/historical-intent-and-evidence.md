# #13 단계1~5의 기존 의도·수행·근거 기록

이 파일은 게시 전 로컬 개인 두 문서에서 해당 DATA002 기록만 발췌한 역사 사본이다. 원 문서와 다른 작업의 기록은 변경하지 않았다. 현재 게시 승인과 미완료 상태는 이 인수물 README 및 새 세션 두 문서를 따른다.

### 신진하-20261005-002-DATA002-STEP1 — #13 시험 입력·예상 원문 연결 준비

- 작성/실행 확인: 2026-10-05 KST, 입력 준비 검사 시각 03:47:50. 담당 신진하 / Codex 현재 대화 / 위 로컬 저장소.
- 상태: 1단계 로컬 준비·검증 완료. P2-DATA-002/#13 전체는 pending, PM 미검수·미병합·미통합.
- 지시 출처: 직접 사용자. 이전 001-local/E007-local, 근거 신진하-E008-DATA002-STEP1. Issue #13, 요구 R03/R04/R05/R06/R10/R13.

#### 사용자·PM 지시

> “그럼 지금 #13을 해보자 1단계부터 실행해. 최우선으로 정이량이 지시한거에서 벗어나지말고 모르는거있으면 물어보고 하네스를 사용해도 좋아.”

PM 지시 요약(원문과 구분): [PM-20261005-DATA-001-MINIMUM-HANDOFF](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935)는 10/5 18:00 최소 인수/구체 막힘 보고와 10/20 전체 제출을 구분하고, 인수 대기 중 #13 처리/OCR·#14 비교 입력의 독립 준비를 허용했다. [#13](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13)은 자료 등록·파싱·검색·모델/버전 필터와 원문 연결을 담당 신진하에게 배정했다. 브라우저에서 이번에 직접 읽었다.

#### AI 해석·완료 조건

이번 1단계는 이미 보유한 CSV/PDF 시험 입력을 정하고 모델·문서 버전·자료 성격·원문 위치 및 개발 기대 결과를 준비하는 것이다. 신규 자료·가전 범위 확대나 등록/API 구현으로 해석하지 않는다. 원본/기존 ID 보존·자료 성격 분리·Schema 검사·실제 실행 근거를 갖추면 이 준비 단계를 마친다. 앞선 #13 미실행 조건과 달라진 범위는 이 직접 요청으로 승인된 준비뿐이다.

#### 예정 행동과 실제 수행

1. root 지침·공통 기록 규칙·자기 기록/근거·PM 최신 지시를 확인하고 `next --member 신진하`, `packet P2-DATA-002`를 읽었다. 선행 #12와 #13 pending을 확인해 공식 start/finish를 실행하지 않았다.
2. 초기 의도/계획을 STEP1/README에 남긴 뒤, 기존 dataset 리뷰 36건을 reviews-v1.0.csv로 손실 없이 내보냈다. 기존 5모델/36리뷰/42근거는 그대로 두고 CSV 기대 결과에는 리뷰 근거 36건만 연결했다.
3. 기존 공식 냉장고 PDF를 원본 해시로 확인하고 18~19쪽 텍스트·렌더를 함께 읽었다. T876MEE1H1·MFL71401557 Rev.00_032526·F-M·19쪽의 선반 주의 문구를 별도 실자료 기대 근거로 연결했다. 실제 PDF 내용을 합성 FRIDGE-A의 근거로 혼합하지 않았다.
4. input-selection.json/expected-records.json/control-plan.json 및 준비 스크립트와 실제 run 로그를 작성했다. 다른 모델·버전·scope 누락·미언급은 향후 서비스의 기대 처리로만 작성했다. 비공개 평가 자료나 정답은 읽지 않았다.
5. 기존 계약 검사·지침 동기화·하네스 무결성·공백 및 입력 해시를 확인했다. 단계별 체크리스트/선정 결정은 STEP1/README와 자기 기록에 남기고 PM 공유 운영 상태를 바꾸지 않았다.

#### 검증·실패·한계

- CSV 36건의 원문·ID·모델/버전·원래 locator 행·근거 참조가 일치했다. 기대 Product 6·Review 36·Evidence 37건이 기존 계약 0.1.0 Schema를 통과했다. 기존 dataset/참고팩/case-input/schema/store/#13 task와 PDF 해시는 보존됐다.
- 기존 `uv`는 PATH에 없으며 프로젝트 .tools/uv/bin/uv.exe 실행 2회와 경로 조회가 접근 거부로 실패했다. 권한 우회/재설치 없이 기존 .venv Python 3.11.17로 동일 하네스/계약 스크립트를 실행했다. PDF 준비는 이미 제공된 번들 Python/pdfplumber·Poppler를 사용했다.
- run 로그의 argv·stdout/stderr·exit·해시·코드 commit은 runs/initial와 runs/final에 있다. 초기 스크립트 출력도 실제 다시 읽어 확인했다. phase2 valid=true는 기록 무결성이며 기능/PM 완료가 아니다.
- 공식 PDF의 옵션을 특정 SKU 기능 지원으로 단정하지 않았고 `feature_ids`는 빈 배열이다. 후보 근거 ID DATA002-FM-P19-SHELF-01은 개발 기대 레코드의 ID이며 실제 canonical 등록 ID가 아니다.
- 서비스 업로드/파서/검증 저장/검색·모델 실행·독립 평가·세 제품군 완주는 미실행이다. 이전 170시험/HTTP 검사 결과는 E007의 해당 버전에 한정하며 이번 실행으로 바꾸지 않는다.

#### 남은 일·재개

1단계 준비는 완료됐다. 다음 구체 작업은 2단계 문서 등록의 모델/버전/출처/해시·canonical ID·저장 흐름을 최신 PM 규격과 연결하는 것이다. 공통 Schema/API 변경이 필요하면 PM과 편집 경계를 조율한다. #12 인수·#13 전체 구현/검증·PR/PM 검수/병합/통합은 남았다. 변경은 로컬 STEP1 폴더와 신진하 개인 기록/근거뿐이며 원격 게시나 PM에게 메시지 전송을 실행하지 않았다. 실행 중인 서버/모델 작업은 없다.

### 신진하-20261005-003-DATA002-STEP2 — 문서 등록 실행 시작

- 작성: 2026-10-05 KST. 담당 신진하 / Codex 현재 대화. 상태 진행, #13 공식 pending 유지. 이전 002-DATA002-STEP1/E008-DATA002-STEP1 연결.
- 직접 사용자 원문: “그럼 진행해 그다음단계 그리고 #13이 뭐하는건지도 요약해줘 중,고등학생도 알기쉽게”. 정이량 지시 우선·모르는 사항 질문·하네스 허용은 유지한다.
- AI 해석: STEP1 입력을 기존 문서 등록에 실제 연결·재조회·보존 검증한다. 최신 PR69의 004-handoff/E010-handoff와 기존 구현을 읽어, 별도 등록 시스템 대신 고정2691ad1 코드 재사용을 선택했다. 이 clone의 현재7cc25fb·미커밋 STEP1과 다른 작업 공간의 게시/검수 상태를 구분한다.
- 예정 행동/완료 기준: STEP2/README에 명시. private 로컬 등록/원본 보존과 실제 HTTP 검사를 수행하고 결과·한계를 E009-DATA002-STEP2로 갱신한다. 새 수집·설치·모델 실행·공통 Schema/API 수정·온라인 게시/보드 변경은 포함하지 않는다.

#### STEP2 실제 종료 기록

- 상태: 이번 2단계 개별 등록·보존 검증 완료, #13 공식 pending. 작성/확인 시각은 STEP2/runs/verified와 final의 checked_at_kst.
- 실제 행동: 고정 PR69의 DocumentRepository/ReviewCsvRepository를 재사용해 PDF1건·기존 합성36리뷰를 private에 등록했다. HTTP20요청/35검사로 메타데이터·원문 해시·동일 파일 재등록·서버 재시작 보존을 확인했다. 원문/DB/토큰/전체 응답과 추출문은 Git 제외 private에만, 고정 소스는 tmp에 보존했다. 만들었던 서버4프로세스는 모두 종료했다.
- 입력·범위: F-M/T876MEE1H1/MFL71401557 Rev.00_032526/public/40쪽 중19쪽 한 근거 DATA002-FM-P19-SHELF-01, REVIEWS-CSV-v1.0/기존5모델/1.0/synthetic/36리뷰. 단일 PDF 제한 plan은 전체 기능 목록·실제 후기·독립 평가가 아니다. 로컬 ID 등록을 전역 채택으로 표시하지 않는다.
- 실패·복구: initial PDF400/SOURCE_MISMATCH는 기대 텍스트와 pypdf 줄바꿈 차이였다. 원본/STEP1을 수정하지 않고 같은 단어의 유일한 raw span을 plan에 연결했다. CSV 열 순서400/PARSING_FAILED는 기존 serializer의36행과 STEP1을 손실 없이 대조해 연결했다. aligned PASS 뒤 import Ruff I001 두 지적을 수정하고 최종 verified를 새 run으로 실행했다. 각 당시 스크립트·원본/결과 해시·실패 로그를 보존했다.
- 오류/검사: 다른 CSV 모델/버전·변경 PDF 바이트·미등록 문서ID·잘못된 인증/Origin 거절. 필수 scope 누락은 trusted plan 생성의 KeyError로 거절되며 사용자 메타데이터 API의 친절한 오류로 주장하지 않는다. 기존 문서 등록8/CSV 경계5 fixture·자기 스크립트 Ruff·현재 clone 계약/지침/phase2/공백 PASS. 기존 자료/계약/검색/task 및 STEP1 입력 해시 유지. 기능 검사와 PM 승인·수요·검색 품질을 구분한다.
- 산출물/근거: STEP2 README/run_registration.py/finish_checks.py, initial·aligned·verified·final 로그. 실행 코드2691ad1/파일 SHA·입출력·parser·명령/exit는 E009-DATA002-STEP2와 각 JSON에 연결했다. 새 공통 파일/API/Schema·기본 데이터·타 작업 공간 파일/기록 변경 없음.
- 최신 읽기 한계: project_report.py status는 WinError2로 실패해 설치 없이 브라우저 #12/#13·PM 지시·PR69/기존수신증을 확인했다. CLI 실패를 상태 조회 성공으로 바꾸지 않고 새 온라인 보고/게시도 하지 않았다.
- 남음/다음: 등록에 필요한 제한된 파싱은 실제 실행했지만 일반 명세JSON/OCR/임의 문서 처리·전체 검색/Agent 연결·세 제품군 완주·#12 인수·PM 검수/병합/통합은 남았다. 다음 구체 행동은 3단계 추출 결과의 페이지/행·모델/버전/ID 대조다. 현재 사용자에게 필요한 정보나 별도 승인은 없다.

초기 템플릿의 '실제 작업 기록 없음' 상태는 아래 기록으로 갱신한다. 모델 추천/문서 조사와 실제 한국어 성능·GPU 실행을 구분한다.

### 신진하-20261005-004-DATA002-STEP34 — #13 추출·검증 저장 실행 시작

- 작성 2026-10-05 KST / 담당 신진하 / 현재 LG Kitchen #13 대화 Codex. 상태 진행, 공식 #13 pending 유지.
- 사용자 원문: “그럼 #13에 대해서 하자 3~6단계에서 지금 3,4단계만 실행하자”.
- AI 해석: STEP1/STEP2 입력을 재사용하고 최신 main f88dd7a의 파서/자료 검증을 별도 스냅샷에서 실제 실행한다. 3단계 원문·페이지/행 대조, 4단계 오류 거절·정상 저장 보존만 수행한다.
- 경계: LGAX #12의 인용 수정/평가 자료, PM의 원 PDF 무결성 코드, 검색 연결·세 제품 완주·온라인 게시·검수·병합을 이번 수행에서 제외한다. 기존 dirty 파일·STEP1/STEP2·독립 평가 원본은 보존한다.
- 예정 행동/완료 조건: data/research/P2-DATA-002-step34-20261005/README.md. 새 private 실행에 STEP2 등록을 복사하고, 실제 파서/HTTP/계약 경계를 구분한 검사·실패·코드/자료 해시를 E010-DATA002-STEP34로 연결한다.

#### DATA002 STEP34 실제 실행·종료 근거

- 사용자 요청 범위의 3·4단계를 기존 승인 CSV36건·공식 PDF1건에서 실행했다. 고정 main f88dd7ac6448ef863a8cdc418804b7838eff0e24를 tmp에 추출해 기존 코어를 재사용했으며 checkout/타 작업 공간/공통 코어/Schema/API를 수정하지 않았다.
- 3단계: 실제 CSV 파서로36건의 원문·행2~37·모델/버전/성격·근거 ID를 대조했다. 실제 pypdf로40쪽을 추출하고 등록된19쪽 문구의 원문 문자 범위와 해시를 검증했다. 전체 추출문과 원본·DB·응답은 private에만 저장했다.
- 4단계: HTTP CSV17종 변조와 잘못된 PDF 원문/형식/ID를 거절하고 정상 등록이 보존됨을 확인했다. 잘못된 PDF page0/41/다른 page/없는 문구4종은 실제 파싱 뒤 오류로 거절되고 DB/원문 부분 저장이 없었다. 계약 검증의 누락·중복·교차 모델/버전/성격·잘못된 feature 연결과 서버 scope/version 재사용 거절도 분리해 확인했다.
- 결과: 주 실행130검사/기록 HTTP29요청 PASS. 별도 새 저장소 PDF/CSV 실제 삽입·원문 보존·재개8검사 PASS. 합계138검사. 서버4프로세스 종료 후 포트50837/50838 실제 연결 거절 확인. STEP1/STEP2와 기존 자료/task/계약 보존.
- 보조 검사: 자기 스크립트 Ruff·공통 계약·지침 일치·phase2·공백 PASS. 기존 전체485회귀는 웹 CI 준비/정리2검사 실패를 보존했다. 같은 고정 코드의 단독 API 준비 진단은 PASS, 해당2검사의 독립 재검사 결과는 failed-checks-retry.json. 전체485 PASS나 원인 확정으로 표시하지 않는다.
- 한계: 승인된36건 전용 CSV와 공용 냉장고 PDF40쪽 중등록1문구의 처리/검증이다. 제품별 기능 적용·일반문서/OCR·사용자 메타데이터 API 전체 완료가 아니다. source_kind 누락 등의 서버 설정 검사와 HTTP 오류 거절을 boundary로 구분했다. 실제 모델0/OCR0/독립 평가 원본 읽기0.
- 온라인: gh 부재로 project_report status WinError2. 인증 브라우저 #13 Open/담당 ginaginaring/Project Todo/선행DATA001/미체크 완료조건 확인. 이번 사용자 지시는3·4단계로 제한돼 게시/PR/상태 전송은 하지 않았다. 공식 pending 유지·PM 의미 검수/의존 해제/병합/통합은 별도다.
- 변경/근거: data/research/P2-DATA-002-step34-20261005의 README·run_steps.py·verify_fresh_storage.py·finish_checks.py·retry_failed_checks.py와 immutable runs/initial 결과, 신진하-E010-DATA002-STEP34. 이전 실패/증거를 삭제하지 않았다.
- 다음: #12 인용 보완 결과를 확인한 뒤 #13 5단계 검색/원문 연결 scope를 고정한다. 이번에는5·6·7단계를 실행하지 않았다. 현재 사용자가 직접 할 일은 없다.

- 2026-10-05 STEP34 보조 검사 정정/확정: 기존 두 웹 CI 검사의 독립 재검사에서 API 준비 검사 PASS, 실패 경로 종료 정리 검사 FAIL1. 단독 API CLI 진단은 PASS다. 전체 회귀 원본2실패와 독립 재검사1실패를 함께 보존하고 원인은 미확정으로 유지한다. 이번 DATA002 실제3·4범위138검사 및 문서 서버의 실제 포트 종료 확인은 PASS다.

### 신진하-20261005-005-DATA002-STEP5 — 검색·제품/버전 필터·원문 연결

- 작성/갱신 시각: 2026-10-05 05:14~05:33 KST. 상태: 승인된5단계 개별 실행 검증 완료·전체회귀미완료·미게시·#13공식pending. 담당 신진하 / Codex LG Kitchen #13 / 현재 clone codex/data001-lg-sourcepack-20261004, HEAD7cc25fb. 실제 실행 소스는 별도 tmp의 main bbf4e1c1da0106e140c6c7e87f7159e6f0fe3532다.
- 사용자 원문: “5단계 실행해”. 후속 “추가사항:pr이랑 이슈에 올리지마 내가 올리라할때올려”. 정이량 지시 우선·모르는 사항 확인·#12 다른 대화와 중복하지 않음 유지.
- AI 해석/범위: 기존 STEP34 승인 CSV36합성 리뷰/5모델과 공개 냉장고 PDF40쪽/등록 인용1건을 기존 실제 검색 API에 연결한다. 검색→근거ID→원문 행/페이지/문자 범위·해시·제품/버전/source_kind를 대조하고 잘못된 필터·조건 부족과 재시작 보존을 확인한다. 6단계 세 실제 제품 전체 문서 흐름/7단계 게시·검수·병합·AI판단·독립평가로 확대하지 않는다.
- 사전 확인: 온라인 #13 Open/Todo·미체크/선행DATA001, 최신 PM CITATION-FIX, PR74 Open/검수 대기/head5af64e9를 인증 브라우저에서 확인했다. 커넥터404·git fetch 연결 실패·현재 checkout의 상태 CLI 파일 부재/고정 스냅샷 gh WinError2를 별도로 기록했다. 원격 최신 fetch/보고 성공으로 표현하지 않는다. 최신 PR74 인용9기능/.2 자료는 LGAX #12 대화 범위라 섞지 않았다.
- 예정/실제: 기존 등록 DB/원본을 새 private 폴더에 복사했다. 기존 코어/Schema/API는 수정하지 않고 실제 loopback PDF/CSV 서버를 사용했다. 리뷰36건 각각 자기 원문으로 검색/조회 후 원 CSV 행2~37과 대조했다. PDF는 원본을 실제40쪽 재추출해 검색/조회/metadata19쪽 문자248~285 및 텍스트해시와 대조했다. 모델5개/버전6조합(같은 FRIDGE-A1.0/2.0 포함)의 실제 필터·미등록 ID/버전·조건 부족·오류/0결과를 검사했다.
- 실행 결과: verified run 220검사 PASS / 기록HTTP122요청. 네 서버 실행 프로세스 종료와 두 포트의 native netstat listener 부재 확인, PDF/CSV 각각 재시작 뒤 검색·근거·원문/metadata 보존. STEP1/STEP2/STEP34 및 private 원본·data/task/계약 보존. 8개 코어/계약 파일은 이전 f88 실행과 SHA 동일, runner와 실제 실행 원본 SHA도 동일.
- 실패/정정: 최초 initial run은 HTTP116/208검사에서 검색·원문·필터 뒤 포트 종료 관측이 실패했다. 10035/TimeoutError는 열린 포트 증거가 아니었다. Get-NetTCPConnection은 접근 거부, 별도 netstat 성공에는 TIME_WAIT/PID0만 있고 listener가 없었다. 자식 서버 잔류라고 단정한 중간 설명은 정정했다. 최초 증거와 두 Ruff 지적을 보존하고 자기 runner만 native netstat의 시작 listener/PID 관측→종료 부재 판정으로 보완했다. PM 공통 CI/포트 코드를 수정하지 않았다.
- 종료검사/실패: 검색/근거 회귀13·문서등록 회귀10, 고정/현재 계약·지침/phase2·자기Ruff/공백PASS. 전체회귀는240초 시간초과·개별완료수/실패수미확인이다. 최초 finisher가 부분 test출력 저장을 놓쳤으므로 timeout실제오류/원본을 baseline-first-timeout.json에 보존하고 자기 finisher만 timeout/부분출력보존·고정commit실패증거 재사용을 보완했다. 관련/종료검사만 다시 수행했고 전체suite반복·PM공통CI수정은 하지 않았다. final-checks.json은 requested_scope_result pass / whole_suite_passed false다. 이전 STEP34회귀실패는 보존.
- 검증 경계: 검색은 literal_token_count이며 자연어 검색 품질/재정렬 성능 점수가 아니다. 모델필터 없는 검색은 여러 모델을 포함하고 근거ID 조회는 scope 매개변수가 없으므로 소비자가 선택 모델/버전과 반환 근거를 대조해야 한다. 이번 실행은 정확한 필터와 반환 대조를 수행했다. 미언급을 미지원으로 바꾸지 않았다.
- 산출물/근거: data/research/P2-DATA-002-step5-20261005의 README·run_search.py·finish_checks.py·preflight-read.json 및 runs/{initial,verified}; 신진하-E011-DATA002-STEP5. 원본/DB/전체응답/토큰/추출문은 private/data002-step5/{run-id}에만 있다. 실제 고객 리뷰0/AI호출0/OCR0/독립평가 원본 읽기0.
- 공식/다음: 이번 개별 범위와 #13 공식 완료를 구분한다. 다음은6단계 동일 계약의 세 제품 문서 흐름 검증이며 사용자 직접 할 일은 없다. PR/Issue/push/상태보고/PM메시지 전송 없음. 사용자가 올리라고 할 때만 게시한다. PM 의미 검수·#12 의존 해제·병합·통합은 미완료다.

### 신진하-E008-DATA002-STEP1 — #13 개발 입력 선정·원문 연결 준비의 실제 검사

- 관련 기록/담당/시각: 신진하-20261005-002-DATA002-STEP1 / 신진하 / 2026-10-05 KST. 초기 확인 03:47:50, 종료 확인 시각은 runs/final/final-checks.json.
- 근거 종류: 직접 사용자 요청, 인증 브라우저의 PM/Issue 읽기, 기존 원본·코드 읽기, 결정론적 CSV 대조/Schema/하네스 실행, PDF 원문 렌더 확인. 실제 서비스/모델/독립 평가 실행 아님.
- 작업 기준: branch codex/data001-lg-sourcepack-20261004, code commit 7cc25fba66e4d0f4a19ef9eebbaa9268937ce1c4, 계약 0.1.0. 현재 원격 main 전체와 같다는 주장은 하지 않는다.
- PM 출처: [#12 최신 최소 인수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935) 및 [#13](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13). 최소 인수 대기 중 독립 개발 준비·담당 신진하·#12 의존성과 자료 처리/원문 연결 범위를 직접 확인했다.
- 기존 원본: data/demo/dataset.json, P2-DATA-001-real-reference-20261004/reference-pack.json, R03-fridge-20261004/case-input.json. 기존 자료와 계약/검색/#13 task의 정확한 SHA-256은 STEP1/runs/initial/verification.json의 source_hashes_preserved.
- 실제 PDF: C:/Users/user/Downloads/REF_KOR_MFL71401557_00_260325_00_OM_WEB.pdf, 40쪽, MFL71401557 Rev.00_032526. SHA-256 d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815. 기존 공식 다운로드 URL·모델 적용 범위는 input-selection.json. 18~19쪽을 텍스트/이미지로 직접 확인했고 선반 주의 문구는 19쪽. 공용 매뉴얼 옵션을 특정 모델 지원 여부로 단정하지 않음.
- 재현: README의 번들 Python 명령으로 prepare_inputs.py --run-id <새ID>. 스크립트는 기존 .venv Python 3.11.17에서 lgax_contracts.validate와 phase2 next/packet을 호출하며 새 설치/네트워크 호출을 하지 않는다. PDF 준비의 pdfplumber 버전은 runs/initial/pdf-inspection.json.
- 실행 로그: STEP1/runs/initial/{phase2-next,phase2-packet,schema-check,pdf-inspection,verification}.json과 runs/final/final-checks.json. 실행 argv·조건·stdout/stderr·exit를 연결한다. builder/출력 해시도 verification.json에 기록한다. 자기 기록/근거의 자체 해시는 넣지 않는다.

| 확인 | 실제 결과 | 증거 |
|---|---|---|
| CSV 원문·참조 | 기존 36건/5모델의 ID·모델/버전·원문·행·근거와 손실 없이 일치 | reviews-v1.0.csv, verification.json |
| 개발 기대 레코드 | Product 6, Review 36, Evidence 37 Schema PASS | expected-records.json, schema-check.json |
| PDF 위치/보존 | 원본 해시 일치, 18~19쪽 직접 확인, 선택 문구 19쪽 | input-selection.json, pdf-inspection.json |
| 모델/평가 분리 | 실자료/합성 별도 입력, private 평가 미열람 | input-selection.json, verification.json |
| 하네스 | next=선행 #12, #13 packet pending; 공식 상태 변경 없음 | phase2-next.json, phase2-packet.json |
| 종료 무결성 | 기존 계약·지침 바이트·phase2 구조·공백/원본 해시 검사 | runs/final/final-checks.json |

- 실패/대체: uv PATH 미등록, 기존 .tools/uv/bin/uv.exe 접근 거부 2회 및 폴더 조회 접근 거부. 기존 가상환경으로 동일 스크립트 실행에 성공했으며 권한/실행 정책 변경·설치 없음. source 검사 pdfplumber의 2열 텍스트 순서는 서비스 파서 품질 증거로 쓰지 않는다.
- 지지하는 결론: #13의 1단계 개발 입력·메타데이터·원문 위치·예상 레코드 준비가 재현 가능하고, 이 준비 결과의 ID/원본 보존 및 기존 Schema 형식을 확인했다.
- 지지하지 않는 주장: 실제 canonical 문서 등록·파서·검증 저장·검색 필터 성공, 미언급을 미지원으로 단정, 기능/시장 효과, 독립 평가·#12/#13 전체·실제 PR/PM 검수·병합·통합 완료. control-plan은 미실행 기대 처리이며 통과한 서비스 시험으로 집계하지 않는다.

### 신진하-E009-DATA002-STEP2 — 기존 등록 코드를 통한 실제 입력 등록·보존

- 관련 기록/담당: 신진하-20261005-003-DATA002-STEP2 / 신진하 / 실행 시각 STEP2/runs/verified/registration-checks.json 및 runs/final/final-checks.json.
- 근거 종류: 직접 사용자 다음 단계 실행 요청, 최신 인증 브라우저/고정 Git 소스 열람, 실제 loopback HTTP·SQLite/원문 보존·재시작, 결정론적 대조·기존 fixture 시험. AI/OCR/독립 평가 실행 아님.
- 원래 코드: PR69 head2691ad194be9f0f1c85963ad27ac60626d888738, 다른 작업 공간의004-handoff/E010-handoff를 읽고 재사용했다. 이 clone의HEAD7cc25fb와 최신조회main671ec2b는 별도다. 새 코어/API를 중복 작성하거나 미검수 PR을 PM 승인으로 표시하지 않는다.
- 실행 소스/조건: run_registration.py는 Git 고정 아카이브를 tmp에 추출하고 실제 import 위치를 검사했다. documents/document_store/documents_server/review_csv/review_csv_server/pdf_text_worker/store 및 공통 Schema 파일 SHA는 verified 결과의 source_files, 아카이브 SHA와 실제 runner SHA/당시 원본은 같은 run에 있다. 프로젝트 Python3.11.17·기존 번들 pypdf, 새 의존성/설치/권한/모델 사용 없음.
- 원본: STEP1 reviews-v1.0.csv·input-selection.json·expected-records.json 및 기존 dataset.json. 공식 PDF 기존 로컬 경로/40쪽/원본 SHA d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815. 입력 선정/확인 근거는 E008-DATA002-STEP1, 공식 URL·버전·모델 적용 범위는 STEP1 명세.
- 실패/보존: initial PDF 등록 SOURCE_MISMATCH는 pypdf의 문장 중간 공백/줄바꿈 차이였다. 같은 단어의 유일한 원문 span을 선택해 정확한 raw text를 plan에 넣었다. STEP1 plain 기대 텍스트와 raw span 해시는 pdf_excerpt_alignment에 있으며 원본·STEP1은 그대로다. CSV 헤더 순서의 PARSING_FAILED도 기록하고 기존 serializer 변환본의36행 사전과 STEP1이 일치함을 확인했다. initial/aligned/verified의 당시 스크립트와 실패/성공을 각각 보존했다.

| 실제 검사 | 결과 | 위치 |
|---|---|---|
| 실제 HTTP 등록/조회/오류 | 20요청·35검사 PASS | STEP2/runs/verified/registration-checks.json |
| CSV 보존 | 36리뷰·기존5모델·1.0·synthetic·원문/ID/행 일치, 재시작 후 same hash | 같은 결과의 registered.csv/conversion/checks |
| PDF 보존 | F-M/T876MEE1H1/문서개정/public/40쪽·19쪽 한 근거, 원본 재조회 hash 일치 | registered.pdf 및 private 원응답 |
| 오류 차단 | 변조 CSV 모델/버전, 다른 문서ID, 변경 PDF, 인증/Origin 오류 거절 | verified checks |
| fixture/기본 규칙 | 등록8·CSV경계5·Ruff·계약·지침·phase2·공백 PASS | STEP2/runs/final/final-checks.json |
| 자원/원본 보존 | 만든 서버4개 종료, 기존 자료/계약/검색/task·STEP1 hash 유지 | verified servers_stopped/preserved_hashes |

- 실제 데이터 저장은 private/data002-step2/{run-id}의 PDF/CSV·SQLite·토큰·전체 응답·전체추출문이며 Git 제외다. 공개 실행 근거에는 요청 경로/상태/응답 SHA·제한된 메타데이터만 둔다. registered CSV SHA64e83d42c65b1af18040c6a4cdac9a7f6b14fca63041005f6d79f6c9faaec4ab, STEP1 SHA3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9; 열 순서만 다르고 행/원문/ID는 동일하다.
- 최신 상태 읽기: project_report.py status는 WinError2(exit1)로 실패했으며 exact argv/stdout/stderr를 final-checks.json에 남겼다. 브라우저 #12/#13·PM MINIMUM-HANDOFF·PR69/기존 ACCEPTED를 직접 읽었다. 새로운 보고/온라인 상태 편집/PR 게시·PM 검수/병합 수행으로 표현하지 않는다.
- 지지하는 결론: 선정된 두 개발 입력을 기존 승인 범위의 로컬 등록 경로에 연결하고 원문·모델·버전·출처와 재시작 보존을 실제 검증했다. 로컬 단일 PDF 근거 ID가 등록됐으며 기능 지원 판정은 생성하지 않았다.
- 지지하지 않는 주장: 일반 문서 업로드/OCR/모든 PDF 레이아웃 품질·전체 검색/Agent 완주·실제 수요·독립 평가·#12/#13 전체·PM ID 채택/인수/승인·병합·통합 완료. 필수 scope 누락은 trusted plan 내부 설정 오류이며 새 사용자 메타데이터 API의 친절한 오류로 주장하지 않는다.

### 신진하-E010-DATA002-STEP34 — 승인 입력 추출·검증 저장

- 연결 기록: 신진하-20261005-004-DATA002-STEP34. 확인2026-10-05 KST. 현재 대화의 실제 로컬3·4단계 증거이며 #13 공식 완료/PM 승인/병합 증거가 아니다.
- 소스: main f88dd7ac6448ef863a8cdc418804b7838eff0e24. run_steps.py가 git archive SHA와 documents/document_store/review_csv/pdf_text_worker/store/계약 파일 해시·import 경로를 기록했다. 현재 checkout7cc25fb와 구분한다. 기존 production 코드 변경 없음.
- 입력: STEP2/runs/verified의 고정 입력/등록 증거. CSV 합성36건/5모델/문서1.0/기존원문SHA64e83d42c65b1af18040c6a4cdac9a7f6b14fca63041005f6d79f6c9faaec4ab. PDF F-M/T876MEE1H1/public/40쪽/MFL71401557 Rev.00_032526/SHA d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815. PDF 등록근거 DATA002-FM-P19-SHELF-01은 로컬 개발 ID이며 확정 기능을 주장하지 않는다.
- 실행 명령/재현: STEP34/README의3개 Python 명령. 실제 main/run_id/runner 파일SHA·HTTP 요청/status/responseSHA·검증 경계·오류·실제 parser/version·원문 페이지/행/문자 범위/해시는 runs/initial/step34-checks.json 및 extraction-records.json. 실행 당시 스크립트 원본도 보존했다.
- 결과: 실제 파서/기존HTTP/계약/저장 주 실행130검사 PASS, HTTP29요청. fresh-storage-checks.json의 새 DB 실제 삽입·원문/검증 결과·재개8검사 PASS. 합계138검사. PDF4실패에서 DB/원본 부분 저장 없음, CSV17변조 뒤 정상 등록 및 서버 재시작 보존. port-cleanup-check.json에서두포트 실제 연결 거절 확인.
- 검사: final-checks.json의 계약/지침/phase2/자기Ruff/공백PASS. 변경 없는 고정 main 전체485검사의 웹 CI2실패는 원문 결과로 보존. 단독 ci-probe-diagnostic.json PASS 및 failed-checks-retry.json 독립 재검사와 구분한다. 상태CLI WinError2·인증 브라우저 #13상태확인도 해당 로그와 기록에 연결했다.
- 지지: 지정된 승인 CSV·텍스트PDF의 파싱/원문 위치·scope 보존, 누락/중복/교차scope 거절, 실제 저장/원자성/재개. 미지지: 임의 문서·OCR·기능 적용의 의미검수·시장수요·검색/재정렬성능·Agent판단·독립평가·#13전체완료. source_kind public/synthetic 보존·미언급 미지원 전환 없음.
- private 원본/전체추출문/응답/DB/임시토큰은 private/data002-step34/initial에만, 실행 코드 스냅샷은 tmp/data002-step34-source-initial. 기존 STEP1/STEP2 원본/실패와 LGAX #12 인용/평가 작업을 보존했다.
- 다음은 최신 #12 인용 수정 결과 확인 후 #13검색/원문 연결(5)이다. 이번3·4단계 지시에 따라 온라인 게시/PM 검수/병합/통합은 하지 않았다. 현재 사용자 직접 조치 없음.

- 2026-10-05 STEP34 보조 검사 정정/확정: 기존 두 웹 CI 검사의 독립 재검사에서 API 준비 검사 PASS, 실패 경로 종료 정리 검사 FAIL1. 단독 API CLI 진단은 PASS다. 전체 회귀 원본2실패와 독립 재검사1실패를 함께 보존하고 원인은 미확정으로 유지한다. 이번 DATA002 실제3·4범위138검사 및 문서 서버의 실제 포트 종료 확인은 PASS다.

### 신진하-E011-DATA002-STEP5 — 실제 검색·필터·원문 추적 검증

- 관련 작업기록/담당/시각: 신진하-20261005-005-DATA002-STEP5 / 신진하 / 2026-10-05 05:14~05:33 KST.
- 지시/범위: 사용자 “5단계 실행해”, 후속 “추가사항:pr이랑 이슈에 올리지마 내가 올리라할때올려”. 기존 승인 CSV36건/PDF등록1인용을 실제 조회하며 6·7단계와 타 대화 #12 인용/평가 변경을 제외한다.
- 종류/버전: 실제 local HTTP·기존 canonical 계약/파서·SQLite 등록 재개·native 포트 관측. Python3.11.17·main 고정bbf4e1c1da0106e140c6c7e87f7159e6f0fe3532. source-provenance.json에서 이전 f88의8개 실행 코어/계약 해시와 동일성을 확인했다. 해당 src와 실행 runner 스냅샷/SHA는 search-checks.json에 있다.
- 입력: 기존 STEP34의 DB/원본/plan/dataset을 새 private에 복사. CSV transport SHA64e83d42c65b1af18040c6a4cdac9a7f6b14fca63041005f6d79f6c9faaec4ab; 공개PDF SHA d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815. CSV 합성1.0 리뷰36/5모델, 공식PDF MFL71401557 Rev.00_032526/F-M의19쪽 selected 인용1건·Feature0. 실제 모델 적용 미확인 유지.
- 재현: README의 run_search.py --run-id {새ID}, finish_checks.py --run-id {새ID}. 실행 당시 runner/finisher 원본 보존. 전체 응답/CSV/PDF·추출문·DB·임시토큰은 private/data002-step5/{run-id}. 공개증거에는 원문 대신 위치/해시·ID·scope·오류만 있다.
- 실제 결과: verified/search-checks.json의220검사/HTTP122요청 PASS. 원문 검색→근거조회→36CSV행 대조 및 PDF 실제40쪽 재추출→19쪽 문자248~285 exact/text SHA 일치. 모델5개/버전6조합의 scope 분리, 미등록ID/버전·조건 부족·잘못된 검색과 limit 거절, 정상0검색은 빈 근거로 유지. original-traces.json/filter-isolation.json에 상세.
- 저장/종료: PDF·CSV 각각 실제 서버 재시작 후 검색/원문/metadata 보존. 네 프로세스 종료 및 두 포트 시작 시 listener/PID를 관측하고 종료 후 정상 native netstat에서 listener 부재를 확인했다. socket10035는 시간 초과/미확인으로 별도 표시. STEP1/STEP2/STEP34·demo/task/계약 해시 보존.
- 실패: initial/search-checks.json은208검사/HTTP116 뒤 포트 종료 관측 실패 원본이다. socket10035·2초 TimeoutError만으로 열린 서버/자식 잔류를 입증하지 못했다. Get-NetTCPConnection 접근 거부, 별도 netstat 정상 결과 TIME_WAIT/PID0·listener없음과 초기 Ruff2개 수정은 cleanup-diagnostic.json에 보존했다. 자기 runner만 보완해 새 verified run에서 통과했고 PM 공유 CI는 변경하지 않았다.
- 종료 회귀/계약/지침/하네스 결과: final-checks.json requested_scope_result pass. 검색/근거회귀13·문서등록회귀10·고정/현재계약·지침/phase2·자기Ruff/공백PASS. 전체회귀는240초TimeoutExpired로미완료·whole_suite_passed false, 개별통과/실패수미확정. 최초finisher가부분출력보존을놓친실패를baseline-first-timeout.json에기록했다. 기존실행소스snapshot보존/자기finisher의timeout출력보존·고정commit증거재사용을보완해관련검사만다시수행, 전체suite반복/PMCI수정없음. 이전STEP34의485회귀실패는원증거보존.
- 지지: 승인 등록 범위에서 기존 실제 검색·제품/버전 필터·근거 원문 행/페이지/문자 추적·자료 성격 보존·재시작 보존. 미지지: 임의문서/OCR·모델별Feature 의미적 적용·Agent판단출력/불편별trace·세 실제 제품 완주·BM25/BGE 성능·독립평가·시장 수요·#13 전체완료. 실제 고객리뷰0/모델0/OCR0/독립평가 원문0.
- API 경계: 필터 없는 검색은 여러 모델을 포함할 수 있고 ID조회는 모델/버전을 받지 않는다. 소비자의 선택scope 대조가 필요하다. 이번에는 두 필터와 반환대조를 사용했고 빈 검색을 기능 미지원으로 표현하지 않았다.
- 온라인 읽기/게시: preflight-read.json의 커넥터404·fetch실패/상태CLI실패와 인증 브라우저 #13/PM/PR74 조회를 구분한다. 해당 PR74 head5af64e9 인용 보완은 다른 대화이고 이번 자료와 혼합하지 않았다. 이 대화의 PR/Issue/push/보고/메시지 전송0, 게시 지시 전 로컬 보관. 공식pending/PM 검수·의존 해제·병합/통합 미완료, 다음6단계·현재 사용자 직접 조치 없음.
