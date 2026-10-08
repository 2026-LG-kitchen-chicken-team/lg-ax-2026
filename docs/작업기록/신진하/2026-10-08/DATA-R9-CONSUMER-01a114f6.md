# DATA-R9-CONSUMER-01a114f6

- 담당: 신진하 / ginaginaring, 현재 사용자 지시를 수행하는 Codex.
- 시작: 2026-10-08 KST. 고정 시작 main: dc0ccc05916c637b2e0c2cc268a061dfa655c0b7.
- 편집: evals/data-consumer-handoff/20261008-01a114f6-r9-consumer/와 본인 날짜별 새 기록만.

## 실제 지시와 해석

사용자는 #14·#15와 실제 CORE 결과의 원문 대조를 맡겼다. 최신 main·PR262·R9 큐와 기존 완료 범위를 읽고 새로 바뀐 주장만 검수하며, 실제 원출력 미수신은 완료로 기록하지 말라고 했다. 자동 table graph/승인 adapter 및 승인된 비공개 전달 경로가 제공되면 기존 자료와 대조한다. 새 모델/OCR·운영 재시작·자동화 ON 없이 완료 단위마다 작은 PR을 제출하고 남은 역할을 정리한다.

AI 해석: 기존 PM findings/표 sidecar/ZIP 발신 검사는 재사용한다. 공개된 PM의 실행 보고를 원 JSON 수신이나 새 의미 검수로 대신하지 않는다. 원문에 대한 검토와 actual runtime/독립 평가를 분리한다.

## 착수·의존 확인

- 개인 인증 ginaginaring 확인. 관련 Gmail과 #14/#15/#234 및 PR257/258/262를 읽기 전용 확인.
- PR262는 2026-10-08T00:06:40Z 병합, 필수 CI4 성공. 이전 PR246~261의 통합과 부모 의미 품질 미승인을 구분.
- PM 최신 009/E056은 간결한 지침 뒤의 새 normal run-1f83d846191941aea21153897b944ec1과 revision run-754268c6b0cb41bba50c5b8d713332d9를 보고한다. 기존 semantic-review.json의5실험과 분리한다. 최신2 원출력/원입력/실행 code pin·SHA·모델/usage/같은 HTTP-MCP export는 이 창에 미수신.
- 사용자는 별도로 받은 R9 원출력·자동 graph/adapter·비공개 전송 경로가 없다고 답했다. 미수신분은 실검수로 승격하지 않는다.
- 다른 창 「제품 기획 단계 알아보기」가 R9 전체 자료/운영 무결성 검수를 수행 중이다. 본 창은 전체238/184 감사·생산 metadata 수정을 반복하지 않고 PM 의미 findings에 필요한6 source 경계와 실제 수신 단계만 다룬다.
- app create_worktree는 외부 빈 저장소의 기준으로 exact nested main을 못 찾아 실패했다. 실제 코드 저장소의 기존 commit으로 별도 branch/worktree를 만들었으며 원 dirty checkout은 그대로 유지했다.
- Docker image python:3.11-slim은 로컬에 없어 조회만 실패했다. 새 다운로드 대신 기존 고정 image d2b9d2d0d1da29f3226a8293340d63f58877a03b7189d3982123ff6995e8e01c를 사용한다.

## 진행·다음 행동

원문6개와 PM 원문/실행 보고를 고정 입력으로 받고 최신2실행의 인수표를 만든다. 기존5실험16 findings는 원 보고로 재사용한다. 보존 p49 이미지·native 발췌를 읽어 조건별 안내/다른 절 참조/공용판 적용 미확인을 보존한다. 결과는 source-only·network-none·credentials0 Docker로 자기 검수 후 작은 PR에 제출한다.

전체 실제 결과 검수·자동표·평가 전달·독립 채점·부모Done은 아직 미완료다. 공유 README·공통 계약·CORE/WEB/API·생산 자료는 읽기 전용이다.

## 첫 완료 단위·검증 결과

PM009/E056 최신 normal/revision2개와 원 semantic report의5실험16 findings를 구분한 인수표를 작성했다. 기존 PM findings를 새로 채점하거나 최신2에서 해결/재발했다고 전이하지 않았다. 참고 개발 후기4/공식p49발췌2의 객체·본문·14인용의원문범위를 고정했고, 이것은 최신 실제 selected ID receipt가 아니다.

source-only Docker에서 frozen Git blob11개+DATA 기대spec1개,6 Source·14 anchor·16기존finding 참조·기존5/새2보고를 검증해 exit0/PASS를 받았다.6 metadata probe가 수신/정확도/평가/완료 승격을 모두 거절했고 UID65534·입력/root쓰기 거절을 확인했다. 코드/환경/원로그는 [완료 단위](../../../../evals/data-consumer-handoff/20261008-01a114f6-r9-consumer/README.md)와 [자기 근거](../../../작업근거/신진하/2026-10-08/DATA-R9-CONSUMER-E-01a114f6.md)에 있다.

원문 대조의 경계: 배우자의 다리 불편, 구매 기대, 총 사용 약3달/어느 순간 냄새, 긍정+당황 문구, 설치기사의 고객 인식, 공용판 조건부 안내를 구분했다. 보존 p49 이미지도 직접 읽었고 원native suffix의 표 헤더를 절차로 쓰지 않는다.

#14는 기존 sidecar/CORE 수동 수신을 재사용하고 auto graph/adapter/accuracy/error_count/runtime은 미확인. #15는 기존 sender PASS와 실제 CORE 수신0을 구분하며 승인 경로·Gold·채점자·동일입력 원출력이 미수신. 새 모델/OCR/운영/공통 생산 변경0, 원표 sidecar/ZIP재생성0이다. 실제 수신이 필요한3부분은 계속 미완료이고 본 완료 단위만 PR 인수 요청한다.

## 작업 중 새 CORE 인수

최신 main이 CORE PR265 병합 `36bd1c5e60d220baebba9f7d76de6cba05cf2627`로 이동해 새 context Git blob/SHA를 인수했다. 별도 무인증 network-none·readonly·UID65534 Docker에서 새 metadata만 대조해6 source ID/본문SHA/판본·이전5run/SHA 일치 PASS를 받았다. 원 full raw/같은 HTTP-MCP 미수신과 최신2run이 manifest에 없음도 구분한다. 기존34 CORE검사나 본인 최초12pin검사를 반복하지 않았다.

원 실행 stdout/history의 CRLF를 Git이 LF로 바꾸는 경고를 발견했다. 원3파일은 외부 scratch에 보존하고 원SHA/bytes를 기록한 뒤 게시 텍스트 사본만 LF로 정규화하여 manifest와 Git blob byte 일치 조건을 맞춘다. 원 입력/Git blob·private Gold·생산 파일은 수정하지 않는다.
