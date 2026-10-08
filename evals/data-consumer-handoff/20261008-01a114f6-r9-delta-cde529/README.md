# DATA R9 새 CORE 후보 인수와 독립 전달 조건

신진하 DATA · 2026-10-08 · `20261008-01a114f6-r9-delta-cde529`. 최신 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`에서 이 창의 3번 범위만 진행했다. 공통 계약·생산 파일·공유 README는 읽기 전용이다.

## 새로 실제 받은 것

[CORE PR271](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/271)의 고정 head `548a1fa5629eb5d0e6d145b8e7dc8da8e78c4186`에서 검사 후보·후보 요약/상담 문맥·조건부 공식 참고 ZIP을 읽었다. 9개 고정 입력의 Git blob/bytes/SHA, 기존 Source6 metadata, 새 후보14/원문 구간26, PM 지적 연결8, 참고 ZIP1 entry를 대조했다. [원문 인수](intake-review.json) · [고정 입력](input-pins.json) · [검수 코드](verify_new_core_intake.py).

이 산출물은 **실제 수집 원문에 연결한 CORE 검사 후보**다. 최신 정상·조건 변경 모델의 실제 출력, 자동 표 graph, 승인된 adapter, 분류 승인, 원문 추출 성공으로 사용하지 않는다. CORE의 기존62검사·DATA의 기존14/16/34/225/50검사는 반복하지 않았다. 최신2 원출력에서 어떤 오류가 실제로 고쳐졌는지는 모두 미확인이다.

## 독립적으로 진행할 다음 단계

- 최신2 원출력: PM264 선언SHA는 PR273의 고정 인수를 재사용한다. 이 PC의 문서화된 localhost18969 GET은 연결 거부였다. HTTP status/body/SHA가 없으며, PM PC의 서비스 상태를 판단하는 결과도 아니다. [실제 GET 기록](http-get-receipt.json). 원 public JSON의 받은 필드부터 검수하며 full raw/usage 전체 도착을 불필요한 선행 조건으로 붙이지 않는다.
- 자동 표: PR258의 수동5셀/각주/Evidence 대응과 CORE 수신을 재사용한다. 실제 같은 PDF/판본의 자동 graph·승인 adapter는 미수신이다. PR271의 typed claim ledger는 자동 표 인수물이 아니다.
- 평가 ZIP: [새 CORE 수신 선언6050061005](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6050061005)은 README1/ZIP0이다. **승인된 기존 비공개 경로·PC 매핑·입력 읽기 범위가 확정되면 기존 input-only ZIP을 전달하고 실제 SHA/bytes/11-entry를 확인한다. 이 전달 단계에는 Gold·채점자·전체 R9 raw·자동 표 완료를 선행 조건으로 붙이지 않는다.** Gold·독립 채점자·동일입력 원결과는 이후 점수 생성 조건이다. [전달/평가 조건](handoff-gates.json).

[CORE 새 회신2와 본문 해시](received-core-notices.json)는 상대방의 인증된 선언으로 인수했다. DATA가 상대 PC 폴더에 직접 접근한 수신증은 아니다. 다른 창이 이미 보낸 ZIP 경로/export 요청과 회신 경로를 사용하며 추가 이메일은 발송하지 않았다.

## 자기 검수·한계

Docker 고정 image/UID65534/network none/root·input·code read-only/credentials mount0에서 새 후보 대조 PASS. 첫 helper가 기존 Source 키를 `id`로 잘못 읽은 실패는 [check0](history/check-0.log)에 보존하고 `source_id`로 고친 [check1](history/check-1.log)만 복구했다. [실행 경계·원 실패](history/runtime.json).

실제 최신2 원출력/자동 graph·adapter/원 평가 ZIP은 미수신이다. 모델/OCR·운영 재시작·자동화 ON·독립 점수·PM 승인·부모 Done은 0 또는 미확인이다. PR273 CI의 시작 제한은 이미 PM에 보고했으며 새 검사 성공으로 필수 CI를 대신하지 않는다. PM과 CORE는 PR271 후보를 기존 호출의 trusted envelope/recovery·private 저장에 연결할 범위를 조율한다.
