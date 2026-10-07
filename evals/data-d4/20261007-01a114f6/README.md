# D4 고정 원문·분할·Excel 독립 검수

담당 신진하/ginaginaring, 세션01a114f6. 생산자는 LGAX #12의 D1·D2 창이며 이 디렉터리는 생산 코드/자료를 편집하지 않는다.

## 현재 범위

audit_delivery.py는 생산자 함수를 import하지 않는 별도 표준 라이브러리 감사 코드다.
238개 원 기록·관측239개·추가 관측860977·기존 분할/그룹·게시일/SKU null·개발전용3Bundle·연구 SQLite의 원 기록·읽기 전용 Excel 내용을 대조한다.
운영 DB/API/MCP 배포·재시작, 새 모델/OCR 호출, 실제 의미 Gold 채점과 독립 사용 승인은 이 검수의 범위가 아니다.

고정 producer commit6fd98c01b3c6f1abf4741df2130a485142eeeae4의 version lg-public-research.20261007.d1-01a10600.v1을 읽기 전용으로 인수했다.
result.json의 검수는238고유·239관측·원문/분할·개발전용48/48/45입력·Excel238원문과 날짜/SKU null·원소스/manifest를 통과했다.
원 키 누락/변경 없이 DB에 추가된59건의 dedup_group_id는 원 body_group_id의 명시적 별칭으로 대조했다.
원 metadata dict 전체동일 가정/누락 quarantine 필드의 첫 두 실패는 history/와 기록에 보존했다. 생산 파일은 수정하지 않았다.

이 결과는 로컬 고정 commit의 인수다. 생산자의 이후 P0 canonical 실행입력 변경·원격 PR 인수·운영/API/MCP·실모델 의미 품질·Gold 승인·독립사용 승인과 부모 Done은 별도다.
result.json, producer-receipt.json, execution.json이 실제 고정 입력·검사·격리 설정의 근거다.

## 인수 조건·재현

생산자가 고정한 commit/head·version·manifest와 Git 바이트를 대조한 receipt를 먼저 받아야 한다.
receipt의 SHA/크기·producer_version·producer_head는 보호된 실제 Git 조회/고정 파일과 연결된 인계 근거가 필요하다.
JSON의 선언만으로 sender 인증이나 상대 수신을 입증하지 않는다.
research SQLite·검토용 XLSX는 해당 manifest/전달 증빙의 원 해시와 대조해 별도 읽기 전용 복사본으로 받는다.
Gold/답안/방식키/인증 프로필·개인 경로는 mount하지 않는다.

고정 Docker의 별도 source 복사본, network=none/auth=none/read-only 입력에서:

`python audit_delivery.py --source-root /source --producer /producer --receipt /receipt/producer.json --xlsx /workbook/reviews.xlsx --output /out/audit.json`

결과는 새 입력 버전과 새 source SHA를 명시한다. 경합 중 파일, 누락 입력, 기존 불완전 복사본 검사를 완주로 바꾸지 않는다.
독립 평가/시연 분할은 원 분할의 보존 여부만 검사하고 Gold/실모델 품질을 채점하지 않는다.

## 후속 프롬프트·팀 전달

- [창별3작업 프롬프트](../../../docs/작업기록/신진하/2026-10-07/followup-prompts-01a114f6.md)
- [원 팀 메시지와 남은 역할](../../../docs/작업기록/신진하/2026-10-07/team-handoff-gaps-01a114f6.md)
- [이 창의 직접 지시/진행 기록](../../../docs/작업기록/신진하/2026-10-07/신진하-20261007-D4-AUDIT-01a114f6.md)
