# DATA-001 — 최신 main 대조·부분 전달

2026-10-05 신진하 / Codex. 이전 04281bb 및 170/382/395개 검사 증거는 보존했다. 최신 main 61addf3을 개인 브랜치에 merge한 b82cf9c에서 이번 검사를 실행했다. 최종 PR commit과 실행 대상 파일의 SHA256는 별도 게시 수신증과 checks.json을 대조한다.

## 이번 실행 결과

- 승인된 기존 Python 3.11.17/.venv를 재사용했다. 새 설치·전역 환경 변경 없음.
- 계약·동일 지침·phase2·패킷/대기열·회귀 475개·MCP stdio·HTTP 66요청/70검사·평가 metadata 검사 통과. 각 명령/입출력/시각/exit는 개별 JSON과 checks.json에 있다. HTTP 원응답·CSV는 private에 보존한다.
- 실제 모델 T876MEE1H1·DUE6BGL2E·MW23FDI의 Product3/사례 Feature9/Evidence10와 모델별 input/dataset 쌍을 보존했다. 기존 PDF3건의 원문/적용 범위/버전/페이지 증거는 stage123, 제품 조사60항목·출처 차이2·미확인7은 real-reference를 따른다. 전체 LG 기능 목록은 아니다.
- 기존 합성5모델/36리뷰/42근거를 그대로 사용했다. public 설명서 자료와 synthetic 데모를 분리하고 실제 고객 리뷰는 0건이다. 공개 자료가 없으면 합성 자료로 기능 검증을 허용한다는 PM MINIMUM-HANDOFF를 적용하되 실제 고객 수요 증거로 표현하지 않는다.
- 평가 여섯 유형의 현재 PM manifest/파일/hash/개발 ID·동일 문장 겹침0을 재확인했다. 평가 정답 내용은 개발에 읽지 않았다. 독립 작성·정답 타당성·실제 평가 실행은 미확인이다.
- 전역 Ruff는 기존 main과 동일한 파일의 지적을 별도 lint.json에 남긴다. 자기 자료 처리 변경 파일 검사는 통과했다. 다른 담당 파일을 임의 수정하지 않는다. GitHub CI는 게시 후 실제 결과로 구분한다.

## 버전과 실패 구분

검사를 실행한 코어/자료/schema/test 파일은 hash로 고정했다. verifier 시작 후 explicit check=False를 추가한 lint 수정은 version-provenance.json과 executed-verifier-source.py.txt에 양쪽 SHA와 실행 원본을 남겼다. subprocess.run 기본값도 False여서 검사 명령/결과와 코어 동작은 바뀌지 않았다. 오래된 검사를 최신 main 검사로 재표시하지 않는다.

## 막힌 점 / R03 실행 여부

현재 모델 환경 변수4개가 없고 문서화된 loopback18864/18865의 2초 연결이 timeout이다(model-connection-preflight.json). 실제 AI 호출0이며 HTTP201은 failed 실행 저장이다. GPU 사용·기존 SSH 포워드·비공개 설정 경로가 미확인이라 임의 연결이나 서버 시작을 하지 않았다. PM에게 기존 연결 정보와 자료 처리 계약의 인수 범위를 요청한다.

R03는 승인된 PDF·합성 CSV·작업실 자료 조회 경로의 실제 실행 증거다. 일반 명세 JSON/OCR/임의 문서 지원이나 #13 전체 완료는 아니다. 출력의 리뷰/기능 추적(R04/R05/R06/R13)과 세 제품군 실제 판단 완주(R08)는 미실행이다. AI 판단 코어 자체의 구현/품질 개선은 황대겸·PM 담당이며 #12를 이유로 담당 범위를 확대하지 않는다.

## 부분 PR 준비와 #12 역할

[#12](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12)는 정이량이 신진하/ginaginaring에게 배정한 **세 제품 자료팩·원문·모델·버전 계약 준비**다. AI가 다른 모델의 사양이나 가상 리뷰를 실제 LG 근거로 잘못 사용하지 않도록 자료와 근거를 연결하는 일이다. 현재 작업은 [최신 최소 인수 지시](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5982756935)의 세 input/dataset·검사·개발/평가 분리·진척/막힘 부분 전달에 해당한다.

사용자가 이번 대화에서 기존 작업의 Issue/부분 PR 게시를 직접 요청했다. 자기 기록004/E010과 증거를 같은 commit으로 전달한다. 기존 가상/합성 원문·평가 입력/답안 전문·PDF/전체 추출/이미지/DB/토큰은 새 diff에서 제외하고 publication-content-audit.json에 검사를 남겼다. 부분 PR은 #12 전체 완료 제출이나 의존 해제가 아니다. 실제 게시/ACK/CI/PM 상태는 원격 링크 및 로컬 게시 수신증을 따른다.

## 남은 순서와 사용 방법

다음 하나는 준비된 부분 PR과 인증 자기보고를 PM에게 전달하고 수신 확인을 확인하는 것이다. 이후 기존 모델 연결 정보로 냉장고 한 사례의 출력 근거를 대조하고 다른 두 제품군에 적용한다. 평가 원본은 승인된 비공개 전달 경로와 PM의 독립성/정답 확인이 필요하다. 최종 검수·병합·병합 후 통합은 PM 정이량만 판정한다.

재현은 기존 프로젝트 Python으로 프로세스 PYTHONPATH에 packages/core/src;packages/contracts/src;apps/api/src;apps/mcp/src;scripts를 지정하고 `python -B -X utf8 scripts/verify_data001_handoff.py --cases <private 평가 cases.json>`을 사용한다. 이 명령은 기존 검사·실제 전송과 모델 설정 부재 실패를 재현하며 AI 실행 도구가 아니다.

#12가 PM 검수·병합·통합까지 끝나면 phase2 next/PM 최신 배정에 따라 [#13 문서 등록·파싱·조회·모델/버전 필터](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13)를 이어간다. [#14 검색·재정렬·OCR 비교](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14)는 그 다음 배정/의존을 확인하며, 이번 작업에서 전체 구현으로 확장하지 않는다.
