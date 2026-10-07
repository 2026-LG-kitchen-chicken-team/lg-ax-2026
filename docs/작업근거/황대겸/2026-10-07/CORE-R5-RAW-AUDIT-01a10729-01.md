# CORE-R5-RAW-AUDIT-01a10729-01 — 원3응답 인수·독립 대조 근거

황대겸 / unknownamed, 2026-10-07 KST. 원 지시·해석·수행은 [같은 ID 기록](../../../작업기록/황대겸/2026-10-07/CORE-R5-RAW-AUDIT-01a10729-01.md), 원 반례·판정표·재현·해시는 [독립 검수 근거](../../../../evals/core-manual-quality/20261007/r5-independent/README.md)에 있다.

인계 커밋은 `814fe2fbcd3b752ff6400d8a08671dce7bdd2d80`, 원 모델 코드는 `de09b64ca72d5ae918cc0a95f244b0e0562761b0`, 기존 main 기준은 `1f3f4ecb93fdd945850a1e9f790bc37766b2355c`이다. 모델 digest는 `8b9d11d807c57feb1e2ecb0d6cbf40334c37dcc3523bed5540af4f927f112a37`이고 합성 냉장고 입력이다. manifest의 원 세 output SHA/바이트와 실제 다운로드 bytes를 대조했으며 원본을 재작성하거나 모델에 재전송하지 않았다.

실제 원문 대조: 정상의 RE008은 후보와 mechanism 검수에는 있으나 difference 검수에는 없다. 수정2의 held/questions[]/hold_reasons[]는 HOLD_WITHOUT_QUESTIONS로 거절됐다. 조건 변경 CONCEPT002/003의 두 시도는 MANUAL001 누락이며 실제 feedback은 code/stage만 제공했다. 설명서 부족의 NEED006은 RE007과 연결되어 검수 입력·reviewed_output·최종 output에 모두 있는데 원 검수 주장은 누락이라고 했다. features=[]에 대한 설명서 부족 held는 그대로 적절하다.

고정 Docker의 stdlib 대조기는 모델 응답15개의 raw/generated 동일, 원 호출6/5/4와 토큰42626/27769/21192, 수정 최대2 및 위 경로를 실제 검증했다. 비교 JSON SHA256은 `1a0eb0e71c1a1742773c981bb4aee1303e27b0d9d50490cdfb7eefff72c205af`이다. 이미지/격리·초기 세 locator 실패와 복구·검사 범위는 manifest에 기록한다. 새 제품 기능/모델/성능/기존 원6 재평가를 실행한 근거가 아니다.

미검증: 새 PM 수정 head, 새 코드의 반례 해결, 실모델 정상/변경 완주, 실제 후기 3제품 품질, PM 승인/병합/운영 release/Done. 다음은 정확 head 인수와 같은 원문/코드 독립 대조다. 현재 별도 사용자 판단은 필요하지 않으며 원 실패/비용·Worker OFF·20분 비중단 지시는 유지한다.
