# DATA 네 후속 작업 — 새 실행과 남은 조건

확인일: 2026-10-06T21:57:37.933694+09:00 / 담당 신진하(@ginaginaring). 사용자 지시: 운영 자료·날짜팩·검색 비교·독립 평가 준비를 실행하고 PR로 제출. 자동화 OFF 유지, 운영 배포·재시작·설정 변경·예약 조작·제품 AI 생성 없음.

|작업|이번 실제 결과|완료 여부 / 남은 조건|
|---|---|---|
|#13·#16 운영 자료 비교|승인 문서에 있는 주소 6개 GET. 로컬5 연결 거절(10061), 외부health HTTP502. 운영 버전/ID/원문 해시 응답 없음.|조회 시도 완료, **운영 자료 일치 여부 미확인**. PM의 승인된 읽기 연결 또는 원본 snapshot 필요. 서버 OFF·자료 불일치로 추정하지 않음.|
|#16 날짜팩 운영 확인|PR194 병합 직접 조회. 원 날짜 미상/PM 구성날짜31/DATA 구성날짜9의 dataset·sidecar·date source 8파일을 고정SHA와 새 대조, 모두 일치.|정적 자료 대조 완료, **날짜·주제 승인 및 실제 운영/API·작업실·WEB의 같은팩 확인 미완료**. 기존108바인딩/15query/40거절/HTTP46은 PR194의 이전 실행이며 이번 재실행으로 계산하지 않음.|
|#14 검색·재정렬|같은 공식 원문21·개발 질문15·3방법·5회 반복 = 새225행, 실패0. 근거630출현 모델·버전·원문 해시 대조PASS, 버전없는15회는 빈 결과/확인요청.|**새 측정 완료**, 기존11문항 전체 점수는 FR-01 정답근거 PM 확인 전 null. API 검색이나 전체 Agent 의미 품질 검증은 아님.|
|#15 독립 평가 준비|기존 비공개 인계8입력이 공개heldout7파일과 중복이라는 고정 보고/blocked 접수 보존. 이번 공개 core-contract6입력의 development대조는 중복0. 공개PM manifest의6유형 메타데이터 확인, CORE 의미기준 인계 확인.|**독립 평가 미완료**. 새 공개6대조는 비공개 인계8의 처분/교체를 대신하지 않음. PM 자료 승인·검토자·비공개 경로 및 외부 전체입력 Agent/기준선 결과·독립 채점 필요.|

## 검색 결과 — 개발 진단만

FR-01은 기존 F10 ID가 현재 선반 들어올리기 문장이고 질문은 식품 제거이므로 F10-FOOD 제안을 별도 보존한다. 기존 gold를 수정하지 않았다. 아래 정확도 분모는 나머지 **서로 다른 질문10개**이며 독립 평가 점수나 실제 고객 수요 근거가 아니다. 처리시간 분모는 각 방법에서 근거있는11질문×5회 =55성공 시도다. 냉간 적재/색인 시간과 no-gold20회는 분리했다.

|방법|Hit@1(10질문)|Recall@3|MRR@3|중앙 처리시간|p95|전체 시도/실패|
|---|---:|---:|---:|---:|---:|---:|
|BM25|70%|85%|0.800|0.19 ms|0.27 ms|75 / 0|
|BGE-M3|70%|100%|0.833|390.29 ms|993.78 ms|75 / 0|
|BGE-M3 + 재정렬|70%|90%|0.783|6621.96 ms|13116.40 ms|75 / 0|

모델·버전 혼입률0은 사전 필터 정책의 결과다. 재정렬은 이번 작은 자료에서 검색보다 Recall@3/MRR@3가 낮았고 느렸다. 새 운영 도입·우월성·전체 정확도를 선언하지 않는다. 버전 누락 이외의 no-gold3질문의 의미상 거절/질문/미확인 답변은 생성하지 않아 미검증이다.

## 정확한 버전·재현 조건

- 자료/기존BM25 코드 기준 main: `9cd2d56be52588764c18c109c9ffca4c104bd48c`. 실제 실행 코드 commit: `d728d786a057ab6c3fccb1b97534653bcdcf22ea`. 결과/인계 commit은 이후 별도이므로 실행판과 구분한다.
- 자료: `lg-manual-scope-20261006.3-pm-intake`, 원문21의 UTF-8 문장·모델·문서 version은 인수 dataset와 동일. [원문 위치·source ID·URL·PDF pin 연결](retrieval-provenance.json). PDF 해시는 기존 인수 선언값이며 이번 새 다운로드 검사는 아님.
- BGE-M3 `5617a9f61b028005a4858fdac845db406aefb181` / reranker `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, 기존14파일 원바이트 해시 핀 대조. 설치 승인, Python3.11.17/torch2.8.0+cpu/transformers4.57.1과 실제 패키지 전체 버전은 [환경](environment.json).
- CPU4 / float32 / CLS L2 정규화 / embedding batch8 / reranker top10 / 최대256, 실제 token 길이 검증 무잘림. 모델 생성0/유료 API0/OCR0, 검색모델 forward는 [실제 실행](execution.json)에 따로 계수했다.
- [격리 확인](container-proof.json): image 고정, root 읽기전용, source와 BGE2폴더 읽기전용, 출력만 쓰기, network none, 인증/호스트.git/Docker socket 비마운트. 같은PC에 실행중 Docker0개임을 시작 전 확인, 중앙 예약 조작0. 예전 protocol의 PM gold/중앙 실행조건 완료를 대신하지 않고 사용자 승인한 로컬 진단 측정으로 수행했다.
- 원 설치 요구 목록과 Dockerfile은 [environment/](environment/). Linux 추가 전이 의존성 hf-xet은 실제 설치 버전을 environment.json에 기록했다. 전역 Python/PATH 변경 없음.

## 실행·출력·근거

|단계|명령·입력|출력·판정|
|---|---|---|
|환경 설치|기존 고정 validator image에서 `uv pip install` historical requirements, 공식 CPU/PyPI index|build exit0, 실제 고정패키지 버전 대조PASS; 유료API 없음|
|운영 조회|문서상의 기존 health/bootstrap/products/projects에 GET6, token0|[조회 원 기록](runtime-get-results.json). HTTP 응답없음5/502 1, 원문 버전/ID/hash null|
|검색 실행|`python -B /workspace/run_retrieval.py --out /artifacts --code-version d728d786a057ab6c3fccb1b97534653bcdcf22ea`; 답안없는 원문21/질문15|[원 시도225](attempts.jsonl), [CSV](retrieval-attempts.csv), [로그](retrieval-execution.log), [token길이](tokenizer-lengths.json), exit0/OOM false|
|결과 확인|별도 network-none container에서 `python -B /workspace/score_retrieval.py`; 모델 가중치 미마운트, 기존 공개개발 gold는 이 단계만|[진단 점수](retrieval-summary.json), [무결성 검사](result-integrity.json):225시도/45그룹/630근거 대조PASS. 독립 평가 아님|
|날짜·평가 준비|고정Git 원바이트와 PM 공개 pin 읽기, 공개 입력6과 manifest 메타데이터만 대조|[날짜 상태](dated-pack-status.json), [독립 준비 상태](independent-readiness.json). 비공개 답안/리뷰 원문 새읽기·게시 없음|

[준비 실패](preflight-failures.json)는 설치 폴더 untracked, Git helper의 status 앞공백 제거, GitHub 신원검사 반환값 해석으로 준비검사가 잘못 거절된 3건이다. 설치 폴더만 로컬 ignore 처리했고 경로검사는 파일명 목록으로 수정했다. GitHub의 정상 신원검사 함수는 반환값 없이 통과하므로 비교식을 제거했다. 실제 영역 위반·계정 불일치·새 모델 재실행은 없었다. 원 실패는 보존했으며 실제225시도 실패와 섞지 않았다. `torch_dtype` deprecation 경고는 실행 로그에 보존했으며 실행 실패가 아니다.

## PM에게 필요한 결정과 다음 하나

1. 운영 비교는 승인된 읽기 연결/버전별 원본 snapshot을 PM이 전달하면 같은 version/source/model/hash 표에 실응답을 채운다. PM controller token을 작업실 viewer token으로 쓰지 않는다. 조회 불가를 동일/불일치로 추측하지 않는다.
2. 날짜·주제 분류/운영팩을 PM이 승인하고 같은 자료를 운영 collector·WEB에 연결한 뒤 실제 동일 ID/분모/원문/내보내기를 확인한다. 구성 날짜는 실제 리뷰 게시일·불만률이 아니다.
3. FR-01 F10 또는 F10-FOOD 정답근거를 PM이 판정하면 보존한 순위225행을 재채점한다. 모델 재실행이 자동으로 필요하지 않다.
4. #15 중복 인계 자료를 교체/진단용으로 처분하고 독립 검토자·비공개 수신 경로를 정한다. CORE의미기준은 이미 인계됐으므로 다시 미수신이라고 하지 않는다. 중앙⑤가 동일 전체입력·예산의 Agent/기준선을 실행하고 독립 검토자가 원답/판단을 채점한다.
5. 최신PM R4의 PR190 보류/질문 유실 P1은 CORE11/공통연결 및 WEB25와 별도 조율할 작업이다. 이번 네 자료 작업에서 공통판단 코드를 수정하거나 대신 통합완료라고 하지 않는다.

**다음 작업 하나:** PM이 전달한 승인된 운영 읽기 snapshot/연결로 PR183 인수 version/source ID/model/문서 version/원문 hash를 실제 응답과 대조한다. PM 검수·실제 병합/운영 통합·#12 등 부모 Done은 이번 부분 PR로 처리하지 않는다.

## 게시 전 기존 검사·평가 인계

[기존 검사7개](existing-checks.json)는 고정 snapshot `6744985c1a2d9d49a32fe7a76866c93ac01444c4`에서 별도 인증·네트워크 없는 container로 exit0이다. 계약48정의/가상5모델·36리뷰·요청3 검사, AGENTS/CLAUDE 바이트 일치, 개인 기록 이관의 저장 바이트 보존, phase2 next/003·004·005 packet 읽기를 포함한다. next/packet은 읽기이며 수행·채점·정식 상태 변경이 아니다. Git을 마운트하지 않아 로컬 이관검사의 Git 원commit 결속 검사는 이 명령에서 실행하지 않았고 PR의 실제 CI gate로 분리한다.

[버전 경계](version-boundary.json)는 고정 원문21/질문15/기존BM25 source가 새 artifact commit에도 그대로임을 확인한다. 검색 실행판d728과 결과/검사판674를 구분하며, 다른 코드 버전의 성공을 현재 모델 실행처럼 표시하지 않는다.

CORE가 인계한 의미 기준을 여섯 유형의 [독립 인계 체크표](independent-handoff-checklist.csv)로 연결했다. 특정 사례의 새 정답·점수·가중치가 아니라 검토해야 할 축이며, 미확인 수신자·원문/답안을 대신 채우지 않았다. 비공개 자료는 이번 PR에 포함하지 않는다.
