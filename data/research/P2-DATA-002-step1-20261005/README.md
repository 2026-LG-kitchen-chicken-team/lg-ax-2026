# #13 1단계 - 시험 입력과 예상 결과 준비

상태: **1단계 로컬 준비·검증 완료, #13 전체는 pending 유지**. 담당 신진하, 수행 AI Codex. 기록 ID `신진하-20261005-002-DATA002-STEP1`, 근거 ID `신진하-E008-DATA002-STEP1`. 실행 기준 commit `7cc25fba66e4d0f4a19ef9eebbaa9268937ce1c4`, branch `codex/data001-lg-sourcepack-20261004`.

## 요청과 범위

사용자 원문: “그럼 지금 #13을 해보자 1단계부터 실행해. 최우선으로 정이량이 지시한거에서 벗어나지말고 모르는거있으면 물어보고 하네스를 사용해도 좋아.”

해석: #13의 1단계인 기존 시험 입력 선정·제품/문서 버전·원문 위치·예상 근거 연결 준비를 수행한다. 기존 PM 배정과 `phase2.py next/packet`을 확인하고 준비 결과를 검사한다. #12 인수 대기 중 가능한 독립 준비이며 #13 등록 API/파서 구현 또는 전체 완료를 의미하지 않는다.

PM 근거: [최신 최소 인수 지시](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935), [#13 작업](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13). 2026-10-05 브라우저 직접 확인. 기존 합성 자료와 보유 공식 PDF를 재사용하고 개발 자료와 독립 평가 자료를 분리한다.

## 실행 결과

하네스 `next --member 신진하`는 선행 #12를 반환했고, #13 `packet`은 #12 의존성 및 pending을 확인했다. PM 최소 인수 지시가 허용한 독립 개발 준비 범위에서 기존 자료를 선정했다. 공식 시작·완료·보드 상태는 변경하지 않았다.

| 입력 | 모델·버전 | 원문 위치 | 선정 이유 |
|---|---|---|---|
| 기존 합성 리뷰 CSV 36건 | FRIDGE-A/B/C, DISHWASHER-A, MICROWAVE-A / 1.0 | 헤더 1행, 리뷰 2~37행 / REVIEWS-CSV-v1.0 | 기존 5모델·36리뷰·근거 ID를 보존해 CSV 등록의 개발 입력으로 사용 |
| 보유 공식 냉장고 PDF 1건 | T876MEE1H1 / MFL71401557 Rev.00_032526 | 40쪽 중 18~19쪽 확인, 선반 주의 문구는 19쪽 / F-M | 텍스트 PDF의 페이지 추적을 별도 실자료 사례로 준비 |

CSV는 기존 `data/demo/dataset.json`의 리뷰를 손실 없이 내보낸 파일이다. 새 리뷰를 만들지 않았고, 냉장고 30건·식기세척기 3건·전자레인지 3건이다. JSON의 원래 locator 행 번호와 CSV 물리 행 번호를 대조했다.

PDF는 기존 로컬 원본 `C:/Users/user/Downloads/REF_KOR_MFL71401557_00_260325_00_OM_WEB.pdf`를 참조한다. 원본 SHA-256은 `d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815`다. 공식 원본 URL·제품 적용 범위·개정 표기는 `input-selection.json`에 연결했다. 텍스트 추출과 18~19쪽 렌더를 함께 확인했고 원문 전문을 저장소에 복제하지 않았다. 공용 매뉴얼의 모델별 옵션을 특정 SKU의 지원 기능으로 확정하지 않는다.

## 산출물과 검사

| 파일 | 용도 |
|---|---|
| [reviews-v1.0.csv](reviews-v1.0.csv) | 원래 리뷰·모델·버전·출처 성격·행·근거 ID를 보존한 CSV 입력 |
| [input-selection.json](input-selection.json) | 입력 경로, 원본 URL, 해시, 모델·버전, 원문 위치와 자료 성격 |
| [expected-records.json](expected-records.json) | 향후 등록 결과와 비교할 개발용 Product/Review/Evidence 기대 레코드 |
| [control-plan.json](control-plan.json) | 동일 모델 조회, 페이지 추적, 다른 모델/버전, 필수 scope 누락, 미언급의 예상 처리 |
| [prepare_inputs.py](prepare_inputs.py) | 입력 준비·대조·Schema 검사·하네스 읽기를 재현하는 스크립트 |
| [runs/initial/verification.json](runs/initial/verification.json) | 실제 실행 결과, 입력·산출물·스크립트 해시, 코드 commit과 한계 |
| [runs/final/final-checks.json](runs/final/final-checks.json) | 종료 시 계약·하네스·지침·공백 검사와 원본 보존 재확인 |

실제 검사: CSV 36건의 원문·ID·근거·행 round-trip 일치, 기존 입력/계약/검색/하네스 파일 해시 유지, PDF 해시 일치. 기대 레코드 Product 6건·Review 36건·Evidence 37건이 기존 계약 0.1.0 Schema를 통과했다. PDF 근거 `DATA002-FM-P19-SHELF-01`은 이 준비 폴더의 후보 ID이며 실제 등록 시스템의 canonical ID가 아니다. 기능 지원 판단을 만들지 않아 `feature_ids`는 빈 배열이다.

종료 확인은 기존 계약 검사, AGENTS/CLAUDE 바이트 일치, phase2 구조 무결성 및 `git diff --check`로 한정한다. 서비스 코드를 바꾸지 않아 웹/MCP·기존 전체 회귀를 새로 실행한 결과로 표시하지 않는다. 다른 모델·버전·누락·미언급 통제는 **서비스 미실행의 기대 처리**이며 성공한 기능 시험이 아니다.

## 재현

저장소 루트에서 실행한다. 아래 번들 Python은 이미 제공된 pdfplumber를 사용하고, 스크립트 안의 Schema/하네스 검사는 프로젝트 `.venv`의 Python 3.11.17을 사용한다. 새 설치·권한 변경은 수행하지 않았다.

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 data/research/P2-DATA-002-step1-20261005/prepare_inputs.py --run-id reproduce-01
```

같은 run-id를 재사용하면 기존 실행 근거를 덮어쓰지 않고 실패한다. 원본 PDF가 위 로컬 경로에 필요하다. PDF 검사에서 제공된 Poppler로 18~19쪽을 임시 렌더해 직접 확인했다. `uv`는 PATH에 없고 기존 `.tools/uv/bin/uv.exe` 실행은 접근 거부로 실패하여, 동일 하네스 스크립트를 기존 `.venv/Scripts/python.exe`로 실행했다. 규칙이나 실행 정책을 낮추지 않았다.

## 단계 체크리스트·결정 기록

- [x] PM 지시·담당·하네스 의존성 확인
- [x] 기존 합성 CSV와 실자료 PDF를 독립 입력으로 선정
- [x] 원래 ID·모델·버전·행/페이지·원문·해시 보존
- [x] 개발용 기대 레코드와 향후 통제 시나리오 준비
- [x] 실제 대조·Schema 검사와 개인 작업기록/근거 연결
- [ ] 문서 등록·파서·검증 저장·등록 자료 검색 서비스 구현
- [ ] 세 제품군 실제 서비스 완주·PM 검수·병합·통합 확인

선정 결정: 정이량의 최소 인수 지시와 기존 준비물을 기준으로 합성 CSV를 손실 없이 재사용하고, 보유 텍스트 PDF를 별도 원문 위치 시험으로 선택했다. #12 전체 인수 전 가능한 #13 준비만 수행한다. 공유 운영 체크리스트의 PM 완료 항목 대신 이 담당 단계의 체크리스트와 개인 기록에 결과를 남긴다.

다음 구체 작업은 **2단계 문서 등록의 메타데이터·ID·저장 흐름 설계와 구현**이다. 먼저 최신 PM 규격과 기존 공통 계약의 접점을 확인하고, 공통 Schema/API 변경이 필요한 부분은 PM과 편집 범위를 조율한다. #12 인수와 #13 전체 완료 조건은 계속 별도로 추적한다.

## 현재 제한

두 입력은 서로 다른 자료 성격과 모델을 가진 독립 개발 시험이다. 실제 LG PDF의 내용을 가상 FRIDGE-A 기능 근거로 혼합하지 않는다. PDF 원본은 기존 로컬 경로를 참조하며 저장소에 전문을 복제하지 않는다. 개발용 시험 기대 결과를 독립 평가 정답으로 사용하지 않는다. 공통 Schema/API·PM 상태/근거·온라인 Project·타 담당 기록은 변경하지 않는다.
