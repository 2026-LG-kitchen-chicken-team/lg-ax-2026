# R5 독립 인계·집계 및 실제 저장·조회 검수

확인: 2026-10-07 KST. 사용자 4·5·6번 후속과 PR 게시 지시. 검사 source `8ec1e8a51faabd6db032e52245680bef4229f93f`, 게시 base `4e2bec4b6b6c65cf6f94347968a3e3a88281cec3`. 두 commit의 핵심 코드·고정 자료는 [같은 바이트](source-main-bridge.json)다.

| 항목 | 실제 확인 | 남은 조건 |
|---|---|---|
| 4 / #15 | 새 합성6유형+이전입력1 metadata, 역할별 ZIP3 원바이트 SHA, 현재 Agent input schema SHA 일치. 공개8은 PM 결정에 따라 개발 진단용으로만 유지 | Gold·의미 독립성·최종 채점자·비공개 경로·전체 모델 입력 전달·동일 조건 Agent/기준선 생성 및 실제 채점 |
| 5 / #16·148 | 239관찰−ID중복1=238고유, 개발141/평가후보36/시연49/격리12, 내부 ID·NFKC본문 교집합0. 비격리 분모226과 원문238 연결 | 226개 게시일 미상으로 월별 분모0. 토픽 정답/분자/비율은 null, 제품 판단 적격후기0. 실제 시장/월별 추세로 승인하지 않음 |
| 6 / #13·PR219 | 고정179후기 연구 SQLite 재생성의 원래 SHA 일치. 공개 실행팩 후기0·설명서3·근거21·기능9. 자체 HTTP109요청·저장/재시작584검사 PASS | 새 R5 **운영** DB/API 전후 캡처와 원 운영 출처·PM 인수. 연구238결합 DB/Excel과 새 리뷰CSV 등록은 미수신/미실행 |

[후기 원문·분할·산술 대조](research-population-audit.json) · [238원문 ID 대조 CSV](review-membership.csv) · [18개 표시페이지 분모](page-model-denominators.csv). 표시 모델은 구매 SKU가 아니고 구매일은 게시일이 아니다. 별점은 불편/토픽 정답이 아니다. [과거 원문 SHA 재사용](historical-original-hash-binding.json)의 776453은 demonstration이며 새 독립 평가로 승격하지 않는다. 제한된 정규화 본문 스캔0과 이 원문 SHA 대응1은 서로 다른 대조 범위다. 과거 전체 튜닝 이력을 검수했다는 주장이 아니다.

[ZIP opaque 검수](candidate-opaque-archive-intake.json)는 ZIP 내부를 열거나 입력/답안을 읽지 않았다. [schema 바이트 도메인](input-schema-binding.json)과 [최종 평가 release 조건](independent-evaluation-release-gates.json)을 분리한다. [PR222](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/222)의 후보/집계 제출을 고정 head로 소비하고 같은 private 후보를 새로 만들지 않았다. 이 개발 대화는 최종 독립 채점자가 아니다.

[실제 자체 캡처](isolated-HTTP-SQLite-capture.json)는 원 PDF3의 HTTP 등록, metadata와 DB record, 원본 다운로드 SHA, 근거21, 정상/다른 유효 모델/미등록 모델/잘못된 판본 검색, 프로젝트3·같은 canonical source SHA를 검사했다. 소유한 컨테이너 내부 서버2를 실제 종료·재시작한 뒤 모든 HTTP 원응답과 DB 행·스키마·바이트가 같다. 전체 API/DB 원응답 JSON과 원 바이트 SHA가 있다. 연구 DB는 별도179행이며 SQLite3.40.1에서 원 artifact SHA `253d184c62f568d9f9ff336cc59ca64b22ec79c83728e5fb102959de154af289`를 재현했다. [운영 미수신 경계](operating-intake-status.json)는 유지한다.

network none·UID1000·read-only root/source·zero auth 프로필·소유한 loopback HTTP만 사용했다. 실제 제품 계획 모델/OCR0, 새 설치/다운로드0, 운영 서비스/자동화/보호설정 변경0. 기존 이미지에 없던 pypdf6.10.0은 [이미 있는 bundled library](existing-parser-source-manifest.json)를 바이트 고정 복사해 자체 자식 프로세스에서만 사용했다.

재현: 같은 고정 소스·의존성·격리 경계에서 `python evals/data456-r5-verification/20261007-01a10c5c-bf12d6e3/audit_research.py`, `python evals/data456-r5-verification/20261007-01a10c5c-bf12d6e3/capture_integrity.py`; 출력은 `/artifacts/result.json`. 두 번째 명령은 실행 source의 `_verificationdeps/pypdf`에 기록한 기존 parser 파일을 두거나 pypdf6.10.0을 이미 제공하는 격리 Python이 필요하다. 실제 운영자 자격증명/서비스를 사용하지 않는다.

[검수 요약](validation-summary.json) · [코드/자료/실행 버전](code-data-version-binding.json) · [584검사 실행](execution-integrity-v6.json) · [기존 계약51/지침/문서 연결](contract-rules-navigation-checks.json) · [최종 Ruff](source-lint.json). 1416/584는 연결·산술·응답 비교 assertion 수이며 모델 품질 점수가 아니다. 새 코드 의미에 맞는 실제 검수를 수행했고 전체 제품 test suite 재실행으로 표시하지 않는다.

[실패와 복구](failure-history/resolutions.json)는 원 v1~v5 출력·실패 code copies·의존성 진단·lint 기록을 보존한다. 검사 도구의 가정 오류를 제품 결함으로 표시하지 않았다. 실패한 자체 통합 묶음만 재실행했고 연구 산술 검사와 모델 생성은 반복하지 않았다. 부모 Done·최종 평가·운영 인수는 미완료다.
