# DATA13-R5-CONSUMER-01a1100e 근거

## 고정 source·의뢰

- source main: `8b41fd4785bc149593f04d913ef974f29fb341fe`.
- [PM R5 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-6028745109): 자료 생산과 신진하 독립 검수 경계.
- [1·2번 창 팩 인계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-6029129366): 이번 #13은 등록 후 DB/API 캡처를 추가로 받는다.
- [CORE 현재 canonical 소비 경계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029193144): ID·가전 모델·문서 판본·원문 위치·origins와 자동 표 graph를 구분.
- [PM의 기존 운영 검증](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-6028048853): 원 R4/원 실행의 배포·조회·재시작 범위. 새 R5의 증거가 아님.

## 산출물

- [source-manifest.json](source-manifest.json): 실제 계약/API/DB 구현10source의 Git blob·원 bytes SHA·행 번호.
- [protected-baseline.json](protected-baseline.json): 기존3,661파일 보존 기준.
- [검수대조표.csv](검수대조표.csv): 13항목, actual before/after null·미확인.
- [input-intake.json](input-intake.json): 새 고정 팩·DB/API·재시작 인계0.
- [consumer-audit.py](consumer-audit.py): 폴더 안의 공급 파일만 읽는 오프라인 비교기.
- [validator-self-checks.json](validator-self-checks.json): 현재 비교기 SHA와 합성22사례. product/API/model 실행이 아님.
- [current-unreceived/result.json](current-unreceived/result.json): actual UNCONFIRMED·documents/captures0. exit2를 예상했다.
- [verification.json](verification.json): 기존 files/source 일치·합성 확인과 실제 미검증을 분리.
- [인계양식.md](인계양식.md)·[범위와인계요청.md](범위와인계요청.md): 실제 공급 담당과 명세. 공통 계약 채택/운영 승인으로 해석하지 않는다.

## 실행

PDF 라이브러리가 있는 기존 bundled Python을 사용했다. 아래 새 helper만 실행했고 repository producer·service·모델/OCR은 실행하지 않았다.

```text
python check-validator.py
python consumer-audit.py --packet handoff-template.json --output current-unreceived
python build-audit-report.py
```

`current-unreceived`는 처음 실행한 결과를 보존한다. 비교기는 비어 있지 않은 결과 폴더를 덮어쓰지 않는다. 실제 packet이 공급되면 새 결과 폴더를 사용한다. manifest SHA와 실제 Git blob 게시 검증은 별도로 확인한다.

실제 운영 출처·consumer commit 계약호환·PM 승인·#13 Done은 남아 있다. 준비 검사의22통과를 실 DB/API/재시작 보존22건으로 표현하지 않는다.
