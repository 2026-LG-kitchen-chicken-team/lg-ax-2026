# DATA-W2-01a108a8-7b67e6

신진하(DATA) · 2026-10-08 KST · 수동 자료 보완/검수. 상태: 부분 결과 검수 요청 준비. 부모 완료·분류 승인·자동 표 검증은 미완료.

- 기준 main: `eab85d48385f965eef48c07a6cdd8f6fd9851c62`.
- 별도 branch: `codex/data-w2-01a108a8-7b67e6`.
- PR270 읽기 pin: `33b6312721c79f234f035fbe408f7d570fa6c36d` (open/unmerged).
- PR272 읽기 pin: `0a811ffa6d07f7cf8f5590ef86e3174dd7936108` (open/unmerged).
- 중앙 조회: 팀/4명 OFF. 최초 본인 예약을 해제한 뒤 출력 폴더와 신규 보고 연결 문서 2개의 경로를 합쳐 `manual-data-w2-final-01a108a8-7b67e6`으로 예약했다. 다른 세션 예약은 바꾸지 않았다.
- 메일 조회/발송은 사용자 지시에 따라 3창 담당이다. 이 창은 메일을 열거나 보내지 않는다.

## 범위와 인수 조건

1. #14: 기존 수동 OCR/표 검수와 원 PDF를 재사용한다. 실제 automatic table graph 및 승인 adapter의 commit/version/config pin을 수신해야 자동 출력과 대조할 수 있다. 미수신은 검증 불가이며 자동 정확도/오류수는 null이다. R9 기획 근거 graph는 자동 table graph의 대체물이 아니다.
2. #16/#148: 기존 development 141행 주제 초안만 재사용한다. PM 분류 승인/지적 Source ID 없이는 분류를 바꾸지 않는다. 원문 연결·분자/분모·중복·격리·미상 날짜 제외를 검수하며 게시일 미상이면 월/계절 분모0·ratio=null을 유지한다.
3. 15모델 설명서 후보와 PR270 보완 자료를 재사용한다. 정확 구매 SKU/구매시점 판본·게시일 근거가 있는 실제 후기/Q&A의 빈칸을 조사하며 새 자료는 별도 후보에만 기록한다. FAQ는 제조사 안내로 유지한다.

기존 코드·자료·CSV 8열·개인 README·다른 창 파일 변경, 모델/OCR/기존 수집기 재실행, DB/API·모델결과·ZIP·독립평가 승인·자동화 ON을 수행하지 않았다. 신규 자료와 상세 검수 결과는 이 폴더에 둔다. #16 인증 보고가 허용하는 신규 개인 세션 경로에는 이 폴더를 가리키는 연결 문서 2개만 추가한다.

## 완료 범위와 근거

| 범위 | 실제 관측 | 완료하지 않은 판단 |
|---|---|---|
| 기존 수동 표 5셀·1각주 | PDF 2개의 고정 SHA·native 구간·기존 렌더를 대조하고 9축×6항목=54행 기록. 수동 근거 일치49, 수치 셀이 아닌 각주의 해당 축 미확인5, 오류0 | 자동 table graph/adapter 미수신. 자동 비교54행 모두 검증 불가, 정확도·오류수 null. 도형 bbox 미확인 |
| 기존 141행 초안 | Source ID·원ID·인용292곳·구간/해시·주제 membership·격리·미상 날짜·저장된 빈 집계36개 대조 | PM 승인·지적 Source ID 미수신. 분류 수정0·의미 정확도 null. 월/계절 분모0·분자0·비율 null |
| 기존 15모델 설명서 | 원 PDF 19참조/15개 고유 SHA를 읽어 기존 파일 해시와 일치 확인. PR270의 범위 확정5/조건부10을 재사용 | 구매 SKU 확인0·구매 당시 판본 확인0·선택 기능 확정0 |
| 새로운 실제 후기 후보 | 판매처 공개 후기 4건의 게시물 ID·본문 연결·날짜 표시·원 응답 SHA·판본 시점 차이 보존 | 독립 구매자·정확 구매SKU·게시/수정 날짜 의미 미확인. 승인 분모 증가0, 기존238/141행 합산0 |
| 고객 사용 Q&A | MW20GDN 공개 초기 페이지 응답 확보 | 연결된 개별 질문ID·질문·답변·게시일은 미수신. 새 Q&A0, 제조사 FAQ를 고객 후기/불편 분모로 전환0 |

정적 자료 연결 검사 1,101개 PASS는 위의 고정 자료·구간·집계 조건 검사다. 자동 표 품질, 주제 분류의 의미 정확도, 제품 사양 실측, 독립 평가, 운영 실행 성공의 증거로 사용하지 않는다.

- [표 대조 결과](table-review.json) / [54행 검수표](table-review.csv)
- [141행·집계 검수](trend-review.json) / [원문 연결별 검수표](trend-row-review.csv)
- [15모델 적용·구매 SKU/판본 공백](manual-gap-review.json)
- [신규 후기 후보 4건](review-candidates.json) / [공개 원 응답 6건의 조회 근거](new-source-receipts.json)
- [입력 commit·버전·SHA](input-pins.json) / [정적 검사 결과](inspection-result.json)
- [검수 근거·한계](evidence.md) / [지시 해석·실제 수행·실패 기록](work-record.md)
- [PM 인계 요청](pm-handoff-requests.json): [#14 자동 표·adapter](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6050704556), [#148 분류·SKU·날짜](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/148#issuecomment-6050704880)

다음 작업 하나: PM이 제공하는 승인 pin 또는 지적 Source ID를 받으면 해당 표 연결/행만 보완한다. 현재 사용자가 직접 처리해야 할 항목은 없다.
