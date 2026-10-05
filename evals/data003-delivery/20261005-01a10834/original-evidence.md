# 신진하 — 작업근거

## 신진하-E-LIVE3-01a10834 — 실제 결과·검증 근거

2026-10-05T06:01:58.579948+09:00 / 신진하 / 현재 Codex. 로컬 세 작업 완료, 정식 의존/완료 상태 변경 없음.

요청한 환경 확인→실제 비교→검토 자료 작성의 세 로컬 작업 완료. #14 정식 완료/PM 검수·병합/#13 통합은 미완료다. 사용자 지시대로 PR·Issue·push·보고 전송·Notion 반영 없음.

- 자료/조건: 기존 DATA003 질문15·요약27·11gold/4무gold 및 OCR6사례14crop/원문3PDF/cache hash를 유지했다. 정확한 model+document revision으로 사전 필터하며 FR-04 개정미지정null·무정답 의미 미평가를 보존했다. 독립 final 기대 답안을 읽거나 수정하지 않았다.
- 환경 확인: 기존PC Python3.11에 학습 모델 패키지/가중치 없고 SSH접속config/agent 미설정·문서화된loopback서비스 미연결. 따라서 현재PC의 private/model-runtime에 CPU용 전용2환경을 새로 만들었다. 실제 모델 실행의 필수 준비로 설치/다운로드를 해석했으며 공식 API/패키지/weight 네트워크는 도구 자동 승인 검토로 허용받았다. 유료API·GPU·공용캐시·기존venv/시스템 설정·다른 작업공간 변경은 없다. 시작 디스크89.83GB/설치후77.14GB, RAM15.68GiB.
- 모델: BGE-M3 5617a9f61b028005a4858fdac845db406aefb181/MIT, reranker 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e/Apache2, Paddle c02ecaf1f22bfd1c618cce154fd19185b47e663a/Apache2. 공식HF API exactrevision/license와 내려받은19개파일의LFS SHA256/작은Gitblob SHA1+localSHA256/크기를 대조했다. 원시파일·캐시·설치로그는private이며전체패키지freeze는공개evals에있다.
- 코드: data003_model_preflight.py, download_data003_models.py, run_data003_models.py, summarize_data003_live.py, test_data003_models.py. 실행은모델파일local-only/offline·CPU4threads·BGEFP32/normalizedCLS/256tokens/batch8·rerankerrawlogits/top10. BM25Pythonfloat64/1thread 별도표시. tokenizer 최대119로truncation0.
- 실제검색: retrieval-v1의3방법각15×5/총225attempt+warmup6, 오류0·모델/개정혼입0. Hit@1/Recall@3/MRR@3 BM25=.9091(10/11), BGE=1(11/11), BGE+reranker=1(11/11). 지원55attempt median/p95 BM25 .6337/.9264ms, BGE316.2207/365.0488ms, reranker포함6006.4974/9531.8831ms. 원시순위/반복/실패와 각실행당시runner전체소스·hash를저장했다. 두모델을함께올린processpeak4206.1MiB이며방법별메모리/운영처리량이아니다. coldload BGE3444.7ms/reranker1985.4ms·index14486.3ms 별도. 이AI의중복학습모델/OCR/설치heavy작업은측정중실행하지않았고가벼운진척조회만했다. 공유PC외부부하는미통제다.
- BM25실패: MW-01의수동출력선택M11을기존BM25는못찾았다. 질문token 수동조리에서/선택할/수/있는/출력은/몇/w야 중 M11과겹침0, M06의조건문구‘수’만겹쳐2.1444점1위·나머지0점ID순때문이다. BGE와reranker는M11을1순위로회복했다. gold/corpus/tokenizer를이실패에맞춰고치지않았다.
- 실제OCR: 최종ocr-v3 14×5=70attempt+warmup2/오류0/모든영역반복문자일치. normalizedexact8/14, macroCER.0689935/microCER.0687023. 숫자본값15/15·명시단위12/12이나엄격숫자필드전체10/11:1000 W∗1의Unicode∗를ASCII*1각주규칙이분리하지못해extra1이남았다. 공백누락5영역·각주기호차이1영역을보존했고채점규칙을결과에맞춰수정하지않았다. median309.3421ms/p95513.4352ms/load3188.9ms. MW외형mm은crop밖머리글이어서단위분모제외. modelcolumn/layout accuracy null; 수동열지정은자동표인식성능이아니다. pypdf14구절존재와PaddleCER는서로다른분모/작업이다.
- 실패/복구: 기본외부소켓Win10013→승인된네트워크; HFsymlink권한Win1314→normal local_dir(관리자/개발자모드변경없음); Paddle import공용cache쓰기거부→호출범위tildecache전용격리(HOME/USERPROFILE/라이브러리소스변경없음); Paddle한글절대경로native읽기실패→동일파일ASCII상대경로. 초기다운로드/ocr-v1/v2로그와결과빈폴더는보존했다.
- 검증: 무결성216PASS/오류0, 새9시험·기존BM25 8시험·Ruff·계약30definitions/합성5모델36리뷰3요청·phase2valid/errors[]·동일지침·gitdiff/private제외PASS. 양쪽pipcheckNo broken requirements. 첫전체시험은shared main editable의다른코드로326시험4fail26errors;실제import경로관찰후worktreePYTHONPATH로수정했다. 올바른전체492시험491pass/WindowsCI실패cleanup1fail. 코드변경없이해당7시험단독재검사전부PASS. 전체첫실행을allPASS로바꾸지않는다. 신규브라우저/build/MCP·독립최종평가실행은없다. 실행후PythonPID15380을관찰했으나읽기전용CIM확인시이미사라져종료명령은없다.
- 검토의견: 이번개발셋의#13연결후보BGE-M3, BM25기준선유지·reranker추가품질없음/지연약6초로현조건채택보류. 텍스트PDFparser우선/OCR은대체후보이며스캔/잡음/전체페이지검출/열연결미검증. 독립모델우위·전체Agent성공·운영선택확정은지지하지않는다.
- 재개/다음: evals/data003-live/20261005/README.md, verification.json, execution-checks.json과retrieval-v1/results.json/ocr-v3/results.json을본다. 신진하#13실제출력연결후통합/무정답의미검토, PM정이량개발gold/실제출력검수·인수/병합/통합·공식완료가남는다. 사용자가게시하라고할때에만원격공유한다. 현재사용자직접할일없음.

근거 위치: [실측·검토 보고](../../evals/data003-live/20261005/README.md), [실행/검사](../../evals/data003-live/20261005/execution-checks.json), [검색 원시 결과](../../evals/data003-live/20261005/retrieval-v1/results.json), [OCR 원시 결과](../../evals/data003-live/20261005/ocr-v3/results.json). 결과/코드/원문/모델/패키지 버전 hash는 verification 및 execution-checks의 artifact/code/source 목록을 따른다. 자기 문서 hash를 자기 문서 안에 넣지 않는다.


## 신진하-E-LIVE3-01a10834 — 고정 모델 실측 시작

추가 사용자 지시: “pr이랑 이슈에 올리지마 내가 올리라할때올려”. PR·Issue 댓글/보고·push 등 원격 게시를 실행하지 않는다. 로컬 작업은 계속한다.

시작 2026-10-05T05:15:27.591365+09:00 / 신진하 / 현재 Codex 대화. 진행 중.

연결 기록: 신진하-20261005-LIVE3-01a10834. 입력은 기존 DATA003 protocol/corpus/queries/manifest, BM25 canonical v3, OCR canonical v2. 입력 hash와 모델 lock을 유지한다. 첫 네트워크 권한 오류·기존 설치 부재를 기록하며 기존 bootstrap 점수를 새 입력 실측으로 재사용하지 않는다. 결과/원시반복/실패/모델 파일 hash/코드 hash/실행환경을 새 evals/private 경로에 보존한다.


작업 의도·진행: [신진하 기록](../작업기록/신진하.md). 형식: [공통 규칙](../작업기록/README.md#근거-문서-형식).

## 현재 상태

최신 종료: 신진하-E-NOW3-01a10834 / 직접 사용자 지시의 세 로컬 작업 수행. BM25v3의11지원문항중10정답/75회·OCR6사례14입력/원문14구절 대조·#15의10검사기준/개발12사례를 기록했다. 새8시험·무결성164항목·Ruff·계약·phase2·규칙PASS. 이전 DATA003PREP 원본/hash 및 독립 최종 평가 답안은 보존한다. 실모델/OCR/변경서비스·PM 완료는 남았다.

### 신진하-E-NOW3-01a10834 — 세 후속 작업의 시작 근거

- 원문 지시/해석/예정 행동: 신진하-20261005-NOW3-01a10834 기록을 따른다. 준비/규칙 검사·실제 BM25 실행·OCR 입력 처리·전체 모델/OCR/서비스 실행을 구분한다.
- 시작 입력: evals/data003-preparation/20261005의 corpus/queries/protocol/ocr-cases/manifest, 고정 DATA001 참고팩과 기존 원문3개 PDF/cache. 원문 전체/비공개 평가 기대 답안을 새 공개 자료로 복사하지 않는다.
- 상태 확인: project_report status 실행파일 미발견, 로컬 next/packet 조회 성공, Edge #15 담당/의존/Todo/완료조건 직접 확인. 이 실패를 전체 온라인 상태 조회 성공으로 바꾸지 않는다.
- 범위: 기존 설치된 stdlib/PDF 라이브러리로 실행. 소스 모델/개정·해시·좌표·실제 결과/미측정·실패를 보존한다. 신진하 담당 로컬 자료/검색/평가 파일과 자기 기록만 수정한다.
- 아직 지지하지 않음: BGE/Paddle 성능, 전체 문서 OCR, R22 변경 서비스 통합, 독립 평가 E01 완료, PM 검수·병합·Notion/원격 보고 수신.

#### 종료의 실제 증거

- 연결: [세작업 결과·재현·한계](../../evals/data003-followup/20261005/README.md), [무결성164항목](../../evals/data003-followup/20261005/verification.json), [실행 검사 출력](../../evals/data003-followup/20261005/execution-checks.json). 2026-10-05 04:53 KST 검사, verification SHA256 `6d0355dbca948ea7dded47b77b8ac9131553a4494d941f4643879b07e207764b`.
- BM25 고정 입력: 직전 corpus27개/queries15개/protocol SHA256을 실제결과에 넣고 source/output13개·원본PDF3/cache3개를 보존 검사했다. 현재 runner source를 canonical v3출력에동결했다. rank에는 gold/답안/분류 없이 userquery/model/version/ID만 들어간다. FR-04 과거개정null 입력을 별도기록하며 현개정으로 대체하지 않는다.
- 실제관찰: v3의75측정+warmup2, gold11문항중10첫순위정답(Hit@1·Recall@3·MRR@3=.9091), 실행오류0/모델·버전혼입0. MW-01은M11누락/M06이1위인실패를보존. 무gold4문항의뜻/응답은미평가. CPU1thread/Pythonfloat64, RAM15.68GiB/peak25.90MiB, 지원55측정 median.3318ms/p95.6938ms. tiny corpus·공유CPU부하미통제이고모델성능/전체Agent효용이아니다.
- 조건/실패: v1/v2도원실행으로보존하되canonical v3만기준으로쓴다. 첫Ruff2개실패수정, v2PDF사전처리중첩확인후v3단독측정. CIM CPU/메모리 access denied는 [환경한계](../../evals/data003-followup/20261005/environment-limitations.json)와preflight의null에남겼고 platform/WinAPI관찰로대체했다. 권한상승/새설치/GPU없음.
- OCR 입력:6실문서페이지/14crop을300DPI RGB·정확한 sourcechar/point/pixel좌표·크기·PDF/raster/crop/goldhash로연결했다. private이미지/전문을시각열람한뒤v2수정/검토를별도visual-review.json에기록. 원문6페이지/14구역·두표열검토PASS. pypdf출력의14구절존재확인은단순존재검사이며CER/숫자·단위·모델열은null/OCR호출0. 실제인식이정확했다고주장하지않는다.
- #15 개발자료:6유형각2/총12dev,10criterion,57빈검수칸,실제충돌2보존. 원본fact/조건/null/출처를검사했다. 합성후기4·합성명세2를private에DEV버전·출처성격으로명시하고 실제후기0/실제새개정0 유지. before/afterhash·변경근거 의존판단/후보와 무관한fact보존을확인했으나 실제 R22서비스 호출0/E01독립최종사례사용0.
- 검증범위: 신규8unit·후속무결성164·Ruff·계약30정의/합성5모델36리뷰3요청·phase2valid/errors[]·동일규칙·diff검사PASS. 실제작업출력/원시반복·소스해시/크기/hash·빈결과양식을대조한다. 전체회귀·웹/MCP/실모델/독립평가는재실행한것이아니다.
- 지지: 요청한 세로컬작업의 실제기준선·실패, 재현코드/입력·검토된OCR준비물·개발검수계획/기대초안과 보존·무결성증거가존재한다. 개발성능을전체시장성능/독립평가/PM완료로확대하지않는다.
- 다음담당: 신진하 기존모델환경/라이선스·weightrevision확인과실측/#13통합, 황대겸 실제변경재검토, PM정이량 독립평가·의미검토/인수·병합·통합/완료. 원격게시/PR/보고ACCEPTED/PM수신/Notion미실행. 현재사용자직접할일없음.

### 직전 DATA003PREP 상태 (보존)

현재 대화 신진하-E-DATA003PREP-01a10834 / 2026-10-05 04:13 KST 검사 기준. #14 단계3/4의 로컬 개발용 질문15개·근거27개·검색3방법/OCR6사례 조건과 빈 측정표를 별도 브랜치에서 준비했고 무결성188항목 PASS. 기존 #12 실행 증거 및 비공개 독립 평가 답안은 보존한다. 실제 모델/OCR 성능과 PM 통합 완료는 미실행이다.

### 신진하-E-DATA003PREP-01a10834 — #14 준비의 출처·범위

- 관련 기록: 신진하-20261005-DATA003PREP-01a10834.
- 시작 코드: b82cf9c2d063458bc3e54eb34b856c1050c93ced, 별도 codex/data003-preparation-20261005.
- 읽은 자료: DATA001 real-reference/reference-pack.json, stage123 mapping/original-locations, stage345 model-pairs의 세 dataset, bootstrap retrieval/OCR 모델 ID·revision·설정과 기존 benchmark 코드. 원문 PDF/페이지 캐시는 기존 작업 공간의 private/documents-source에서 읽기만 한다.
- 온라인 확인: project_report status는 실행파일 미발견(WinError2), GitHub connector #14는404. 로그인된 Edge #14의 본문/담당/의존·Todo를 직접 확인했다. 이 결과를 전체 Project 실시간 조회 성공으로 바꾸지 않는다.
- 자료/평가 경계: 개발 질문은 기존 공개 설명서/사양 자료의 질의이며 실제 고객 리뷰가 아니다. 비공개 최종 독립 평가 답안은 읽지 않고 이 준비를 독립 성능 평가로 표현하지 않는다.
- 지지: #14 개발용 입력/정답 근거와 비교 조건은 선행 준비 가능.
- 지지하지 않음: #12/#13/#14 전체 완료, 새로운 성능 수치·모델 우위·실제 고객 수요·실가전 검증·PM 인수/병합·원격 공유.

#### 실제 산출물과 검사

- 원문 모델/버전: T876MEE1H1 — MFL71401557 Rev.00_032526 / DUE6BGL2E — MFL71959117 Rev.07_030626 / MW23FDI — MFL68822538 Rev.00_120925. 원본 URL·PDF/cache SHA256·페이지 수는 [manifest](../../evals/data003-preparation/20261005/manifest.json), 각 질문의 실제 페이지/근거는 [질문표](../../evals/data003-preparation/20261005/질문_정답근거표.md)와 queries.json의 gold_sources.
- 재사용 source_versions는 reference-pack/mapping/original-locations·제품별dataset3개·bootstrap 모델 결과/코드·합성dataset·공통schema·DATA003 task 13개다. 기존 파일을 수정하지 않았고 원문3개 PDF/cache 해시 및 문장3개 start/end char·해시를 대조했다.
- 모델 고정: BGE-M3 `5617a9f61b028005a4858fdac845db406aefb181` MIT, reranker-v2-m3 `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` Apache-2.0, korean_PP-OCRv5_mobile_rec `c02ecaf1f22bfd1c618cce154fd19185b47e663a` Apache-2.0 기존 snapshot. 두 BAAI pinned 공식 README의 license metadata는 web 직접 대조했고 Paddle pinned tree 접근만 확인/README web 읽기는 실패했다. Paddle 라이선스·실제 weight revision은 실행 전 재확인 대상이며 새 검증을 성공으로 꾸미지 않는다. 각 공식 고정 URL은 protocol.json models에 있다.
- 질문15개 중11개 gold/4개 무정답·범위·조건 대응. 질문·근거는 개발용이며 private final evaluation 답안은 생성/검사 입력이 아니다. 기존 고객 리뷰0과 모델 개정1개/제품인 한계를 보존한다.
- 검색45행/OCR12행 JSON·CSV는 모든 결과 `not_executed`/null. CER·숫자·단위·모델 열 지표 및 Hit@1/Recall@3/MRR@3·혼입·반복 시간/실패/메모리와 환경 양식을 고정했다. 실제 OCR crop/image·detector/layout 모델은 만들거나 실행하지 않았다.
- 실행: 기존 main clone Python3.11.17에서 준비 generator 후 verifier(원문 폴더 인자) 실행. [validation](../../evals/data003-preparation/20261005/validation.json) PASS/188checks/errors[]/모델0·OCR0. manifest SHA256 `ff88b9f1f6b8afbd72038db36456f0a4a0b560240214619310288330d5a223a9`, verifier SHA256 `f1de3233bd0bbc9c0b89603c1bacaead4614d03fa1eefd80a8412e991431f15e`. 소스/출력 전체 해시는 manifest에 있다. 이 문서의 자체 해시는 기록하지 않는다.
- 추가 검사: 새2스크립트 Ruff와 AST syntax PASS, 규칙 파일 바이트 동일 PASS, 계약 PASS(정의30/합성모델5/리뷰36/요청3), phase2 valid:true/errors[]/legacy stale, diff whitespace PASS. 전체 웹/MCP/코어 회귀·실모델·통합 검사는 이번에 수행했다고 하지 않는다.
- 실패 보존: 처음 선택한 #12 worktree의 빈 venv에는 jsonschema/Ruff가 없어 두 검사 실패. 기존 main clone venv로 실행 환경을 바로잡아 두 검사 PASS; 새 설치 없음. 앱 worktree 등록 실패·온라인 CLI/connector 실패 및 Codex 질문표 열기 queued를 위 기록과 구분한다.
- 실제 결과가 지지하는 주장: 요청한 3/4단계의 로컬 개발 입력·출처/버전 연결·비교 조건·빈 결과표와 재현 가능한 준비 무결성 검사가 존재한다. 규칙/구조 검사는 성능 우위·정답의 독립적 의미 검수·고객 수요를 지지하지 않는다.
- 후속 책임: 신진하 — 5단계 환경/weight/자원 확인과 protocol 어댑터·crop 고정 후 실험. PM 정이량 — gold 의미 검토와 이후 실제 결과 인수·병합/통합·#14 최종 판단. #13 실제 처리 경로 연결은6단계에 남는다. 원격 게시/자기보고·PM 수신·Notion 반영 없음; 현재 사용자 직접 할 일 없음.

최신 E009-local / 신진하-20261005-003-local. 기존 PDF3건 경로에 합성36리뷰 CSV 등록·파싱·검증·조회 및 실3모델 공통 작업실 자료 연결의 실제HTTP66요청/70검사를 추가했다. 사용자실행환경 전체395회귀·계약·하네스·MCP PASS. 실제모델 호출0/실제고객리뷰0이며 PM연결문의 댓글만 게시했다. 평가6유형 metadata/개발겹침0은 확인했지만 독립성/정답/실제평가는 PM미확인. 사용자 게시승인 전 부분PR/push/인증보고를 하지 않고 #12전체·PM검수/병합/통합은 미완료다. 이전 실패와 버전을 보존한다.

## 근거 기록

모델 카드/코드 조사와 실제 자료 처리·한국어 검색/OCR·GPU 실행을 별도로 기록한다. 문서 모델·버전·페이지와 결과의 원문 연결을 확인한 뒤 [공통 근거 형식](../작업기록/README.md#근거-문서-형식)으로 추가한다.

### 신진하-E001-local — 식기세척기 예시의 실제 제품 대응

- 관련 기록/담당/확인 시각: 신진하-20261004-002-local / 신진하 / 2026-10-04 17:49 KST.
- 근거 종류: 로컬 원고·코드 열람 및 외부 공식 자료 조사. 실제 검색/OCR/모델 실행은 아님.
- 원본: 기획/제출제안서_원고.md 59~66행; data/research/사례선정_2026-10-04.md에 URL/문서 표시일/열람 시각/섹션/모델·버전 불일치 기록.
- 기준 코드: commit 755c3927667ae1787d177622f89b7a1d10c68c48, 공통 계약 0.1.0. DemoStore는 합성 데이터 전용, 모델·버전별 literal 검색 존재. 기본 자료 5가상 모델/36합성 리뷰와 계약은 수정하지 않음.
- 실제 관찰: 원고 예시 2 식기 조합별 적재 안내, 실제 DUE6BGL2E의 높이 조절/상하단 제한/사이드랙 미지원 확인. 공식 지원 문서에서 적재 방향/열풍 모델 덮개 혼동 사용 문제 확인.
- 실패/제외: 실제 재신청 PDF 미발견. 검색된 PDF는 DIE5PT.AKOR 표지라 DUE6BGL2E 사양/설명서 근거로 채택하지 않음. OCR 없음. Python 3.11/jsonschema 없어서 기존 검색 실행 미실시. 신규 설치 없음.
- 지지: 원고 예시에 대응시킬 실제 판매 모델과 제한된 공식 사용 문제 근거가 존재한다.
- 지지하지 않음: 실제 제출 첨부본 일치, 해당 모델 구매자의 불편 빈도, 제안 서비스 수요/효과, 자료팩 전체 완성, #12 요구사항/PM 병합 완료.
- 구조 확인: git diff --check 통과, AGENTS.md/CLAUDE.md 바이트 일치 검사 PASS. phase2 validate는 과거 증거의 hash mismatch/로컬 merge commit 미존재로 valid:false; 전체 무결성 확인 미완료. 조사·선정 기록과 PM 운영 증거 수정을 분리하고 후자는 변경하지 않았다.

### 신진하-E002-local — 세 제품군 기존 자료의 실제 확보·참조 대조

- 관련 기록/담당/시각: 신진하-20261004-003-local / 신진하 / 2026-10-04 18:00~18:02 KST.
- 근거 종류: GitHub 최신 Issue/파일 조회, 로컬 코드/JSON 직접 읽기, 표준 라이브러리 실제 대조 실행, 코어 import 실패. 실모델/Agent/검색 질의 실행은 아님.
- 입력/버전: data/demo/dataset.json, manifest.json, planning_requests.json, 코어 store.py, 공통 schema. 자료·계약 0.1.0. 정확한 경로/SHA-256과 원격 blob은 data/research/자료확보현황_2026-10-04.json의 source_versions/latest_remote_blobs.
- 실행/환경: 설치된 번들 Python 3.12.14에서 JSON parsing/hashlib/ID 고유성/리뷰-근거-기능 참조 대조, ast로 기존 함수 확인, 소스 경로 지정 후 lgax_core import 시도. 기존 phase2 next --member 신진하와 packet P2-DATA-001 실행. 새 설치 없음.
- 관찰: 가상 모델 5·리뷰 36·기능 6·근거 42. 냉장고 3모델/30리뷰, 식기세척기 1/3, 전자레인지 1/3. 참조 불일치 0건, manifest 수량/SHA-256 일치. dataset SHA-256 97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0.
- 실패: 실제 lgax_core import는 ModuleNotFoundError: No module named 'jsonschema'. 프로젝트 Python 3.11 환경 미확보. 대표 질문 3개는 예상 MANUAL-001/004/005와 함께 미실행으로 기록. 기존 검색/검사를 복제하거나 스텁 처리하지 않음.
- 지지: 기존 합성 자료의 수량과 직접 참조 연결에 오류를 발견하지 않았고 재사용 대상 코드/입력·세 제품군 사례가 존재한다. 냉장고 2개는 2제품군이 아님.
- 지지하지 않음: 전체 JSON Schema 검사 통과, 현재 검색/API/파싱/Agent 완주 성공, 실제 제품의 설정 저장 기능, 실제 수요/효과, 자료팩/#12 전체 완료, PM 검수·병합·통합 완료.
- 최신 사용자 허가: phase2 사용과 LG 공식+SSG 승인 확인. 최신 방향 변경 후 신규 수집은 범위 확인 전 대기. 다음 단일 작업은 모델/확인항목/수집 상한 확인이다.
- 종료 확인: 기존 5개 입력/코드/계약 파일의 해시는 현황 JSON에 기록한 값과 계속 일치(변경 0개), git diff --check 통과, 로컬 지침 바이트 일치 PASS. 현황 JSON SHA-256은 3bfa72530f425b900cf740ecdd177795a7b8fb46ed9a8789c412864231a959b1. 전체 #12 완료/검색 3질문 실행은 false.

### 신진하-E003-local — 세 실모델 참고팩·#12 충족/잔여 대조

- 관련 기록/담당/시각: 신진하-20261004-004-local / 신진하 / 2026-10-04 18:10~18:34 KST.
- 근거 종류: 공식 제품/지원/설명서와 승인 SSG3판매글의 제한된 사실 조사, PDF 텍스트 추출/원본 표·도면 확인, 실제 구조·CSV/JSON·SHA-256 대조. Agent/검색/실기기/OCR 실행 아님.
- 원본/입력: 참고팩 sources.csv/JSON의 공식9건·SSG3건 URL, 설명서 개정/게시일/적용 범위/해시. 기존 inventory JSON SHA-256 3bfa72530f425b900cf740ecdd177795a7b8fb46ed9a8789c412864231a959b1.
- 모델/계약: T876MEE1H1 fridge / DUE6BGL2E dishwasher / MW23FDI microwave. Product5필드는 계약0.1.0 명칭을 따르고 URL·상태는 sidecar. source_kind public은 재배포 라이선스 아님. DemoStore 합성 전용 입력과 구분.
- 실행 환경: 설치된 번들 Python3.12.14 + 표준 라이브러리 json/csv/hashlib + 이미 제공된 pdfplumber/pypdf. 공식 PDF 다운로드3건을 읽었다. 새 설치/유료 API/권한·새 하네스 없음.
- 실제 실행: pdfplumber 페이지 텍스트와 규격 표/설치 도면 임시 렌더 확인; 전체 MW문서의 저장/호출/메모리/최근/즐겨찾기 키워드 및 메뉴 문맥 확인. serializer로 UTF-8 JSON/CSV 생성 후 실제 파일 다시 읽어 비교. 검증 기록은 data/research/P2-DATA-001-real-reference-20261004/verification.json.
- 최소 대조 결과 PASS/오류0: 세 모델/제품군, 공식9+SSG3 상한, 사실60·차이2, 출처 URL/모델/성격/버전/시각/페이지, CSV/JSON 값·위치, null/미확인·충돌 관찰값, 원본PDF 개정/모델/주요 숫자 및 해시. 기존5파일 해시 보존 true.
- PDF 해시: 냉장고 d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815 / 식기세척기 ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5 / 전자레인지 3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc.
- 출력 해시: reference-pack.json 11b52928b1be5e145a49327a704b9d62405e8d2272372075b54a9974d2ca9bb0. CSV3개 해시는 verification.json의 output_sha256. 자기 근거 파일의 자체 해시는 넣지 않음.
- 제한/실패: MW PDF 웹 조회 실패 후 공식 다운로드·pdfplumber로 해결, pypdf 표지 맵 오류 해결. DUE로 검색됐던 DIE5PT 매뉴얼 제외. 사용자 설정 저장/호출, 개정코드 날짜 해석, 실제 고객 후기/효과, 세부 SKU/일부 가격 조건 미확인. 후기/이미지/설명서 전문을 repo에 복제하지 않음.
- #12 실제 최신 조회(18:33 KST): open/updated_at 2026-10-04T08:19:49Z, 미체크9. 가상5/합성36 수량·세 제품군/직접 참조 준비 충족, R03~R08/R13 실제 실행·출력 연결/완주와 PR/PM 검수·병합·통합은 남음. 사용자 가상 예시 게시 금지 유지, 원격 변경 없음.
- 지지: 승인한 세 실모델에 대한 bounded 참고팩과 최소 출처·숫자 확인 완료, 기존 예시/코드 보존, 충족/미완료 명시.
- 지지하지 않음: 전체 JSON Schema·기존 검색 3질문·업로드/파싱/Agent 완주·전체 하네스 valid·수요/효과·PM/PR/전체 #12 완료. 코어 import jsonschema 없음과 phase2 과거 hash/merge 이력 진단은 이전 실제 실패로 유지.
- 종료 확인: git diff --check 공백 오류 없음, scripts/sync_agent_rules.py --check PASS. 다음 하나는 R03 실행 환경/연결 준비, 이번 범위 수집 종료.

### 신진하-E004-local — R03 환경·기존 경로 진단

- 관련 기록/담당/시각: 005-local / 신진하 / 2026-10-04T22:25:01+09:00.
- 근거 종류: 실행 지침/의존성·최신 GitHub main·Issue·PM 배정·코드 열람, 설치 환경 실제 probing/core import 실패, 기존 phase2 next/packet 실행. R03 연결/API 런타임 실행 아님.
- 원본/입력/출력: data/research/R03-fridge-20261004/의 environment-before.json(실제 command/argv/stdout/stderr/exit), case-input.json(냉장고 공식PDF 경로/원본URL/버전/페이지/해시), implementation-inspection.json(route15개), github-snapshot.json(최신Issue/main blob), phase2-readonly.json, r03-status.json. README에 사용법/단계별 미실행 사유.
- 실제 관찰: Python3.11 기준과 현3.12/3.10 불일치; 양쪽 jsonschema 없음, 선언/lock4.26.0 있음, 확인한 기존 venv/uv 없음. core import exit1/ModuleNotFoundError. 고정 PDF hash 일치. next/packet exit0. 업로드/파서 경로 없음; WorkspaceStore는 기획 입력/run snapshot 저장이며 PDF등록 아님.
- 최신 코드5파일 blob은 main과 local 동일. AGENTS782259e8498c3e97205d2ec6e2a31915a8daf8a8의 새 규칙을 읽음. online Project status는 uv와 로컬 project_report.py 부재로 미실행, Issue/main 읽기를 대체 성공으로 표시하지 않음.
- 설치/수정: 프로젝트 내부 uv·Python3.11·잠금 실행 의존성 설치 승인 요청 후 대기. 새 설치/전역 변경/공통 API-schema 수정 없음. #13 등록/텍스트PDF파싱/검증 저장/등록자료 조회와 PM 공통 편집 경계 조율이 필요하다고 먼저 설명.
- 지지: 누락 원인은 의존성 선언 문제가 아닌 잘못된 실행환경/미생성 프로젝트환경, 그리고 별도 문서 처리 구현 부재. R03 미충족/각 단계 미실행.
- 지지하지 않음: Schema PASS·원문 업로드/파싱/조회·출력 메타데이터 유지·전체 #12/#13·PR/PM 완료.

### 신진하-E005-local — CHECKPOINT 부분 전달·연결 및 평가 구분

- 관련 기록/담당/시각: 006-local / 신진하 / 2026-10-04T22:25:01+09:00.
- 사용자 원문과 해석은 006-local에 분리. 최신 인증 PM CHECKPOINT 원문은 https://github.com/jeongiryang/lg-ax-2026/issues/12#issuecomment-5979831712 와 R03 github-snapshot.json. 게시 전 보고 지시 유지.
- 입력: 실제 참고팩 reference-pack.json SHA256 11b52928b1be5e145a49327a704b9d62405e8d2272372075b54a9974d2ca9bb0, facts19/20/21(총60), sources12. 기존 원문/계약/자료5파일 보존.
- 실행: 기존 번들Python 표준 json/Path/hashlib로 실제 파일 재읽기. 모든 사실ID 고유성·출처ID 존재·동일 모델·public 성격·URL/출처 개정/시각 일치·위치/페이지 범위를 대조. ID/원문 연결 결과 traceability-check.json: 오류0/PASS. 이는 직접 참조 검사이며 JSON Schema/API 성공 아님. 연구 fact/source ID와 업로드 생성 canonical Evidence/document ID 구분, 후자는 null.
- 평가 구분: 기존 개발 입력·실모델 참고팩·R03 재현 입력은 개발용. data/evals JSON manifest inventory에서 독립자료 manifest0; private 전체 미조회. 테스트fixture를 독립실험으로 간주하지 않음. PM 최신 docs/pm/evaluation.md blob e108f1a15411efd1722cf3dadc97fbcfc54d634d 계약/조건 변경 읽고 여섯 유형·case/request/data/outputcontract·원본/canonical hash 요구를 readiness에 연결. 독립 자료/기대 대응·평가 결과·측정치는 아직 없음.
- 출력: data/research/P2-DATA-001-checkpoint-20261004/README.md, traceability-check.json, evaluation-readiness.json, partial-pr-description.md, delivery-manifest.json. 두 개인기록/근거와 실제팩/R03 진단은 로컬 동일commit 후보의 명시적 파일목록. 자기 파일/manifest에 자신의 hash 또는 commit SHA를 넣지 않음. 실제 commit receipt는 로컬 tmp에 별도.
- 지지: 세 실제품 참고팩 ID/출처/모델/각 출처 버전/위치 연결 오류를 발견하지 않았고 개발/독립자료의 범위와 부족이 명시됨. 부분 인수 후보와 재개 증거를 준비.
- 지지하지 않음: 독립자료 여섯 유형 준비 완료·독립성/실제평가·Schema/API/R03 완주·전체 #12·PR 게시/PM 검수·병합·통합. 설치 승인이 없어 실행 못한 부분은 숨기지 않음.

- 부분 묶음 최종 기본 확인: git diff --check 통과, sync_agent_rules.py --check 로컬 지침 바이트 일치 PASS, 전달 후보20파일 해시/JSON 읽기 오류0, 기존 자료/검색/계약5파일 SHA256 유지. 이는 R03/schema/HTTP 실행 검사가 아니다. 로컬커밋은 manifest의20파일만 대상으로 준비하며 원격 게시하지 않는다.

- 동일커밋 해시 대조에서 최초 Windows CRLF와 Git LF 차이를 실제 발견. .gitattributes의 LF 규칙을 놓친 생성 파일을 LF로 정규화하고 원래 수집 당시 해시는 verification.json의 line_ending_normalization 이력에 보존. JSON 내용/CSV 정보·원본 PDF/기존5파일은 유지. 최신 참고팩 SHA256는 cdbc8e8dbcacf6f95d219856ff48f827d9b23a06d0f72d9e7f94d7a0854c8f17이며 이전11b529... 값은 원래 Windows 바이트의 역사 값이다. 이 변경은 자료 의미/모델/기능 수정이 아니다.

### 신진하-E006-local — #12 계약 검사·부분 전달 재개 확인

- 관련 기록/담당/확인: 007-local / 신진하 / 2026-10-04 KST. 이번 코드검사 기준은5fa1a62273c5f699d0619c2a088a2f5a35c7a128. 이전 보고/사용자 붙인 설명은 역사 자료이고 현재 직접조회는 별도 기록.
- 실제 읽기/환경명령/입력/출력: checkpoint/runs/20261004T134134Z/의 remote-read-status.json, environment-check.json, run-context.json, execution-preflight.json, query-input.json, scope-and-manifest-check.json, run-result.json. 각 실행 경로·명령·stdout/stderr·오류와 code/자료/계약 SHA256 연결.
- 직접 관찰: HEAD/branch 일치, 기준20파일 기존해시 오류0, 이전4개 미커밋변경 보존. 기존5모델·36리뷰·42근거·실제참고3모델/60사실/12출처/차이2/미확인7 수량 재읽기. 확인한 Python3.12.14/3.10.2/3.12.0과 strict3.11 불일치, jsonschema 없음, venv/uv 없음. jsonschema는 이미 선언·잠금4.26.0. 대상venv Python -V는WinError2 파일부재로 시작실패.
- 최신 지침/12·13/PM CHECKPOINT/실행/평가 안내·schema/의존성 재조회. 이후README·코어/API4개 원격조회는404실패. main 최신코드전체를 이번에 읽었다고 주장하지 않음. 정확한 code_commit은로컬5fa1a62.
- 설치: 프로젝트 내부경로/3.11/uv/locked runtime+dev/간접의존성/무료·유료API없음 이유를 한 질문으로 제시. 아직 승인 없음, 새설치/전역변경 없음. 계약·회귀·HTTP조회는미실행이며 환경사전조건 실패와 #13 등록/파서 부재를 분리. 독립평가 여섯유형/기대대응은미완료, 평가정답튜닝혼입 없음.
- 부분 전달: 기존20파일을 기준으로 새실패/준비증거·명령별상태와 제목/본문/명시적목록 갱신. 게시제안은jeongiryang/lg-ax-2026 main←codex/data001-lg-sourcepack-20261004, 실제push/PR생성승인전 미실행. 전달commit이달라져도검사대상5fa1a62/각파일hash를유지.
- 지지: 최신직접환경/자료수량/기존변경보존 확인과 제한을 남긴 부분 전달준비.
- 지지하지 않음: jsonschema검사·회귀통과·HTTP조회메타데이터유지·R03완주·독립평가·#12전체·PR게시·PM검수/병합/통합.

- 007-local 현재 부분 전달 준비 확인: 새 code/data hash 고정·기존변경4파일 보존·로컬기본검사/next/packet/문서diff 확인은 prepublication-check.json에 실제argv/output/exit로 기록. 기존20파일+새run증거8파일 총28파일을전달후보로고정. 공통계약/회귀/API조회는미실행, 설치승인과원격게시승인모두미수신. 다음하나는설치승인후기존검사/조회실행. 실제PR/PM완료상태변경없음.

### 신진하-E007-local — 승인 환경의 기존 계약·조회 실제 실행

- 관련 기록: 신진하-20261005-001-local / 담당 신진하. 확인 시각: 2026-10-05 00:19~00:50 KST.
- 근거 종류: 직접 사용자 승인, 기존 코드·자료 읽기, 실제 설치·결정론적 계약 검사·HTTP 조회, 고정 코드의 fixture 계약 검사. 실제 판단 모델 실행 없음.
- 원본: data/research/P2-DATA-001-checkpoint-20261004/runs/20261004T151925Z/. 각 설치/검사 파일은 argv·stdout/stderr·exit를, HTTP 파일은 입력·상태·응답 hash·metadata 확인을 기록한다.
- 기존 검사 코드: 791c206338dc2786bb880bdd53d80f9d1c010767. 입력·코드 hash는 run-context.json. 최신 main cd3044f77760f0cf1dcaf8d9e97b13c826ae6b4a와 검사한 schema/API/자료/잠금의 일치는 latest-main-comparison.json. main 전체 회귀를 실행했다고 주장하지 않는다.
- 비공개 여섯 사례의 검사 코드는 고정 main CORE001 judgement_contract.py이며 평가 자료 metadata에 SHA256를 따로 기록했다. 자료·답안 원문은 private에만 저장했다.

| 확인 항목 | 실제 결과 | 증거 파일 |
|---|---|---|
| 환경 복구 | Python 3.11.17·jsonschema 4.26.0 import 성공 | environment-install.json, environment-ready.json |
| 계약·회귀 | 계약 PASS, 기존 회귀 170개 PASS | contracts.json, regression.json |
| 실자료·리뷰 연결 | Product 3건·출처 60항목·리뷰 36건 확인 | data-contract-audit.json |
| 기존 HTTP 검색 | 세 제품군·5통제 PASS, metadata 유지·원문 일치·동일 응답 | http-query.json |
| 하네스 | 초기 136오류 후 Git 이력 복구, valid=true/errors=[] | phase2-validate.json, phase2-validate-after-history.json |
| 비공개 평가 준비 | PM manifest 및 계약 기대 결정 6/6 일치, 개발 원문/ID 겹침 0 | evaluation-materials.json |

이 근거는 자료 계약·기존 합성 조회·부분 인수 준비를 지지한다. 실제 LG 문서 업로드/파싱/검색 등록, 실제 Agent 판단·세 제품군 전체 완주, 독립성·정답 타당성의 PM 확인·실제 평가·효과, PR/PM 검수·병합·통합 완료를 지지하지 않는다.

GitHub 커넥터의 이전·현재 주소 404를 보존하고 승인된 브라우저에서 최신 #12/#13/PM 지침 읽기 성공을 구분했다. 동일 저장소의 조직 이전 주소로 origin을 갱신했다. PM 원본 증거와 공유 코드는 수정하지 않았다. 사용자 선택에 따라 #13 구현은 하지 않았다. 실제 게시 승인은 별도다.

### 신진하-E008-local — 실제 설명서 등록·파싱·기획 입력·조회 연결

- 관련 기록: 신진하-20261005-002-local / 담당 신진하 / 2026-10-05 KST. 사용자 “1,2,3단계 지금 실행”에 따라 최소 문서 처리까지 수행했다. 이전001/E007의 #13 제외는 이 범위에 한해 변경했고 게시 보류 유지.
- 지침/코드: main6b9dbe9298cd4e822132e617eaf30262d72d77e8, 이전자료7cc25fb, 병합base13b558c+실행 JSON의 file SHA256. 최신 PM #12 scope 댓글 https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5981905359. 최종 로컬 전달 commit의 tree/file 해시는 Git 제외 tmp receipt로 따로 대조한다. 원격 CI·PR·PM 검수는 없음.
- 원본/입력: 승인된 T876MEE1H1·DUE6BGL2E·MW23FDI 공식 PDF3건. URL·확인시각·전체SHA는 download.json, 개정/적용조건/선택 위치는 data/document_plans/lg-three-models-20261005.json. 개별 Product/Feature/Evidence는 기존 canonical schema를 재사용했고 합성전용 Manifest는 변경하지 않았다.
- 환경: 승인한 기존3.11.17/.venv·jsonschema4.26.0과 이미 있는 번들3.12.14/pypdf6.10.0. 추출은 별도 자식프로세스이며 핵심 서버3.11 유지. 새 설치·유료API·GPU·전역 변경 없음.
- 실행: scripts/verify_lg_document_flow.py가 원문을 localhost/Bearer HTTP POST로 등록하고 실제pypdf 파싱/계약검증/저장 후 GET 검색·Evidence·metadata·원문 반환을 확인했다. 명령·입력/응답hash·상태·통제는 flow-command.json/http-flow.json. 원본 PDF를 되돌려 받은 SHA가 업로드와 같고 서버 종료 후 새 Repository에서 조회하여 저장을 확인했다.
- 결과: HTTP33요청/60검사 PASS. 공개 실자료 Product3·Feature9·Evidence10, 리뷰0. 모델·문서ID·근거ID·page/section·버전·public 유지. 문자위치와 짧은 인용이 원문과 정확히 같은지 대조. 원문 hash불일치·다른 모델/버전·잘못된ID·무인증·Origin은 거부, 정상 빈조회는 성공빈값.
- 계획 입력: 최신 build_planning_input의 실제 실행은 planning-inputs/3파일·planning-contract.json. 동일 Product/문서 버전의 정의 기능/근거 전부 포함 및 다른버전/다중모델 거부 확인. 실제AI 판단·불편/콘셉트 생성은 없음.
- 최소 수치/원본: original-number-check.json에서3단계/30초/출력200~1000W와5선택값의 원문위치hash 확인. 표지3·식세p57·전자p37은 기존PDFium 렌더링 원본 대조. 정확한냉장고모델은 공용표지에 없다고 명시하고 제품연결로적용확인. OCR없음.
- 검사: 최신코드전체회귀382개(신규8포함) PASS, 계약/규칙동기화/phase2/기존하네스/MCPstdio PASS. 각JSON에argv/exit/stdout/stderr와시험파일hash. Ruff초기4지적및WindowsSQLite핸들/시험fixture오류를수정한이력은실패기록에남긴다. 원본clone소유권검사실패는전역설정변경없이정식읽기경로로HEAD/4파일hash재확인.
- 데이터 구분: 개발자료와기존합성5/36/42 보존, 실제60항목/출처12/차이2/미확인7 유지. public DocumentDataset과합성DemoDataset분리. 독립평가6유형은이전private준비/PM미확인;이번답안읽기/튜닝없음.

이 근거는 설명서의 실제 등록→파싱→검증→저장→조회와 세 제품군 입력 계약을 지지한다. R03 전체 CSV/명세/작업실통합, R04/R13 실제 리뷰 불편 출력, R08 실제AI세제품완주, 독립평가/수요/효과/PM인수·검수·병합·통합·#12전체완료를 지지하지 않는다. 원문PDF/전체추출/이미지/DB/토큰과새가상/평가답안원문은전달제외.

### 신진하-E009-local — CSV 원문 연결·실모델 작업실 조회·평가 인수metadata

- 관련기록/담당/확인: 신진하-20261005-003-local / 신진하 / 2026-10-05 KST. 원본코드merge78ab18f, upstream07be0aa. 새코드/자료SHA는 stage345/checks.json, 전달commit은별도로컬receipt에서동일hash 확인한다. 이전2fb3e3e/E008 결과와구분한다.
- 근거종류: 직접사용자지시/선택, 저장소·브라우저읽기, 실제CSV/HTTP/API/SQLite실행, 결정론적계약/회귀검사. 실제AI·독립평가 실행아님. 단계7은PM역할이고매PR게시전사용자확인이필수다.
- 원본/재현: data/research/P2-DATA-001-stage345-20261005/README.md, execution-preflight.json, connections-results.json, checks.json, evaluation-intake-metadata.json, owned-server-cleanup.json. 각argv·시간·입출력hash·status·code자료hash를유지한다. 전체응답/CSV원문/DB/token/원본PDF와평가정답은private.
- CSV: 기존합성5모델/36리뷰/42근거를그대로재사용했다. privateCSV는기존JSON파생전송입력으로과거CSV원본복구가아니다. 실제업로드/표준csv파싱/동일원문·모델·버전·synthetic·행·sourceID/EvidenceID 검증→저장→조회→재시작 유지. 없는실제LG고객리뷰를대체하지않는다.
- 실제3모델: 전용DocumentDataset adapter를기존작업실서버의trusted evidence_store 주입점에연결했다. 내부manifest는버전metadata이며합성DemoManifest/공통Schema정책수정이아니다. 실제3프로젝트/동일모델버전전체정의Feature/Evidence입력·근거조회·교차모델/버전차단·snapshot재시작확인.
- 실제관찰: 새HTTP66요청/70검사 PASS와신규경계5개, 사용자실행환경전체395회귀/계약/규칙/phase2/기존하네스/MCPstdio/Ruff PASS. 초기snapshot키오류51검사기록과샌드박스회귀2개실패/사용자재실행은보존한다. 초기실패를현재성공으로덮지않는다. 일반웹build/e2e/원격CI는이번미실행.
- AI: 승인된Python3.11.17/jsonschema4.26.0 정상, 모델설정4개부재·로컬문서화2포트거절. 세실행은failed/INVALID_ARGUMENT 기록저장, model_calls0. HTTP201·입력계약·fixture성공을실제AI성공으로부르지않는다. PM문의실제고정URL: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982703508 . 답변/기존연결/GPU점유확인은남았다.
- 평가: PM현재manifest parser로6유형/파일/hash검사, 개발ID/동일text 겹침0. expected-answer바이트hash만기록,개발에내용읽기/튜닝없음. 정답타당성/의미상독립성/실제평가·강한기준선비교는미확인이다. 동일text0은독립성입증이아니다.
- 최신PM인수배정: 브라우저 https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935 MINIMUM-HANDOFF/10월5일18시기한 확인. model-pairs의실3모델input/dataset쌍은model-pair-contracts.json에전체정의scope일치/원본hash로연결했다. private평가ZIP13파일/원래바이트 대조는private-evaluation-delivery.json의hash로연결하고sent_to_PM=false로둔다. 준비를PM전달/인수로승격하지않는다.
- 보존/제한: 실모델60항목/공식9·SSG3/차이2·미확인7, Product3/사례Feature9/Evidence10와이전PDF33요청/60검사를유지한다. 실제고객리뷰0/OCR0. 일반명세JSON/임의문서등록/#13전체는미구현, R03전체인정은PM검토대상이다.

이근거는승인한자료의실제등록/파싱/계약/저장/조회와작업실자료연결을지지한다. 실제판단출력의리뷰·기능추적(R04/R05/R06/R13), 세제품군AI완주(R08), 실제수요/효과, 평가완료, PR게시/ACCEPTED/PM검수·병합·통합/#12전체완료를지지하지않는다. 다음하나는PM기존모델연결확인후냉장고실제실행근거대조다.
