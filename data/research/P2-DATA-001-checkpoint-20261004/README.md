# DATA-001 부분 전달 준비 — 2026-10-05

**자료 계약과 기존 조회의 검증을 마쳤다. #12 전체 완료와 PM 검수·병합·통합은 아직 아니다.** 사용자는 이번 범위를 “#12 검증·부분 전달 준비 유지”로 확정했다.

## 이번에 확인한 결과

| 항목 | 결과 | 증거 |
|---|---|---|
| 프로젝트 실행 환경 | Python 3.11.17, uv 0.12.23, 잠금 jsonschema 4.26.0 설치·import 성공 | 최신 run의 environment-install/ready.json |
| 기존 계약·회귀 | 계약 검사 통과, 기존 회귀 170개 통과 | contracts.json, regression.json |
| 실제 세 제품 | Product 스키마 3건 통과, 60항목 출처 연결 오류 0 | data-contract-audit.json |
| 기존 리뷰 | 리뷰 36건의 원문·모델·버전·자료 구분 연결 확인 | data-contract-audit.json |
| 기존 검색 | 세 제품군 실제 HTTP 검색·원문 조회·재호출 및 오류/빈 결과 확인 | http-query.json |
| 하네스 | Git 이력 확보 후 valid=true, errors=[] | phase2-validate-after-history.json |
| 평가 준비 | 비공개 여섯 유형을 PM manifest 형식으로 연결, 계약 기대 결정 6/6 일치 | evaluation-materials.json |

공식 자료 9건과 SSG 3건에서 정리한 실제 자료는 [참고팩](../P2-DATA-001-real-reference-20261004/README.md)에 있다. 냉장고 T876MEE1H1 19항목, 식기세척기 DUE6BGL2E 20항목, 전자레인지 MW23FDI 21항목이다. 출처 차이 2건·미확인 7건은 그대로 남겼다. 실제 자료팩은 public sidecar이며 합성 전용 DemoStore에 주입하지 않았다.

## 버전과 범위

이번 기존 검사·HTTP 실행 코드는 `791c206338dc2786bb880bdd53d80f9d1c010767`이다. 이후 전달 commit과 구분한다. 최신 main `cd3044f77760f0cf1dcaf8d9e97b13c826ae6b4a`의 schema/API/기본 자료/잠금은 검사 대상과 같은 바이트지만, 170시험을 최신 main 전체 검증으로 표시하지 않는다. 비공개 사례의 계약 결정 검사에만 고정 main CORE001 코드를 사용했다.

[최신 run](runs/20261004T151925Z/README.md)에 명령·입력·출력·성공·실패를 연결했다. 이전 환경 실패와 초기 하네스 실패를 삭제하지 않았다. Git 이력 복구로 하네스 오류를 해결했고 PM 원본 증거는 수정하지 않았다. 이전 20파일 준비와 28파일 전달 단계의 증거도 보존했다.

브라우저로 최신 [#12](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12), #13, PM DATA-001-CHECKPOINT와 main 지침·평가 안내를 읽었다. 저장소는 조직으로 이전됐고 origin을 같은 저장소의 현재 주소로 갱신했다. GitHub 커넥터의 404와 브라우저·Git 읽기 성공은 별도로 기록했다.

## 비공개 평가 자료

최신 main에 이미 준비된 CORE001 heldout 여섯 유형을 재사용해 `private/evaluation/DATA001-20261005-contract-review/`에 PM 형식의 자료·출력 계약·별도 기대 대응 초안을 준비했다. 개발 원문·ID와 정확히 겹치는 항목은 0건이다.

현재 자료는 제시된 후보 초안의 계약 검토용 합성 사례다. 독립성·정답 타당성·전체 상품기획 평가에 적합한지는 PM 확인 전 미확인이다. 실제 모델 평가·성능 비교·고객 수요 증거로 표시하지 않는다. 원문과 답안은 새 Issue/PR에 포함하지 않으며 개발·튜닝에 사용하지 않았다.

## 남은 조건과 다음 작업

- R03: 문서 등록·파싱 경로가 없다. 기존 합성 조회 성공을 실제 LG 자료의 업로드→파싱→검증→조회 성공으로 계산하지 않는다. #13 구현은 이번 범위에서 제외했다.
- R04/R05/R07/R13: 실제 판단·분석 출력에서 원문 추적과 재실행을 확인해야 한다. 데이터의 원문 연결 확인과 구분한다.
- R06/R08: 세 제품군의 전체 처리·분석 경로에서 자료 구분과 버전 유지가 필요하다.
- PM: 평가 초안 검토, 부분 PR 인수, 검수·실제 병합·통합 확인이 남았다.

[PR 초안](partial-pr-description.md)과 [파일·해시 목록](delivery-manifest.json)을 준비했다. 제안 대상은 `2026-LG-kitchen-chicken-team/lg-ax-2026`의 `main`이며 head는 `codex/data001-lg-sourcepack-20261004`이다. 실제 push·PR 생성·Issue/Project 보고는 승인 전에 하지 않는다. 다음 작업 하나는 이 내용의 게시 승인 후 부분 PR을 전달하는 것이다.
