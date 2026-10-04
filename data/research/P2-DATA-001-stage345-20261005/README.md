# DATA-001 연결 검증·평가 인수 준비 (로컬)

이 묶음은 이전 `2fb3e3e`의 PDF3건 검증을 보존하고, 최신 main `07be0aa`를 로컬 merge `78ab18f`에 반영한 뒤 진행한 결과다. 각 코드/자료 해시는 `checks.json`과 최종 로컬 receipt를 대조한다. 실제 고객 리뷰와 실제 AI 판단 성공은 아직 없다.

## 이번 실행 결과

- 기존 합성5모델/36리뷰/42근거를 보존했다. 기존 JSON의 36리뷰를 private의 CSV 전송 입력으로 변환해 실제 HTTP 업로드→CSV 파싱→공통 계약/원문 대조→저장→근거/검색/원본 조회→서버 재시작 후 조회를 실행했다. 과거 CSV 원본을 회수했다고 표시하지 않는다. CSV의 각 행은 기존 Review/Evidence와 모델·버전·합성 성격·원문이 같다.
- 실모델 T876MEE1H1/DUE6BGL2E/MW23FDI의 등록된 DocumentDataset을 기존 작업실 서버의 evidence_store 주입 경로에 연결했다. 자료 버전을 위한 내부 metadata를 추가하는 전용 adapter이며 합성 DemoManifest나 공통 계약을 수정한 것이 아니다. 실제3개 프로젝트 생성·모델별 근거 검색·다른 모델/잘못된 버전 차단·실패 실행 저장·재시작 후 같은 snapshot 조회를 확인했다.
- 실제 HTTP66요청/연결70검사는 `connections-results.json`에 명령·입출력 바이트/hash·상태·검사로 연결한다. 합성 원문/전체 응답은 private에만 있다. 신규 경계 단위검사5개는 기존 자료를 재사용한다. 일반 웹 UI나 원격 배포를 실행한 증거는 아니다.
- 실제 설명서 기반 사례 기능9개·근거10개이며 전체 LG 기능 목록은 아니다. 실제 고객 리뷰0건을 유지한다. PDF 원문과 페이지/출처/hash 연결은 이전 stage123의 `original-locations.json`, `mapping.json`, `http-flow.json`을 참조한다.

## 막힌 점

Python3.11.17/jsonschema4.26.0은 사용할 수 있다. 모델 환경 변수4개와 문서화된 로컬18864/18865 서비스는 없다. 세 모델의 작업실 실행 요청은 HTTP201로 실패 기록을 저장했으며, 결과는 failed/INVALID_ARGUMENT, 실제 모델 호출0건이다. **201은 AI 성공이 아니다.** 기존 연구실 GPU 접속/현재 점유 확인 방법을 PM에게 문의했다. 새 설치·유료API·다른 GPU 작업 변경은 없다.

사용자가 승인한 PM 연결 문의는 [#12 댓글](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982703508)에 실제 게시했다. 이 문의만 전송했으며 상태 보고 ACCEPTED·부분PR·검수 수신·연결 답변을 확인한 것으로 표시하지 않는다.

전체395검사의 첫 샌드박스 실행은 웹 준비/정리2개 실패였다. `checks-sandbox-failed.json`과 private 실패 로그를 보존했다. 같은 코드의 두 항목을 사용자 실행 환경에서 재실행해 통과한 증거는 `ci-probe-owner-check.json`이다. 정확한 Windows 환경 차이의 원인은 미확정이다. 현재 전체 검사 결과는 `checks.json`의 exit/test_count로 확인하며 이전382/170개 결과와 구분한다.

## 부분 PR 준비 상태

`partial-pr-description.md`가 제목/본문 초안이며 `delivery-manifest.json`이 명시적 파일/hash 목록이다. 기존20→51→88파일 이력은 각 이전 manifest에 보존한다. 현재 branch는 `codex/data001-stage123-20261005`, 대상은 비공개 `2026-LG-kitchen-chicken-team/lg-ax-2026`의 main이다. 로컬 commit 뒤 receipt의 Git blob/file hash 일치를 확인한다.

진행 중 직접 확인한 최신 PM 배정은 [MINIMUM-HANDOFF](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935)이다. 모델별 `model-pairs/<model>/input.json`·`dataset.json` 세 쌍을 제공하고 `model-pair-contracts.json`에서 기존 build_planning_input과 일치하는지 검사했다. 기한은 **2026-10-05 18:00 KST까지 최소 인수물 또는 구체 막힘 보고**다. 로컬 준비를 PM 전달로 표시하지 않고 사용자 게시 보류를 유지한다.

평가 원본·기대 대응의 비공개 ZIP은 `private/evaluation-transfer/DATA001-six-types-PM-review.zip`에 13파일/원래 바이트 유지로 준비했다. `private-evaluation-delivery.json`은 ZIP/파일 hash만 공개하며 실제 PM 전달은 아직 하지 않았다.

원본 PDF·전체 추출·이미지·DB·토큰·CSV 합성 원문·평가 입력/답안 원문은 게시 후보에서 제외한다. 사용자 승인 전 push/PR 생성/온라인 상태 보고를 하지 않는다. 매 PR 게시 직전에 대상·고정 commit·포함 목록을 보여주고 직접 승인받는다.

## #12 남은 조건 / R03 실행 여부

| 단계 | 직접 확인한 상태 | 남은 조건 |
|---|---|---|
| 1 자료 연결 | 사례 범위 Product3/Feature9/Evidence10와 원문/모델/버전 연결 | 실제 리뷰 및 전체 기능으로 확대했다는 주장 금지 |
| 2 입력 계약 | 세 모델의 같은 버전/전체 정의 근거 입력 계약 검사 | 실제 모델 실행 결과는 별도 |
| 3 문서 처리 | 실제 PDF3건 경로와 합성 CSV36건 경로, 실제3모델 작업실 조회 연결 검증 | R03 인정 범위는 PM 검토; 일반 명세 JSON 업로드/OCR/임의 문서 처리 및 #13 전체는 미완료 |
| 4 실제 AI 결과 | 세 요청의 실패 저장/입력 유지 확인; 실제 호출0 | PM 기존 연결/GPU 확인 후 실제 실행·R04/R05/R06/R08/R13 출력 대조 |
| 5 독립 평가 | 여섯 유형 manifest/파일/hash, 개발ID·동일 text hash 겹침0 확인 | 정답/의미상 독립성 PM 검토·실제 평가 실행 |
| 6 부분 전달 | 로컬 초안·명시적 포함 목록·기록/증거 준비 | 사용자 게시 승인·push/PR·인증 보고 ACCEPTED |
| 7 최종 완료 | 자기 완료 판정 없음 | PM 정이량의 검수·실제 병합·병합 후 통합 확인 |

R03는 승인한 자료의 실제 연결 증거를 보강했으며 단순 파일 읽기/스키마 통과로 전체 성공 처리하지 않는다. R04/R13의 불편 결과에서 실제 사용한 리뷰 추적, R05의 실제 기능 판단 추적, R08 세 제품군 실제 AI 완주가 남았다. 참고팩의 출처 차이2건/미확인7건을 유지한다. 자료팩 부분 준비와 #12 전체 완료는 구분한다.

## 사용 방법 / 다음 작업 하나

승인된 기존 `.venv/Scripts/python.exe`에 이 작업 공간의 `packages/core/src;packages/contracts/src;apps/api/src;apps/mcp/src`를 프로세스 PYTHONPATH로 지정한다. `python -B -X utf8 scripts/verify_data001_connections.py`는 실제 로컬 전송/조회와 **모델 설정 부재 실패**를 검증한다. 이미 모델 변수가 설정돼 있으면 거부하므로 실제 AI 실행 도구로 사용하지 않는다. HTTP 전체 응답 위치는 `private/document-runs/stage345-connections/full-http-responses.json`이다.

`python -B -X utf8 scripts/verify_data001_eval_metadata.py --cases <private 평가 cases.json>`은 기존 PM manifest parser를 사용하며 정답 내용을 읽거나 평가하지 않는다. 평가 원본은 원래 clone `private/evaluation/DATA001-20261005-contract-review/`에 보존하고 공개 metadata만 이 폴더에 남긴다.

다음 작업 하나는 **PM의 기존 모델 연결 경로를 확인하고, GPU 현재 사용/고정 모델 버전 확인 후 냉장고 한 실행의 출력 근거를 대조하는 것**이다. 새 설치나 권한이 필요하면 별도 설명/승인을 받는다. 지금 사용자에게 설치/오류 수정 작업을 넘기지 않는다.
