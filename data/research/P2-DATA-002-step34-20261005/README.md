# #13 3·4단계 — 등록 자료 추출과 검증·저장

상태: **승인된 시험 입력 범위의 3·4단계 실행 검증 완료. #13 공식 pending 유지.** 담당 신진하 / 현재 LG Kitchen #13 대화의 Codex.
기록 신진하-20261005-004-DATA002-STEP34 / 근거 신진하-E010-DATA002-STEP34.

사용자 원문: “그럼 #13에 대해서 하자 3~6단계에서 지금 3,4단계만 실행하자”.
AI 해석: 기존 STEP1·STEP2의 CSV36건/PDF1건을 재사용해 3단계 추출 원문/페이지/행 대조와 4단계 누락·중복·모델/버전 혼입 거절 및 저장의 원자성을 실제 수행한다. 검색 연결(5), 세 제품 전체 흐름(6), 게시·검수·병합(7)은 실행하지 않는다.

## 작업 경계와 시작 기준

- 최신 main 고정 commit `f88dd7ac6448ef863a8cdc418804b7838eff0e24`의 기존 파서·등록·저장 코드를 별도 tmp 스냅샷에서 재사용한다. 현재 checkout이나 기존 코어/공통 API를 덮어쓰지 않는다.
- LGAX #12의 `codex/data001-stage45-citations-20261005`에서 진행 중인 기능 인용·자료팩·평가 입력 수정은 제외한다. PM의 SOURCE_CHANGED 코드도 중복 수정하지 않는다.
- STEP2의 검증된 private 등록 DB/원본을 새 private 작업 폴더로 복사한 뒤 최신 코드로 재개한다. 기존 실행 증거와 실패/원문을 수정하지 않는다.
- CSV는 기존 합성 자료 전용 엄격한 transport(36건/5모델/1.0)이다. 공개 PDF는 T876MEE1H1 공용 설명서 40쪽과 19쪽 주의 문구 한 건만 등록돼 있다. 공용 설명서의 모델별 기능 적용을 판정하지 않는다.
- PDF 전체 추출문과 CSV·DB·전체 응답은 Git 제외 private에 보관한다. 검토용 결과에는 해시·페이지/행 위치·오류·통과 여부만 남긴다.

## 완료 기준

1. 실제 파서가 CSV36행과 PDF40쪽을 읽고 STEP2 등록된 원문/ID/모델/버전/성격 및 selected 원문 문자 범위와 일치한다.
2. 승인 입력에서 파생한 누락·중복·다른 모델/버전/행/근거 변조가 기존 파서/API/계약 검증에서 거절된다. 어떤 검사 경계인지 명시한다.
3. 실패 뒤 기존 정상 등록·원본이 보존되고, 새 잘못된 PDF 등록은 DB/원본에 부분 저장되지 않는다. 재시작 후에도 정상 기록과 해시가 같다.
4. 자기 스크립트와 기존 계약/지침/하네스 검사를 실행하고 의도·실제 증빙·제한을 개인 기록과 연결한다. #13 공식 완료/PM 검수를 대신하지 않는다.

## 실제 실행 결과

기존 코어를 수정하지 않고 최신 main의 고정 스냅샷을 사용했다. STEP2의 등록·원본을 새 private 폴더에 복사해 재개한 뒤, 별도 빈 저장소에도 실제 파싱/계약 검사 후 새 등록을 수행했다. 파서를 mock하거나 고정 성공 응답으로 대체하지 않았다.

| 범위 | 실제 결과 |
|---|---|
| 3단계 CSV | 36건을 기존 파서로 다시 읽고 각 리뷰 ID·근거 ID·원문·행2~37·모델·버전·자료 성격을 승인 자료/근거와 대조했다. 전체 기존 dataset도 동일하다. |
| 3단계 PDF | 원본 40쪽을 pypdf로 새로 추출했다. 등록된 19쪽 주의 문구의 페이지·시작/끝 문자 위치·텍스트 해시가 실제 추출문과 정확히 일치했다. 전체 추출문은 private에만 보관했다. |
| 4단계 오류 차단 | CSV17종 변조가 실제 HTTP에서 PARSING_FAILED로 거절됐다. 누락 필드·중복 ID·행/모델/버전/성격/근거 혼입·행 수 변경을 포함한다. PDF 잘못된 원문/형식/자료 ID도 거절됐다. |
| 4단계 저장 | 잘못된 PDF 페이지0/41·다른 페이지·없는 인용은 실제 추출 후 거절됐고 DB/원본이 부분 저장되지 않았다. 실패 뒤 정상 CSV/PDF의 기록·해시가 보존되고 서버 재시작 후에도 동일했다. |
| 빈 저장소의 새 저장 | PDF·CSV를 새 SQLite DB에 각각 실제 등록해 논리적 기록1건·원문 보존·기존 등록 결과와 동일성을 확인했다. 새 인스턴스로 재개한 뒤 검증된 근거도 보존됐다. |

- `run_steps.py`: **130검사 PASS**, 기록한 검증 HTTP29요청, 서버4프로세스 종료. `port-cleanup-check.json`에서 두 포트의 실제 연결 거절을 추가 확인했다.
- `verify_fresh_storage.py`: **8검사 PASS**. 합계 **138개 실행/검증 검사 통과**다. 등록·검증을 수행한 개수이며 시장 수요·검색 성능·Agent 판단 점수가 아니다.
- 기존 계약 검증·AGENTS/CLAUDE 일치·phase2 무결성·자기 Python 스크립트 Ruff·공백 검사 PASS. 기존 STEP1/STEP2와 P2-DATA-001/002 task·합성자료·계약 해시가 보존됐다.
- 기존 전체 회귀485검사에는 웹 CI API 준비/정리 검사2개 실패가 있었다. 원래 실패 결과를 `final-checks.json`에 보존했다. 같은 고정 코드를 단독 API 준비 진단으로 실행한 `ci-probe-diagnostic.json`은 PASS였다. 해당 두 검사의 독립 재검사에서는 정상 API 준비1검사가 PASS, 실패 경로의 종료 정리1검사가 FAIL이었다(`failed-checks-retry.json`). 원인은 확정하지 않았고 담당 범위 밖의 PM 공통 CI 코드는 변경하지 않았다. 전체 검사 성공으로 바꾸지 않는다.
- 온라인 상태 CLI는 gh 실행 파일 부재로 WinError2를 반환했다. 인증 브라우저에서 #13 Open·담당 ginaginaring·Project Todo·선행 DATA001·미체크 완료 조건을 확인했다. 조회 실패와 브라우저 조회를 구분하며 온라인 상태를 변경하지 않았다.

## 검사 경계·한계

HTTP 오류 차단, 실제 PDF 파서의 오류, 공통 entity 검증, trusted 서버 설정 검사를 결과 JSON의 `boundary`로 구분했다. 서버 plan의 필수 항목 누락은 KeyError/ValueError 등 설정 검증이며 사용자용 메타데이터 API의 친절한 오류를 새로 구현한 것이 아니다.

CSV는 기존 36건과 정확히 같은 자료만 받는 제한된 경로다. 임의 리뷰 수집/일반 CSV 자동 추론을 완료했다고 표현하지 않는다. PDF 전체를 읽었어도 등록한 근거는19쪽 한 문구이고 기능 목록은 비어 있다. 미언급을 미지원으로 바꾸거나 공용 설명서의 특정 옵션을 해당 모델의 확정 기능으로 만들지 않았다. 스캔 PDF/OCR·일반 명세 JSON·기능 인용 의미 검수는 이번 범위에 포함하지 않는다.

모델 호출0·OCR0·독립 평가 원본 읽기0. #12 인용 수정, 검색 연결(5), 세 제품 전체 흐름(6), GitHub 게시/PM 검수·병합·통합(7)은 남아 있다. 이번 실행으로 #13 의존성을 해제하거나 공식 완료로 바꾸지 않았다.

## 증빙과 재현

- `runs/initial/step34-checks.json`: 실제 파서/API/검증/저장·서버 명령·고정 코드/입력 해시와 결과.
- `runs/initial/extraction-records.json`: CSV36건의 ID/행/모델/버전/원문 해시, PDF40쪽별 해시와 등록된 원문 문자 범위.
- `runs/initial/fresh-storage-checks.json`: 실제 새 DB 삽입/원본/재개8검사.
- `runs/initial/final-checks.json`: 기존485회귀 실패2·계약/지침/하네스/자기 lint, 상태 CLI 실패의 원 명령/출력.
- `runs/initial/port-cleanup-check.json`, `ci-probe-diagnostic.json`, `failed-checks-retry.json`: 종료 포트 확인 및 별도 진단. 실패한 전체 검사는 보존한다.
- 당시 실행 스크립트 원본은 `executed-runner.py.txt`와 `executed-fresh-storage.py.txt`에 보존했다. 원문/전체 응답·추출문·DB·임시 인증 토큰은 `private/data002-step34/initial/`에만 있다.

새 run-id를 사용해 기존 증거를 덮어쓰지 않는다. STEP1/STEP2의 private 등록과 고정 f88dd7a Git 이력이 필요하다.

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step34-20261005/run_steps.py --run-id reproduce-01
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step34-20261005/verify_fresh_storage.py --run-id reproduce-01
& '.\.venv\Scripts\python.exe' -B -X utf8 data/research/P2-DATA-002-step34-20261005/finish_checks.py --run-id reproduce-01
```

다음은 #13 5단계 검색/원문 연결이다. 최신 #12의 기능 인용 보완 결과를 확인한 뒤 연결할 자료 scope를 고정한다. 현재 사용자가 직접 해야 할 일은 없다.
