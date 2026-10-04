# DATA001 4·5단계 준비와 인용 보완

사용자 지시: “남은단계 7단계 빼고 4,5단계 할수있어?” 실제 모델 실행의 선행 자료와 개발/평가 분리 상태를 확인하고, 가능한 준비를 진행했다. 7단계 PM 검수·병합·통합은 수행하지 않았다.

최신 PM [CITATION-FIX 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5983430913), main `f88dd7a`의 인수 보고와 모델 어댑터·평가 지침을 직접 읽었다. PM은 PR69의 고정 파일을 PR71로 부분 인수했으며 자료 의미 검수는 미완료다. 기존 게시본을 변경하지 않고 `codex/data001-stage45-citations-20261005`에서 이어간다.

## 실제로 수행한 범위

- `scripts/prepare_lg_document_plan.py`의 재현 레시피를 보완했다. 원문과 연결되지 않은 냉장고 접이식 선반 수량1은 확정 설명에서 제외했다. 공용 설명서의 선택 기능이 정확 모델에 적용되는지는 이 인용만으로 미확인이다. 제품 페이지의 F08 사실은 참고팩에 그대로 보존하며 설명서 인용으로 바꾸지 않았다.
- 냉장고 청소 본문(p21)·플러그 분리(p5), 전자레인지 출력200/400/600/800/1000 W(p25)를 실제 원문 구간에 연결했다. 다른6기능도 함께 대조해 선반의 양손/식품 제거, 식기 바구니 종류/높이/노즐 조건과 전자레인지 메뉴/버튼 근거를 보완했다. 인용에 없는 칼날 방향/사용 가능 식기 조건은 이 기능 graph의 확정 조건에서 제외했다.
- 자료 버전은 `lg-manual-scope-20261005.2`다. 원 PDF·설명서 개정판은 그대로다. 세 제품/9기능/15근거이며 전체 제품 기능 목록이나 실제 고객 후기 자료가 아니다. `feature-citation-audit.json`의 모델·문서ID·버전·URL·페이지·문자 위치·원문/텍스트SHA로 각 설명의 근거를 조회한다.
- 기존 승인된 환경과 기존 HTTP 경로로 실제 PDF3건 업로드→텍스트 파싱→검증→저장→근거/검색/원문 조회→종료 후 재조회가 38요청/76검사 PASS였다. 모델·문서 버전·public 구분이 유지됐다. 임의 문서/OCR/#13 전체를 검증한 것이 아니다.
- 제품별 최신 input/dataset3쌍을 `model-pairs/`에 저장하고 기존 `build_planning_input`과 전체 정의 scope의 일치를 검사했다. `planning-inputs/`와 원문 위치·공통 자료/plan 해시도 새 실행에 연결했다. 과거 `.1` 입력/실패/검사 파일은 덮지 않았다.

## 5단계 평가 준비

기존 private 여섯 HELD 사례는 **계약 검토용**이며 의미 생성 평가를 완료한 자료가 아니다. 그대로 보존했다. 최신 main에 이미 있는 `evals/core-semantic`의 별도 SEM6유형을 기존 `prepare_inputs.py`로 재사용했다. 새 가상 모델/후기/정답을 생성하지 않았다.

정상·기능 중복·모델/버전 혼동·상충 리뷰·근거 누락·명세 변경의 모델 입력과 전체 자료/Schema를 포함한 기준선 프롬프트를 private에 준비했다. SEM03의 의도적 다른 모델/버전 오류와 SEM06의 변경 전후 입력은 유지했다. PM manifest 경로만 private의 내부 Schema 경로로 옮겼으며 원래 요청/자료/Schema 바이트와 해시는 보존했다.

- 공개 결과: `semantic-input-readiness.json`, `evaluation-intake-metadata.json`, `private-evaluation-delivery.json`의 형식/해시/분리 결과만 제공한다.
- 비공개 원본: `private/evaluation/SEM-stage45-20261005/`.
- PM 검토용 비공개 ZIP: `private/evaluation-transfer/DATA001-SEM-stage45-PM-review.zip`,23파일. reviewer-only는 opaque 바이트 복사/해시만 수행했고 개발에 내용은 읽지 않았다. 아직 PM에게 전송하지 않았다.
- 개발 자료와 동일 ID/원문 해시 중복0 및 형식 검사는 독립 작성/의미적 독립성/정답 타당성을 보장하지 않는다. PM의 독립 검토와 실제 Agent/기준선 결과는 없다. 모델 문맥/예산도 PM의 실제 설정으로 검토해야 하며 입력 준비를 비교 실험 성공으로 표시하지 않는다.

## 검사와 현재 제한

게시 후 추가 확인: [PR74](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/74)는 초기37파일/head3cbcc64로 생성했고 [자기보고](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5983852638)를 게시했다. GitHub 전체485회귀 중1실패는 새 `.2` 자료와 기존 연결 검사의 역사 `.1` 입력 비교였다. 기존 검사 입력 경로1곳만 stage45 `.2`로 맞추고 과거 자료/실패는 보존했다. 실패 원격 링크·범위는 `ci-recovery.json`, 수정 후 현재 source/test/input SHA의 결과는 `connection_regression.json`, `full_regression_after_ci_fix.json`에 연결한다. 최초37파일과 복구 추가파일을 전달 manifest에서 구분한다. 원격 CI·보고 ACK 최종 상태는 실제 원격/게시 수신증을 따른다.

계약·규칙·phase2 PASS. 문서 등록 회귀10개, 의미 입력 준비 검사7개, 수정 generator Ruff PASS. `checks.json`은 실행 시작 main SHA, 실제 수정 파일SHA, 명령/입출력/종료코드를 연결한다. 전체 회귀475개/CI4PASS는 이전 PR69 버전의 증거이며 이번 수정본의 전체 검사로 재표시하지 않는다.

실제 고객 리뷰0·모델 호출0, 참고팩의 출처 차이2/미확인7은 유지한다. 선반 선택 기능의 모델 적용/수량은 graph의 별도 미확인이다. 모델 환경4값은 없으며, 최신 PM 지시에 따라 GPU 실실행은 PM의 안전한 전용 연결에서 검수한다. 연구실 loopback을 사용자 PC 주소로 가정하거나 새 tunnel/설치/권한/공개endpoint를 만들지 않았다. 평가 점수/성공 출력/실제 고객 수요를 생성하지 않았다.

13ab5d2까지는 로컬 준비였다. 이후 사용자가 보완37파일과 다음 전달 순서를 확인한 뒤 “실행해”로 이번 후속 PR·push·#12 자기보고 게시를 승인했다. 게시 기록 변경은 실행된 source/data를 바꾸지 않는다. 실제 PR/보고 ACK·CI·최종head는 원격과 로컬 게시 수신증으로 확인하며, 준비/승인을 게시 성공으로 표시하지 않는다. 비공개 평가 ZIP 전송은 아직 승인/실행하지 않았고 #12/R05 전체 완료도 아니다.

## 사용 방법과 다음 작업 하나

승인된 `team-lg-ax-2026/.venv/Scripts/python.exe`를 사용하고 프로세스 PYTHONPATH에는 이 worktree의 `packages/core/src`, `packages/contracts/src`, `apps/api/src`, `apps/mcp/src`, `scripts`를 지정한다. 추가 설치는 없다. 인용 레시피 생성은 `python -B -X utf8 scripts/prepare_lg_document_plan.py --run-directory <새 data/research 실행 폴더>`다. 실제 PDF 재실행 명령은 `document_http.json`, 평가 입력 명령은 `semantic_input_preparation.json`을 따른다. 재실행에는 새 private/output 폴더를 사용해 기존 원문·실패·평가 인수물을 보존한다.

이번 다음 작업 하나는 **승인된 인용 보완 부분 PR·자기보고를 게시하고 접수를 확인하는 것**이다. 이후 PM 안전 연결의 냉장고 실제 출력과 이 `.2` 자료를 대조한다. 평가 ZIP은 비공개 전달 경로와 사용자 확인 후 전송한다. PM은 세 모델의 실제 실행 및 평가 독립성/기대 대응을 별도로 검수한다.

게시 후 복구의 로컬 결과는 연결5검사·전체485회귀 PASS다. 원문/자료/generator를 다시 바꾸지 않고 기존 테스트의 최신 입력 연결만 수정했다. 초기37파일에 테스트 수정 및 실패/복구 증거4파일을 추가한 총41파일이다. 과거 CI 실패는 `ci-recovery.json`의 링크로 보존하며, 수정 후 원격 CI·ACK는 현재 PR head의 실제 상태를 따른다.
