# DATA-001 1~3단계: 실자료 연결·기획 입력·설명서 등록

담당: 신진하. 시작 2026-10-05 KST. 이전 전달 commit `7cc25fb`, 최신 PM 구현 기준 main `6b9dbe9`를 별도 작업 공간에서 합친 base `13b558c`에 작업했다. 사용자 직접 지시로 이번에는 세 모델의 최소 문서 처리 연결까지 진행했다. 원격 게시 보류는 유지한다.

## 이번 단계의 결과

| 단계 | 실제 실행 | 한계 |
|---|---|---|
| 1. 원문·제품·기능·근거 연결 | 공식 PDF 3건, Product 3건, 사례 Feature 9건, canonical Evidence 10건. 원문 hash·모델·개정·페이지·문자 위치·URL·확인 시각 연결 | 정의한 제출 사례 기능 범위다. LG 전체 기능 목록이나 실제 고객 후기 자료팩이 아니다 |
| 2. 기존 기획 입력 계약 | 최신 `workspace_planning.build_planning_input`에 같은 모델·설명서 버전의 원본 Product와 정의한 Feature/Evidence 전부 입력. 세 제품군 모두 schema 검사. 다른 모델·버전 혼합 거부 | 실제 AI 모델의 판단·불편/콘셉트 출력은 실행하지 않음 |
| 3. 실제 문서 처리 연결 | 새 최소 로컬 경로로 PDF HTTP 업로드 → pypdf 텍스트 파싱 → canonical entity/연결 검증 → SQLite·원문 저장 → 기존 조회 함수의 HTTP 검색/근거 조회 → 원문 반환. 재등록과 서버 종료 후 저장 유지 확인 | 기존 공통 작업실 API/MCP에는 아직 통합하지 않음. CSV·이미지 OCR·범용 자동 기능 추출은 이번 경로에 없음 |

HTTP 33요청과 60검사를 통과했고 만든 서버는 종료했다. 텍스트 PDF라 OCR을 사용하지 않았다. 이는 실제 PDF 처리 연결 증거이며, 파일 읽기나 schema 검사만을 전체 처리 성공으로 표시한 것이 아니다.

최신 main에 이번 변경을 더한 회귀 382개, 계약·규칙 동기화·phase2·기존 하네스·MCP stdio 검사가 통과했다. 신규 문서 처리 단위검사 8개는 그 382개에 포함된다. 웹은 수정하지 않았고 새 웹 build/e2e 또는 원격 CI를 실행하지 않았다.

## 모델과 원문

| 제품군 | 모델 | 설명서 개정 | PDF 페이지 수 | 조회 확인 질문/토큰 |
|---|---|---|---:|---|
| 냉장고 | T876MEE1H1 | MFL71401557 Rev.00_032526 | 40 | 선반 분리·청소 조건은? / `선반` |
| 식기세척기 | DUE6BGL2E | MFL71959117 Rev.07_030626 | 60 | 바구니 높이·적재 조건은? / `바구니` |
| 전자레인지 | MW23FDI | MFL68822538 Rev.00_120925 | 40 | 시작/선택 시간 증가와 출력 조절은? / `30초` |

냉장고 표지는 제품군 공용이고 정확한 T876 모델명이 인쇄되어 있지 않다. 식기세척기는 DUE6****E 적용 계열, 전자레인지는 MW23FDI 정확한 모델명이 있다. 이전에 승인한 동일 모델의 공식 제품→설명서 연결과 표지 개정번호를 대조했고 공용 설명서의 선택 기능을 전부 실제 모델 기능으로 가정하지 않았다. D10 프라이팬 거치대와 미확인 M16 개인 설정 저장/호출은 Feature로 만들지 않았다.

숫자 최소 대조는 바구니 3단계·전자레인지 30초 증가·200/400/600/800/1000 W의 본문 위치로 기록했다. 표지 3건·식기세척기 p57의 빌트인 사양 열·전자레인지 p37의 해당 모델 사양 열도 원본 화면으로 확인했다. 냉장고 접이식 선반 1단은 모델별 제품 페이지의 F08에서 유지하며 공용 설명서 인용으로 표시하지 않는다.

## 형식과 보존

- `data/document_plans/lg-three-models-20261005.json`: 승인된 문서 ID·hash·선택 위치·적용 조건을 고정한 계획. 외부 사용자가 임의 URL/모델/추출기를 지정하지 않는다.
- `data/document_datasets/lg-three-models-20261005.json`: 실제 등록으로 생성한 `document_dataset`. 개별 Product/Feature/Evidence는 기존 공통 schema를 사용한다. 합성 전용 DemoDataset/Manifest/BootstrapResponse로 위장하지 않는다.
- `mapping.json`, `original-locations.json`, `original-number-check.json`: 연구 fact ↔ canonical ID ↔ 원문 URL/개정/페이지/문자 위치의 대조.
- `planning-inputs/`와 `planning-contract.json`: 세 모델의 입력과 계약 검사. 실제 AI 출력이 아니다.
- `flow-command.json`, `http-flow.json`: 서버·업로드 명령, 입력/응답 hash, HTTP 상태, 각 성공·실패 통제, 종료 확인. Bearer 값은 기록하지 않는다.
- 회귀·계약·규칙·하네스·MCP 검사 JSON은 각각 실제 argv/exit/stdout/stderr와 시험한 파일 hash를 기록한다. base commit에 미커밋 변경을 더해 검사했으므로 base commit 자체를 검사한 것으로 표시하지 않는다. 최종 전달 commit의 수신증은 Git 제외 `tmp`에 별도로 만든다.

원문 PDF·전체 추출 텍스트·원본 확인 이미지는 `private/documents-source/`, 실제 등록 DB·원문·토큰은 `private/document-runs/stage123-real-01/`에만 보존하며 PR 후보에서 제외한다. 전달 자료는 필요한 짧은 원문 근거와 링크 중심이다. 기존 60항목 참고팩은 그대로 보존했으며 나머지 50항목을 manual/review라고 임의 변환하지 않았다. 출처 차이 2건·미확인 7건을 해소한 것으로 표시하지 않는다.

기존 합성 5모델·36리뷰·42근거는 변경하지 않았고 기본 합성 API는 그대로다. 이번 실제 팩의 고객 리뷰는 0건이다. 독립 평가 원문·답안은 읽거나 튜닝 입력에 넣지 않았으며 이전 비공개 준비와 PM 확인 상태를 바꾸지 않았다.

## 재실행

추가 설치 없이 기존 승인 프로젝트 환경의 Python 3.11.17·jsonschema 4.26.0과 이미 있는 번들 Python 3.12.14/pypdf 6.10.0을 사용했다. 핵심 서버는 3.11이며 3.12는 명시적으로 지정한 PDF 추출 자식 프로세스에만 사용한다. pypdf는 프로젝트 lock에 없으므로 다른 컴퓨터에서 기존 추출 환경이 없다면 설치 승인이 필요하다. 자동 설치나 시스템 Python 변경은 없다.

1. 프로젝트 기준 Python으로 이 작업 공간의 `packages/core/src`, `packages/contracts/src`, `apps/api/src`, `apps/mcp/src`를 프로세스 `PYTHONPATH`에 지정한다. 실제 작업 공간 import 경로를 `flow-command.json`/`http-flow.json`과 대조한다.
2. 승인된 세 PDF를 계획의 SHA256와 일치하도록 private 원본 위치에 둔다. 원본이 없으면 링크에서 별도로 확보해야 하며 검증 스크립트가 인터넷에서 임의 다운로드하지 않는다.
3. `python -B -X utf8 scripts/verify_lg_document_flow.py --extractor-python <기존 pypdf 환경의 python> --directory <현재 작업 공간/private 아래 새 실행 폴더>`를 실행한다. 새 폴더로 실행하면 실제 파싱부터 반복하며, 같은 폴더는 중복 등록을 확인한다. 이 스크립트는 같은 이름의 실행 증거 파일을 갱신하므로 새 증거 보존이 필요하면 먼저 실행 폴더를 별도로 보관한다.

등록 서버는 `python -m lgax_core.documents_server --directory ... --plan data/document_plans/lg-three-models-20261005.json --extractor-python ... --token-file private/... --port ...`로 별도 실행할 수 있다. host는 `127.0.0.1`로 고정하고 모든 요청에 private 파일의 Bearer를 사용한다. 문서 버전/큐레이션 계획을 바꿀 때는 새 저장 폴더를 사용하며 기존 문서 ID를 덮어쓰지 않는다. PDF/토큰을 공유 공용 API로 노출하지 않는다.

## R03와 #12의 남은 조건

R03는 **설명서 PDF 경로 개별 검증**을 충족했다. 리뷰 CSV·명세 등 전체 등록과 작업실 통합은 아직이라 R03 전체 완료를 선언하지 않는다. R05/R06도 이번 자료·입력·조회에서의 연결을 확인했으며 실제 AI 출력까지 확인한 것이 아니다.

실제 리뷰/불편 원문 확보·등록·출력 추적(R04/R13), 세 제품군 실제 판단 완주(R08), 독립 평가의 PM 확인·실제 실행, 공통 연결 검수, 승인된 게시/인수/PM 검수·병합·통합이 남는다. R07의 기존 합성 예시는 재사용했지만 원문을 새 Issue/PR에 붙이지 않는다. 이 로컬 결과로 하네스 finish·PM approve/merge/Done 또는 Project 상태 보고를 실행하지 않았다.

다음 작업 하나는 **세 제품군의 실제 판단을 돌리기 전 부족한 리뷰 근거의 확보·사용 범위를 확정**하는 것이다. 모델 실행이나 수집 범위 확대는 별도 승인을 받은 다음 진행한다. 게시를 다시 결정하기 전에는 이 작업 공간과 준비 자료를 로컬에서 보존한다.
