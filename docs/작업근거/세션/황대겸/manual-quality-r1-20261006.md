# 황대겸 — 수동 필수 판단 품질 R1 근거

- 근거 ID: 황대겸-E-MANUAL-QUALITY-R1. [작업 지시·해석](../../../작업기록/세션/황대겸/manual-quality-r1-20261006.md).
- 시작 main: `d0cfbde3f1ac1054ae94a061b57fbd0a1dcc398c`; 코어/추론/Skill/기존 의미 검토 검사는 통합 main96c6과 동일한 경로임을 git diff로 확인했다.
- 실제 Project 읽기: 2026-10-06 12:38 KST. CORE001 done, CORE002 pending/Ready, CORE003~005 pending/Deferred. 최신 #11의 직접 수동 품질 배정은 부모 완료와 구분한 부분 보완을 요구한다.
- 원 PM 실제 Qwen3:8b 여섯 정상/변경 사례와 냉장고 추가 두 사례는 총 완료0이었다. 원문·모델/설정·모든 호출·토큰·원 출력은 [독립 품질 검토](../../../../evals/pm-intake/20261006/core-quality-review.md) 및 해당 원본을 보존한다.
- 원 PR136/e7005f7 PR142를 현재 main 전체 덮어쓰기로 적용하지 않는다. 두 차별점 근거 보호 규칙은 PR136의 SHA 보존 원 코드와 대조했다.
- 중앙 확인: 2026-10-06 12:42 KST 팀 OFF·unknownamed false·본인 running/queued0. 본인 `LGAX-Worker-unknownamed` Disabled, 12:43 재조회에서 본인 Python Worker0. 예약 원 XML·상세 읽기 수신은 비공개 재개 기록에 있다. 다른 서비스/역사 작업·원 비용은 보존했다.
- 검사 환경 준비: 기존 본인 Docker 이미지 `sha256:36ad082dbccf05bc9cff7c4dc5766e9ab7ed8c42198b0b731cf3831c546aaaf0`; network none, user65534, read-only, cap-drop ALL, no-new-privileges, 임시 HOME, 호스트 홈/게시 인증 마운트 없음. jsonschema/ruff/mcp/httpx 존재·인증 환경변수0을 확인했다. 이 준비는 코어 검사나 실제 모델 성공이 아니다.
- [검사 manifest](../../../../evals/core-manual-quality/20261006/checks/manifest.json)·원 로그에 최신 코드 hash와 실행 환경/시각을 고정했다. CORE233개 fixture/replay 통과, 실제 전자레인지 변경의3Need/1희망 결과 원응답과 냉장고 설명서 누락 원응답도 새 모델 호출 없이 재생했다. 반복된 실패가2회 수정 후 종료하며 원본이 바뀌지 않았음을 확인했다.
- 규칙 동일성·공통 계약·phase2 역사/인수 무결성·새 개발 입력6·변경 소스 Ruff E4/E7/E9/F/I(py311,line110) 통과. Git 역사 검사는 전체 실제 저장소 객체만 읽기 전용으로 동결해 원 출처/조상 관계를 확인했다. 호스트 Git 설정·remote·hook·게시 자격증명은 복사하지 않았다. 초기 역사 없는 복사/불완전 객체 및 Windows 마운트 실행 비트의 실패 수신은 비공개 기록에 보존했다.
- 지원 판정과 불편 해소 판정은 모델 선언으로서 출처 연결을 검사한다. 새 모듈/fixture가 선언의 의미 정확도를 증명하지 않는다. 후보별 리뷰+설명서 차별점 보호 규칙과 수치 문구 의미 검토도 실제 모델 결과를 별도로 받아야 한다.
- 새 입력의 이전/현재 hash·변경 필드는 [개발 입력 provenance](../../../../evals/core-manual-quality/20261006/development/provenance.json)에 있다. DATA/공통 계약/웹/자동 운영/다른 개인 문서는 편집하지 않았다. 기존 CORE001 Done/부모 dependency/원 job·attempt·비용은 수정하지 않았다.
- 아직 미실행: 실제 모델 재검증(Qwen3:8b 정상/조건 변경, 미뤄둔 같은27B1건), PM 독립 평가·인수·병합·전체 완료. 이번 ordinary PR의 개별 보완 인수와 해당 검증·부모 Done은 분리한다.
