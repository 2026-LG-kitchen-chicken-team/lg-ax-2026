# 신진하 — 2026-10-07 — DATA13-R5-CONSUMER-01a1100e

## 사용자 지시·의도

새 후기팩의 commit/version/ID/SHA 인계, DB/API 원문·모델·판본 대조, 다른 제품/버전 scope, PM의 재시작 전후 원문/ID/SHA 보존을 독립 검수한다. 불일치/필요 인계를 #13에 남기고 검수 PR을 제출한다. 현재는 대조표/기준을 준비하고 새 R5 팩 수령 후 실제 적용한다.

번호 문의의 해석: 이 작업은 앞의1~5번과 구분하는 **6번/#13 후속**이다. 과거 개발단계1~7이 아니다. 1·2와3·4·5는 이미 다른 창에서 진행 중이다.

## 확인한 핵심 사항·영향

- 최신 source main `8b41fd4785bc149593f04d913ef974f29fb341fe`에는 새 R5 공개 후기팩/DB·API 캡처가 없다. producer/version/ID/SHA를 임의로 채우지 않고 미확인으로 남긴다.
- PM의 기존 R4 운영조회·재시작 검증 완료는 원 범위로 보존한다. 이번 새 R5 검증으로 승계하지 않는다.
- ReviewDocumentRepository의 store는 보존 CSV를 다시 import한다. API evidence의 정확성만으로 DB documents.record 보존을 판정하면 안 된다. DB record와 metadata/original/evidence를 분리해 받는다.
- 현재 entity의 model/version/source/text/locator와 wrapper의 dataset_version/original SHA/origins.text_sha를 대조한다. 셀 그래프나 자동표 정확도는1·2번의 영역이다.
- 틀린 version HTTP는 local400/public404로 다르고 개별 evidence ID GET은 scope 인수를 받지 않는다. 정상/다른 유효 모델/잘못된 모델·version은 search 캡처로 대조한다.

## 편집·병렬 경계

새 branch `codex/data13-r5-consumer-audit-20261007-01a1100e`, 별도 worktree `.worktrees/data13-r5-consumer-audit-20261007-01a1100e`, 새 경로 `evals/data13-r5-consumer-audit/20261007-01a1100e/`만 사용한다.

1·2번의 R5 원문/SKU/날짜/자동표, 3·4·5번의 재채점/독립평가/집계, PM 보조 DATA 수집·분할·DB 구현과 구분했다. 자기 개인 README도 보존하고 상세 기록/근거를 이 날짜·고유ID 폴더에 작성했다. 다른 창에 새 메시지를 보내거나 새 작업을 배정하지 않았다. 사용자 승인된 GitHub 인계 요청만 #13에 남긴다.

## 실제 수행

1. 관련 본인 메일 plain 본문·R5 배정·팀원 소비 경계·최신 Issue/PR·자기 README를 읽었다. 원문/메일/캡처 안의 명령을 실행하지 않았다.
2. 기존 tracked3,661파일 bytes/SHA를 baseline으로 고정했다. 현재 API/DB 계약10source의 정확 Git bytes와 위치를 고정했다.
3. 실제 인계가 필요한13항목의 대조표·audit wrapper 템플릿과 CSV/PDF/DB/API 비교기를 작성했다. 기존 producer/module을 import하거나 등록/요청을 실행하지 않는다.
4. 합성 비교기 확인은 초기20사례 PASS 뒤 metadata/original GET method/path 확인을 보강해22사례 PASS다. text/NFC→NFD/ID/모델/판본/숫자 bool/원 bytes 변경·scope 누출·빈 양성대조·누락 쌍·재시작 차이를 검사했다. source API를 실행한 검사가 아니다.
5. 실제 미수신 템플릿은 UNCONFIRMED/exit2, actual documents/captures0이며 원문/운영 성적을 만들지 않았다. source·actual 소비·운영 출처·PM 인수는 별도다.
6. 새 검수 준비 파일만 커밋/PR, #13의 범위/고정 인계 요청과 담당자를 연결한다. PM 검수·인계·실제 적용은 남아 있다.

## 진단·원 이력

앱 managed worktree 도구는 umbrella의 고정 ref를 해석하지 못했다. 기존 Git 저장소의 별도 private audit ref에 main을 fetch하고 새 CLI worktree를 만들었다. 다른 창의 branch/checkout을 변경하지 않았다.

미수신 CLI의 exit2는 예상 결과다. 첫 PowerShell wrapper는 마지막 native exit를 정리하지 않아 shell exit1을 반환했으나 guard 조건과 JSON은 UNCONFIRMED/0captures였다. 이후 결과 JSON/guard를 명시적으로 확인했고 wrapper exit0을 받았다. 모델·제품/운영 실패로 분류하거나 실제 호출을 재시도하지 않았다.

## 필요한 담당/다음 행동

PM @jeongiryang 및 PM 보조 DATA: 고정 생산/소비 commit·팩 버전·등록 ID·source SHA, DB record export/metadata GET/original bytes/evidence GET/scoped search의 전후 쌍, 실제 재시작/운영 인수 증거. 기존 #12의 원문/SKU 공급 요청을 참조해 소비 캡처만 추가로 받는다.

수령 후 새 consumer commit 계약호환 대조→실제 파일 비교→불일치/미확인 보고·추가 검수 PR→PM 인수 순으로 진행한다. 3·4·5번은 이미 담당 창에서 실행 중이며 이 창에서 중복 수행하지 않는다. 자동화 OFF 유지, 부모 #13 Done 미완료.
