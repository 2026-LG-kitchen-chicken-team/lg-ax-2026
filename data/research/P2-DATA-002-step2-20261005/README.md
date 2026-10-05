# #13 2단계 — 기존 등록 경로에 시험 입력 연결

상태: **2단계 로컬 등록·보존 개별 검증 완료. #13 공식 pending 유지.** 기록 신진하-20261005-003-DATA002-STEP2 / 근거 신진하-E009-DATA002-STEP2. 담당 신진하, 수행 Codex 현재 대화.

## 요청과 해석

사용자 원문: “그럼 진행해 그다음단계 그리고 #13이 뭐하는건지도 요약해줘 중,고등학생도 알기쉽게”. 이전 조건인 정이량 지시 우선·모르는 사항 질문·하네스 사용 허용을 유지한다.

AI 해석: #13 2단계 문서 등록을 실제 수행한다. 최신 GitHub와 기존 구현을 먼저 확인하고, STEP1의 합성 CSV 36건 및 공식 PDF 한 건을 기존 저장 규격에 연결한다. 공통 API/Schema 변경·전체 #13 완료·새 게시 요청으로 확대하지 않는다.

## 확인과 결정

- PM 최신 MINIMUM-HANDOFF: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935
- #13 담당·R03/R04/R05/R06/R10/R13·pending·선행 DATA001을 확인했다.
- 이번에 별도 작업 공간의 [PR #69](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/69)와 004-handoff/E010-handoff를 읽었다. 기존 문서/PDF·합성 CSV 등록 코드를 발견했다. 고정 head `2691ad194be9f0f1c85963ad27ac60626d888738`을 재사용하고 새 등록 시스템을 중복 구현하지 않는다. 해당 PR은 읽기 확인 당시 Open/PM 검수 대기이며 승인·main 병합으로 간주하지 않는다.
- origin/main `671ec2bf019806f9ab9103b4a41dc4a4ab709a3a`의 지침·작업실 규격을 읽었다. 현재 clone HEAD `7cc25fba66e4d0f4a19ef9eebbaa9268937ce1c4`와 구분하며 fetch만 수행했다. 파일·이력 병합/checkout·원격 게시 없음.
- CSV 열 순서가 STEP1과 기존 업로드 규격에서 다르다. 원래 STEP1 파일은 보존하고 기존 serializer로 변환한 transport가 같은 리뷰/근거인지 대조한다. source_id·model_id·version·text·locator·evidence_id를 바꾸지 않는다.
- 등록 함수의 내부 파싱·검증은 기존 동작을 그대로 수행한다. 이는 등록 검증에 필요한 제한된 파싱이며 임의 문서/OCR·전체 3단계 또는 #13 전체 완료로 확대하지 않는다.

## 예정 행동과 완료 기준

1. Git의 고정 소스 스냅샷을 임시 경로에 추출하고 실제 import 경로·파일 해시를 기록한다.
2. 신뢰된 문서 plan과 기존 CSV transport를 준비한다. 원본/DB/토큰/전체 응답은 Git 제외 private 실행 폴더에만 둔다.
3. 두 loopback 서버에서 등록→메타데이터/원본 재조회→동일 파일 재등록→서버 재시작 후 재조회를 실제 수행한다.
4. 잘못된 문서 ID/원본 변경/모델·버전 변조와 인증·Origin 오류를 확인한다. 누락·교차 scope는 실패로 구분한다.
5. 기존 계약/하네스/지침·개인 기록/근거를 확인하고 결과를 연결한다.

등록한 두 입력의 원문 해시와 ID/모델/문서 버전/출처 성격을 재조회에서 보존하고 재시작 후에도 동일하면 이번 단계의 개별 검증을 마친다. 정식 의존 해제와 PM 검수·병합·통합은 별도다.

## 실제 결과

고정 PR69 코드를 임시 스냅샷에서 실제 import하고, 별도 loopback 포트 두 개에서 CSV·PDF 등록 서버를 실행했다. Python 3.11.17과 기존 번들 pypdf를 사용했다. 새로운 등록 코어/API를 작성하지 않고 입력 연결·재현 스크립트를 추가했다.

| 입력 | 실제 등록 기록 | 검증 |
|---|---|---|
| 기존 합성 CSV 36건 | REVIEWS-CSV-v1.0 / 5모델 / 문서 1.0 / synthetic | 메타데이터·원문 해시·재등록·서버 재시작 후 같은 원문/기록 |
| 공식 냉장고 PDF 1건 | F-M / T876MEE1H1 / MFL71401557 Rev.00_032526 / public | 원본 40쪽 보존, 19쪽의 한 근거 연결·메타데이터·재등록·재시작 후 같은 원문/기록 |

PDF 근거 DATA002-FM-P19-SHELF-01은 이번 개발 plan으로 **로컬 등록한 근거 ID**다. 전역 ID 채택이나 PM 인수가 아니다. 해당 기록은 선반 주의 문구만 포함하며, 기능 지원 판정·특정 모델 옵션·고객 불편 빈도를 만들지 않았다.

최종 `verified` 실행: **실제 HTTP 20요청, 35검사 PASS**. 변조된 CSV 모델/버전, 다른 문서 ID, PDF 바이트 변경, 잘못된 인증과 브라우저 Origin을 거절했다. 누락 scope는 신뢰된 서버 plan 생성에서 거절되며, 사용자용 메타데이터 입력 API가 새로 구현된 것은 아니다. 기존 등록/CSV 경계 fixture 시험 8+5건, 자기 스크립트 Ruff·기존 계약·지침 일치·phase2 무결성·공백 검사도 통과했다. 실제 모델 호출 0, 독립 평가 실행 0, OCR 0. 만든 서버 프로세스는 모두 종료했다.

## 실패와 수정 이력

1. `initial` 실행의 PDF 등록은 SOURCE_MISMATCH로 실패했다. STEP1의 pdfplumber 기대 문장은 한 줄인 반면 기존 pypdf 추출은 문장 중간의 줄바꿈/공백을 보존했다. 원본 내용·해시·STEP1 결과를 바꾸지 않고, 같은 단어로 구성된 유일한 원문 span을 찾아 그 정확한 공백/줄바꿈을 등록 plan에 사용했다. 두 텍스트 해시와 실제 파서의 원문 문자 범위를 결과에 연결했다. 초기 실패와 당시 실행 스크립트는 보존했다.
2. STEP1 CSV의 열 순서는 기존 strict 업로드 규격과 달라 PARSING_FAILED로 거절됐다. 기존 serializer로 만든 transport의 36개 행 사전이 STEP1과 모두 동일함을 확인했다. 원본 STEP1 SHA-256 `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9`, 변환본 `64e83d42c65b1af18040c6a4cdac9a7f6b14fca63041005f6d79f6c9faaec4ab`. 헤더 순서만 달라졌고 리뷰/모델/버전/ID/원문 행은 보존했다.
3. `aligned` 실행 35검사 통과 후 스크립트 import 순서의 Ruff I001 두 지적을 수정했다. `verified`에서 최종 스크립트를 다시 실행해 같은 35검사가 통과했다. 각 run의 스크립트 원본·해시를 따로 보존했다.
4. 최신 Project 상태 CLI는 실행 프로그램 부재 WinError2로 실패했다. 설치/권한 우회 없이 인증 브라우저에서 #12/#13·PM 지시·PR69와 기존 #12 ACCEPTED 수신증을 확인했다. 이 대화가 새 상태 보고를 전송하거나 Project를 갱신한 것은 아니다.

## 증빙과 재현

- [run_registration.py](run_registration.py): 고정 기존 코드와 STEP1을 연결해 실제 등록/재조회를 수행하는 스크립트.
- [runs/verified/registration-checks.json](runs/verified/registration-checks.json): 20 HTTP 요청·35검사·코드/입력 해시·등록 메타데이터·보존 대조·서버 종료.
- [runs/verified/trusted-document-plan.json](runs/verified/trusted-document-plan.json): 명시적 단일 모델/버전·원본 SHA·19쪽 근거의 제한된 개발 plan.
- [runs/initial/registration-checks.json](runs/initial/registration-checks.json): 초기 PDF 실패. 각 run의 executed-runner.py.txt는 당시 실행한 스크립트 원본이다.
- [runs/final/final-checks.json](runs/final/final-checks.json): 실제 명령/출력/exit와 fixture·Ruff·계약·하네스·지침 검사. 상태 CLI 실패는 별도로 구분했다.

저장소 루트에서 새 run-id로 실행한다. 원래 PDF 경로와 Git의 고정2691ad1 이력이 필요하다. 이미 있는 run-id는 덮어쓰지 않는다.

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step2-20261005/run_registration.py --run-id reproduce-01
```

실제 PDF/CSV 원본·SQLite·토큰·전체 응답·전체 추출문은 Git 제외 `private/data002-step2/{run-id}/`에 저장한다. 코드 스냅샷은 `tmp/data002-step2-source-{run-id}/`에 보존하며 checkout/merge·기존 파일 교체를 하지 않는다. 소스의 PR head·파일 해시와 현재 clone HEAD를 구분한다. 공통 Schema/API·하네스 task·기본 합성 자료와 STEP1 해시를 유지했다.

## 쉽게 설명하는 #13과 다음 단계

#13은 자료를 정리하는 작은 도서관과 같다. 설명서·리뷰를 받으면 제품 이름과 설명서 버전을 붙여 보관하고, 내용을 읽어서 필요한 문장을 찾은 뒤 “어느 제품의 어느 설명서 몇 쪽/몇 행”인지 알려준다. 다른 제품이나 다른 버전의 내용을 섞지 않게 하는 것도 이 작업이다.

이번 2단계는 접수·보관·다시 꺼내기의 확인이다. 기존 등록 경로가 내부적으로 읽은 PDF 한 문구와 CSV 36건의 제한된 파싱도 수행했다. 다음 3단계에서는 등록된 입력을 기준으로 페이지/행을 보존하는 추출 결과와 누락·중복·모델/버전 연결을 본격적으로 대조한다. 임의 문서/OCR·전체 검색/Agent 연결·세 제품군 완주 및 PM 검수·병합·통합은 남았다.

- [x] 최신 PM/기존 PR·코드·담당 경계 확인 및 중복 구현 방지
- [x] 명시적 입력 scope와 손실 없는 CSV 변환·PDF 원문 span 연결
- [x] 실제 등록/재조회/재등록/재시작 보존·오류 차단 검사
- [x] 실패/최종 코드/실행 로그·개인 기록/근거 보존
- [ ] 일반화된 파싱·검증 저장·검색/원문 연결과 세 제품군 전체 실행
- [ ] 선행 #12 인수·#13 공식 검수/병합/통합 완료

현재 사용자가 직접 해야 할 일은 없다. 새로운 공통 계약/API 결정이 필요하면 구체적인 접점과 영향 범위를 확인해 질문한다.
