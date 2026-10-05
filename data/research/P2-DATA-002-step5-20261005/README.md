# #13 5단계 — 검색·필터·원문 연결

상태: **승인된 시험 등록 범위의 5단계 실행 검증 완료. 전체 회귀 시간 초과·#13 공식 pending 유지.**
담당 신진하 / Codex LG Kitchen #13 대화. 기록 신진하-20261005-005-DATA002-STEP5 / 근거 신진하-E011-DATA002-STEP5.

사용자 원문: “5단계 실행해”. 기존 정이량 지시 우선·모르는 사항 확인·#12 다른 대화와 중복 금지 유지.
AI 해석: 앞 단계의 승인 CSV36건/5모델과 텍스트 PDF40쪽/등록 인용1건을 기존 실제 검색 API에 연결해 제품·버전 필터, 근거 ID 조회, 원문 행/페이지와 해시 추적을 실행한다. 6단계 세 제품 전체 흐름 및 7단계 게시·PM 검수·병합은 포함하지 않는다.

후속 사용자 원문: “추가사항:pr이랑 이슈에 올리지마 내가 올리라할때올려”. 이 대화의 결과는 로컬에만 남기며 Issue/PR 게시·push·상태 보고 댓글을 실행하지 않는다. 향후 게시 지시를 받기 전까지 이 제한을 유지한다.

## 시작 기준과 완료 조건

- 로컬에 확보된 main 고정 `bbf4e1c1da0106e140c6c7e87f7159e6f0fe3532`를 별도 tmp 스냅샷으로 재사용한다. 이전 3·4단계 f88dd7a와 등록/검색 코어 파일 변경0을 확인했다. fetch는 네트워크 연결 실패였으므로 원격 최신 확인 성공으로 표현하지 않는다.
- 인증 브라우저에서 #13 Open·Todo·DATA001 의존·미체크 완료 조건 및 최신 PM `PM-20261005-DATA-001-CITATION-FIX`를 확인했다. #12 PR74 최신 head 5af64e93b1ca413317a91893e530901fc7f5874e는 Open·PM 검수 대기다. 해당 기능 인용 보완/자료 버전 .2는 다른 대화의 작업이며 이번 입력과 섞지 않는다.
- 기존 STEP34 등록 DB·원문을 새 private 폴더에 복사한다. 원 자료/코드/계약/하네스/과거 증거를 보존하고 코어·공통 API·Schema를 변경하지 않는다.
- CSV36리뷰 각각 검색→근거 조회→보존 CSV 행을 대조한다. PDF는 등록된19쪽 인용 검색→근거 조회→metadata 문자 범위→실제 PDF 재추출문을 대조한다.
- 모델·문서버전이 다른 검색 결과 혼입을 차단하고, 미등록 ID/버전·필수 조건 부족·잘못된 검색 입력을 실제 HTTP 오류로 확인한다. 검색 결과0은 기능 미지원 판정으로 바꾸지 않는다.
- 재시작 후 조회 결과/원문 해시 보존과 자기 서버 종료/포트 연결 거절을 실제 확인한다. 관련 회귀·계약·지침·phase2 검사와 개인 로그를 남긴다.

## 실제 5단계 실행 결과

`run_search.py --run-id verified`: **220검사 PASS / 실제 HTTP122요청**. 최초 실패 `runs/initial/`은 보존하고 새로운 run-id에서 재실행했다.

| 검사 | 결과 |
|---|---|
| 리뷰 원문 추적 | 기존 합성 리뷰36건 각각 검색→근거ID 조회→다운로드한 CSV 행2~37의 ID·텍스트·제품·버전·성격·출처를 정확히 대조했다. |
| PDF 원문 추적 | 보존 PDF40쪽을 실제 재추출했다. 등록 인용1건의 검색/조회→metadata→19쪽 문자248~285(끝 위치 제외)와 텍스트 해시가 일치했다. |
| 제품·버전 필터 | 가상 모델5개의6개 모델/버전 조합에서 다른 scope 결과가 섞이지 않았다. 같은 FRIDGE-A의1.0/2.0도 분리됐다. |
| 오류/부족 조건 | 잘못된 모델·문서버전·근거ID와 모델 없이 버전만 지정, 누락/빈/부호/긴 검색어, 잘못된 limit이 기존 HTTP 오류로 거절됐다. 공개 PDF/합성 CSV의 ID·모델 혼입도 거절됐다. |
| 검색 결과0 | 정상 모델/버전에서 빈 결과가 반환됐고 미지원 판정 필드는 생성되지 않았다. ‘찾지 못함’을 기능 미지원으로 바꾸지 않는다. |
| 재시작 | PDF·CSV 서버를 각각 종료/재시작해 검색·근거·원문·metadata 보존을 확인했다. 네 실행 프로세스 종료 및 두 포트의 listener 부재를 확인했다. |

기존 코어/Schema/API를 수정하지 않고 기존 등록·검색 기능을 재사용했다. 원 STEP1/STEP2/STEP34, 원본/DB, demo/task/계약 해시가 유지됐다. 실제 고객 리뷰0·AI호출0·OCR0·독립평가 원본 열람0이다.

종료 검사: 기존 검색/근거 회귀13·문서 등록 회귀10 PASS. 고정 소스 및 현재 checkout의 계약·AGENTS/CLAUDE 일치·phase2 무결성, 자기 Python Ruff·공백 검사 PASS. 해당23회귀와 실제220검사를 구분한다. 전체 회귀는240초 제한 초과로 미완료이며 전체 검사 성공으로 표시하지 않는다. 원격 게시/CI 실행은 하지 않았다.

## 한계와 실패 기록

- CSV는 기존36합성 리뷰를 받는 고정 경로, PDF는 공용 설명서의 등록된19쪽 인용1건이다. 임의 파일 처리, 세 실제 제품 전체 문서 흐름, 실제 Agent 판단 결과에서 근거 추적을 완료한 것이 아니다.
- PDF의 기능 목록은 비어 있다. 원문이 맞다는 검사와 T876MEE1H1 정확 모델의 옵션/기능 적용 판정은 구분한다. #12 PR74의9기능 의미 검수는 PM 대기다.
- 기존 검색 방식은 `literal_token_count`다. BM25/BGE/재정렬 성능 비교(#14), OCR나 한국어 검색 품질 평가는 실행하지 않았다. 모든 리뷰를 원문 자체로 검색해 원문 연결을 검사했으며 자연어 질문의 검색 정확도 점수로 사용하지 않는다.
- 기존 검색 API에서 모델 필터는 선택 사항이어서 필터 없는 검색은 여러 모델을 포함할 수 있다. 근거ID 조회 API도 모델/버전을 매개변수로 받지 않는다. 소비자는 현재 선택한 모델·버전과 반환 근거를 대조해야 한다. 이번 검사에서는 검색에 정확한 두 필터를 지정했고 반환 scope를 대조했다. API가 모든 호출에 제품 선택을 강제한다고 주장하지 않는다.
- 최초 실행에서 검색/필터/원문 대조 뒤 종료 확인이 실패했다(208검사 중 마지막 실패/HTTP116). socket `connect_ex`의10035와 별도2초 연결의 TimeoutError는 열린 listener 증거가 아니다. `Get-NetTCPConnection`은 접근 거부였다. 별도 정상 `netstat` 조회에는 listener가 없고 TIME_WAIT/PID0만 있었다. 최초 두 Ruff 항목도 보존/수정했다. `cleanup-diagnostic.json`에 상세를 남겼다.
- 자기 runner만 수정해 시작 시 native netstat의 실제 listener/PID를 먼저 관측하고 종료 후 같은 포트의 listener 부재를 확인한다. socket 시간 초과는 그대로 기록하고 네이티브 조회 성공/형식 검증으로 구분했다. PM 공통 종료/포트 코드는 변경하지 않았다.
- 전체 회귀는 최초 finisher에서240초 제한을 넘었다. 최초 종료 도구는 부분 test 출력 보존을 놓쳐 개별 완료 수/실패 수를 확정할 수 없다. 시간 초과를 `baseline-first-timeout.json`에 그대로 기록했다. 자기 finisher를 부분 출력 보존/시간초과 기록 및 동일commit의 실패 증거 재사용으로 보완한 뒤, 관련13+10회귀·계약/지침/하네스/lint만 재검사했다. 전체 suite를 반복하지 않았고 `final-checks.json`의 whole_suite_passed는false다. 최초/보완 finisher 원본을 모두 보존했다. 기존 STEP34의 전체485회귀 실패도 해당 원 증거에 남는다.
- GitHub 커넥터404, git fetch 네트워크 실패, 오래된 현재 checkout의 상태 스크립트 부재 및 고정 스냅샷의 gh 부재를 브라우저 실제 조회와 구분했다(`preflight-read.json`). 원격 변경이나 보고 성공으로 표현하지 않는다.

## 증빙과 재현

- `runs/verified/search-checks.json`: 실제122요청/220검사·소스/입력/응답 해시·서버 명령/프로세스·시작과 종료 포트 관측.
- `runs/verified/original-traces.json`: 리뷰36건의 원문 행/ID/모델/버전과 PDF19쪽 문자 범위/해시. 전체 원문/응답은 private에만 있다.
- `runs/verified/filter-isolation.json`: 모델5개/버전6조합의 실제 반환ID와 필터/ID조회 API 경계.
- `runs/verified/final-checks.json`, `source-provenance.json`, `completion-review.json`: 관련 회귀23/종료 검사, 전체 회귀 시간초과, 이전8소스/계약 해시 동일성과 최종 개별 범위 판정.
- `runs/initial/search-checks.json`, `cleanup-diagnostic.json`: 최초 실패·추가 진단 보존.
- 실행 당시 Python 소스는 각 run의 `executed-runner.py.txt`, 최초 종료 검사 소스는 `executed-finisher.py.txt`, 보완 종료 검사 소스는 해시를 붙인 `executed-finisher-*.py.txt`에 보존한다. private 원본/DB/토큰/전체 응답은 `private/data002-step5/{run-id}/`에 있다.

다음은 6단계의 냉장고·식기세척기·전자레인지 동일 문서 처리 흐름 검증이다. #13 공식 완료·PM 검수/병합은 별도이며 현재 사용자 직접 할 일은 없다. PR/Issue/push/원격 보고는 사용자 추가 지시 전까지 실행하지 않는다.

재실행은 기존 STEP34 private 등록과 고정 commit이 필요하며 새 run-id를 사용한다.

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step5-20261005/run_search.py --run-id reproduce-01
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step5-20261005/finish_checks.py --run-id reproduce-01
```
