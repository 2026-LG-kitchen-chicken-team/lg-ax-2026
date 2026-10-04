# R03 냉장고 연결 확인 — 현재 미충족

이번에는 T876MEE1H1 공식 설명서 한 건의 업로드 → 파싱 → 검증 → 조회 연결을 확인한다. **현재 완료한 것은 환경 원인과 구현 경로 확인이다. 네 단계는 실행되지 않았고 R03 전체는 미충족이다.**

## 실행 환경 원인

- 프로젝트 기준은 Python 3.11(`.python-version`, `pyproject.toml`, `uv.lock`). 앞선 번들 Python 3.12.14와 PATH Python 3.10.2는 기준과 다르다.
- `jsonschema>=4.23,<5`가 이미 선언되어 있고 lock 버전은 4.26.0이다. 의존성 선언 누락이 아니다.
- 확인한 프로젝트/부모 경로에 `.venv`·`venv`가 없고 uv도 PATH에 없다. 두 Python 모두 jsonschema를 찾지 못했다. 기존 코어 import는 실제 exit 1, ModuleNotFoundError로 실패했다.
- 설치 대상으로 프로젝트 `.tools`의 uv·Python 3.11과 `.venv`의 잠금 파일 기준 실행 의존성을 사용자에게 제시했다. **아직 설치 승인을 받지 않아 설치하지 않았다. 전역 환경 변경 없음.**
- [environment-before.json](environment-before.json)에 실제 명령·argv·stdout·stderr·종료값·확인 경로가 있다. 이는 실행 사전조건 진단이고 스키마/검색 성공 증거가 아니다.

## 고정 입력과 단계 결과

[case-input.json](case-input.json)은 T876MEE1H1 / MFL71401557 Rev.00_032526 / 원문 p19 선반 분리 / 공개 실제 자료다. 기존 다운로드 PDF의 SHA256가 참고팩 원본과 일치한다. PDF 전문은 저장소에 복사하지 않았다. `F-M`은 참고팩의 출처 ID이며 업로드가 생성한 문서 ID가 아니다.

| 단계 | 실행 명령·입력 | 출력·근거 | 판정 |
|---|---|---|---|
| 업로드 | 업로드 명령 없음. 기존 PDF와 모델/버전 메타데이터를 입력으로 고정 | 두 API route 목록에 문서 업로드/등록 경로 없음. 문서 ID 미생성 | 미실행·미구현 |
| 파싱 | 등록 문서가 없어 명령 없음 | parser/파싱 Evidence 미생성. 이전 PDF 단독 추출을 이번 연결로 계산하지 않음 | 미실행·미구현 |
| 검증 | 파싱 출력이 없고 프로젝트 환경도 없음 | 기존 코어 import exit1 진단은 [environment-before.json](environment-before.json); Schema 결과 없음 | 미실행 |
| 조회 | 기존 GET `/api/evidence/search` 경로는 있음. 실제품 모델/문서 버전으로 조회할 예정 | 합성 전용 DemoStore가 기본. 이번 HTTP 응답/원문 재조회 없음 | 미실행 |

[r03-status.json](r03-status.json)에 각 단계의 입력·출력·미실행 이유와 런타임 메타데이터 확인 여부를 명시했다. 입력 파일 읽기·독립 텍스트 추출·ID 대조는 전체 연결 성공이 아니다.

## 구현 범위

[Issue #12](https://github.com/jeongiryang/lg-ax-2026/issues/12)는 자료/원문/모델/버전 계약과 재현 입력 준비다. [Issue #13](https://github.com/jeongiryang/lg-ax-2026/issues/13)은 문서 등록·파싱·조회·모델/버전 필터 구현이며 #12 의존 작업이다.

필요한 최소 수정은 등록 코어, 텍스트 PDF 파서, 검증 후 근거 저장, 등록 자료를 사용하는 모델/버전 조회다. 모델·문서/근거 ID·원문 위치·개정·public/synthetic 성격을 함께 유지해야 한다. API/MCP/공통 schema는 PM 담당 편집 영역이라 계약/접근 범위 조율이 필요하다. 이번에는 구현하지 않았다. OCR·새 UI·모델 비교·GPU 실행도 하지 않았다.

[implementation-inspection.json](implementation-inspection.json)은 코드/route 확인, [github-snapshot.json](github-snapshot.json)은 최신 #12/#13/PM CHECKPOINT와 main 코드 blob 대조, [phase2-readonly.json](phase2-readonly.json)은 기존 next/packet 실행 원문이다. online Project 직접 조회는 uv와 로컬 project_report.py가 없어 미실행이며 최신 Issue/main 조회와 구분한다.

## 다음 작업 하나

사용자가 프로젝트 내부 설치를 승인하면 기존 환경 기준으로 validator와 API 조회를 실행하고 실제 응답을 남긴다. 이는 업로드/파서가 없는 상태에서 부분 확인이며, 그 다음 #13의 등록·파싱 연결을 실제 구현해야 R03 완주를 재시도할 수 있다. #12 전체·PM 검수/병합/통합은 미완료로 유지한다.
