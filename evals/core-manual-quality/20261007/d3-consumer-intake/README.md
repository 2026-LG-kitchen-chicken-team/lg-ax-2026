# CORE의 D3 소비 준비 대조

새 DATA PR244의 고정 산출물과 development 원 후기848850을 연결한 부분 검수다. 제품 실행이나 모델 품질 검증이 아니다.

- [소비 조건·원 문맥4구간·입력 pins](consumer-intake.json)
- [검증기](verify_intake.py), [실제 출력](source-check.log), [격리 수신](validation.json)
- [수행 기록](../../../../docs/작업기록/황대겸/2026-10-07/CORE-D3-CONSUMER-INTAKE-01a10729-01.md), [근거](../../../../docs/작업근거/황대겸/2026-10-07/CORE-D3-CONSUMER-INTAKE-01a10729-01.md)

입력은 consumer-intake.json의 정확 head/path/SHA에서 읽는다. PR244 pack과 원 후기 파일을 별도 source-only 복사본으로 확보해, 인증/.git/모델 연결 없이 고정 Docker에서 아래 대조를 실행한다.

```text
python -I verify_intake.py --pack pack --reviews reviews.json --intake consumer-intake.json
```

원 후기의 설치 제약·긍정 경험·잔여 불편을 보존하고, 경쟁제품 외형 깊이에서 내부 접근/효과를 추론하지 않는 소비 조건을 기록했다. 연구 sidecar ID/정규화 문자 위치는 현재 canonical Evidence의 승인된 ID·locator가 아니다. after 장면과 신규 콘셉트 방향은 미생성 상태다.

DATA의 원 HTML 수집·재생성 수신은 재사용했다. 이번 검사는 게시된 발췌 hash와 문맥 연결만 확인하며 원 HTML/물리 효과/고객 만족/실제 Agent 입력/PM 인수는 승인하지 않는다. P0·첫 문제·D1/D2 입력·C1/C2/C3 고정 흐름은 별도 의존이다.
