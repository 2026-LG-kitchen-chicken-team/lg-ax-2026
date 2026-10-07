# #13 R5 소비 결과 독립 검수 — 20261007-01a1100e

**현재: 검수 준비 완료 / 실제 R5 인계 미수신·미확인.**

이 작업은 앞서 나눈 1~5번의 별도 후속인 **6번(#13)**으로 구분한다. 1·2번은 원문/SKU/날짜/자동표, 3·4·5번은 검색/독립평가/집계, PM 보조 DATA는 수집/DB/Excel 구현을 진행한다. 이 폴더는 **등록 후 저장·개별 원문 조회·scope·재시작 보존**만 대조한다.

| 제출한 것 | 실제 의미 |
| --- | --- |
| [검수대조표](검수대조표.csv) | 13항목의 기대 입력·전/후 관측·담당을 준비. actual/null·미확인 유지 |
| [원문/현재 계약 pin](source-manifest.json) | 고정 main8b41의 실제 source 읽기·Git bytes 대조 |
| [비교기](consumer-audit.py) | 받은 원파일·DB export·metadata/original/evidence/search 캡처를 오프라인으로 대조 |
| [합성 확인](validator-self-checks.json) | 비교기 자체의22사례. 실제 DB/API/운영 검증이 아님 |
| [현재 결과](current-unreceived/result.json) | 미수신 입력에 UNCONFIRMED/exit2; 실제 문서/캡처0 |
| [인계 양식](인계양식.md), [템플릿](handoff-template.json) | audit 전용 입력 양식. 공통 Schema/API나 실제 R5 예측값이 아님 |
| [범위·인계 요청](범위와인계요청.md) | PM에게 필요한 고정 R5 팩과 실제 등록 후 캡처·재시작 증빙 |

## 중요한 대조 경계

개별 evidence API는 보존 CSV를 다시 import한다. DB 저장 record·metadata GET·original raw bytes·개별 evidence를 각각 받아야 저장/조회 보존을 판정할 수 있다. 직접 ID GET에는 model/version 필터가 없으므로 scope 검사에는 search의 정상/다른 유효 모델/미등록 모델/틀린 판본 캡처를 쓴다.

틀린 판본 HTTP 상태는 local documents400/public API404로 다르다. 문서 버전·dataset 버전·원파일 SHA·origins의 text SHA를 서로 다른 필드로 대조한다. 제공된 캡처 내용의 일치는 운영 출처·새 consumer commit 호환성·PM 승인·부모Done을 자동으로 입증하지 않는다.

## 수행·보존

고정 source: `8b41fd4785bc149593f04d913ef974f29fb341fe`. 새 별도 worktree/branch와 이 폴더만 사용했다. 기존 코드·자료·개인 README 수정0, 모델/OCR·생산 등록/API·서비스 재시작0이다. GitHub source/배정 조회와 합성 비교기 확인만 실행했다.

[작업 기록](work-record.md) · [근거](evidence.md) · [보존/확인](verification.json) · [입력 인수 상태](input-intake.json) · [산출물 manifest](artifact-manifest.json).

## 다음 행동

1. PM 보조 DATA의 고정 R5 팩과 실제 저장·조회·재시작 캡처를 인계받는다.
2. 새 소비 commit의 관련 source/계약을 고정 대조하고 이 비교기를 실제 파일에 적용한다.
3. 불일치·미확인을 원 ID/SHA와 함께 #13에 보고하고 실제 검수 추가 PR을 제출한다.
4. 다른 창의1~5번 결과는 해당 작성자 PR/head를 인수해 최종 자료 연결을 확인한다. 진행 중인1~5번을 재수행하지 않는다.
