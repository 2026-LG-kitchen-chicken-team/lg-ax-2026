# DATA-W2-01a108a8-r2-0350 — 자료·표·후기 검수 후속

신진하(DATA), 2026-10-08 KST. 기준 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`. 새 worktree·branch `codex/data-w2-01a108a8-r2-0350`·새 출력 폴더에서 수행했다. 이전 [PR280](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/280) 결과는 head `507218bee95ac1f0f86259ca5942751b24a3ad03`을 읽기 pin으로 재사용한다. 이전 파일·코드·개인 README는 수정하지 않는다.

| 범위 | 확인한 부분 | 상충·미확인 |
|---|---|---|
| 자동 표 연결 | 기존 수동5셀·1각주54축과 CORE의 PR280 인수 댓글 재사용 | 실제 자동 graph/승인 adapter pin 추가 수신0. 자동 비교 검증 불가, 정확도·오류수 null. R9 기획 graph 대체0 |
| 후기 동향 | 원238건·개발141행·292인용·36빈 집계의 고정 결과와 SHA/승인 상태 재사용 | PM 승인 분류·지적 Source ID 추가 수신0. 행 수정0·월/계절 분모0·분자0·비율 null. 기존 후보4건 및 확장 미리보기는 승인 집계에 합산0 |
| 경쟁 제품 | T876MEE1H1/RM70F63R231의 공식 페이지3개/발췌12개→별도66-source adapter 연결 확인 | 870/640L·일반 설치/KitchenFit Max·후면 핸들 포함/미포함 기준이 달라 동일 조건 우위 주장은 상충. 내부 도달성/사용자 해결·새 모델 실행 소비는 미확인 |
| 김치냉장고/광파오븐 | Z330MEEF11의 미리보기3+공식3, ML32WW1의 공식4를 source ID/HTML SHA/조건과 연결 | 원 후기ID·게시일·구매SKU·고객 사용 Q&A 미확인. 제조사 기능7개를 고객 후기7건으로 세지 않음 |
| 새 설명서 후보 | 공식 지원 카탈로그2개에서 PDF URL3개→고유 PDF2개/총100쪽. 모델 연결·표지·판본·SHA·선택 구간 확인 | 두 문서 모두 공용. 정확 구매SKU/구매시점 판본·선택 기능은 조건부/미확인. ML32의 두 URL은 같은 SHA이며 문서2개로 세지 않음 |
| 기존 Q&A | MW25S 구매 문의와 DUE6BGL2E 설치 문의, 질문/공식답변4 source의 역할·날짜·인용 SHA 확인 | 실제 사용 후기/불편 분모0. 설치 질문119~120mm의 단위 의미는 미확인. 답변600mm는 인용문에서 확인;590/567~600은 발췌 밖 원답변 필요 |
| 실제 소비 여부 | 소스 코드 등록 경로·기존10-bundle 브라우저 요약 수신증·CORE의 고정 인수 댓글 확인 | 목록 등록/조회와 정확 Source ID의 실제 기획 입력 소비·현재 운영 서비스·품질 승인은 서로 다름. 이번 새 설명서의 소비는 미확인 |

새 자료/인수 연결 검사53개 PASS. 기존225회 실험·11문항 재채점·이전1,101검사를 반복하지 않았다. 모델/OCR0·제품 코드/기존 collector 실행0·새 DB/API/ZIP/모델 결과/독립 평가 검수0·Gold/최종 채점자 결정0·메일 읽기/발송0이다. 자동화는 팀/4개인 OFF이며 메일은 W3 담당이다.

- [자동 표 인계 상태](table-intake-status.json) · [후기 승인/분모 상태](trend-approval-status.json)
- [확장10 source 적용 조건](expansion-source-review.json) · [경쟁12 source 연결/비교 한계](competitor-source-review.json)
- [새 설명서2개 후보](manual-candidates.json) · [Q&A 역할·수치 적용 범위](qa-scope-review.json)
- [소비 단계별 근거](consumer-evidence.json) · [확인·상충·미확인8항목](findings.json) / [검수표](findings.csv)
- [입력 pin/신규 조회 SHA](input-pins.json) · [검사 결과](inspection-result.json) · [기존 파일 보존](scope-preservation.json)
- [상세 작업기록](work-record.md) · [검수 근거](evidence.md) · [실행 범위/예약/원 실패](execution-record.json)
- [PM 인계 요청 receipt](pm-handoff-request.json) · [#148: 필요한 graph/승인/원답변/소비 출력](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/148#issuecomment-6052081322)

다음 작업 하나: PM이 인계하는 실제 graph/승인 pin 또는 지적 Source ID에 해당하는 연결만 보완한다. 새 설명서·후기 후보의 승인/소비 여부와 Gold·최종 채점자는 PM이 결정한다. 현재 사용자가 직접 처리해야 할 항목은 없다.
