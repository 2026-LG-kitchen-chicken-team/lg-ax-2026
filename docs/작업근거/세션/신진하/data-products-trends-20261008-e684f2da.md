# 제품 자료와 후기 통계 검수 근거 — 20261008-e684f2da

담당 신진하 / ginaginaring. 수행 AI Codex. 기준 main eab85d48385f965eef48c07a6cdd8f6fd9851c62. 검수 결과는 [이번 폴더](../../../../evals/data-parallel/w2/2026-10-08-e684f2da/README.md)에 연결한다.

입력: 최신 main의 238records·D1 membership·141행 주제 초안/원문 source/기간 sidecar와 PR270/282/290/293/295 정확 head의 인수 JSON을 읽었다. [input-pins](../../../../evals/data-parallel/w2/2026-10-08-e684f2da/input-pins.json)에 commit/path/blob/SHA/bytes를 기록했다. 다른 창의 파일은 읽기 전용으로 유지했다. 승인된 사서함 점검은 검색 12건(알림11·기존SENT1), 기존 PM 스레드9SENT/수신0 범위였다. 원주소·전문은 공개하지 않았다.

실행: 자체 오프라인 감사기의 [동일 코드](../../../../evals/data-parallel/w2/2026-10-08-e684f2da/audit-source.py.txt)로 자료 ID·hash·판본·위치·분할·분모를 대조했다. 새 공개 후보 2기사만 HTTP GET200으로 읽었고 raw와 첫 파서 실패를 private에 보존했다. 기사 게시/수정 날짜·본문 SHA·7개 조건 범위를 재파싱한 결과는 [후보](../../../../evals/data-parallel/w2/2026-10-08-e684f2da/new-review-candidates.json)다. 인증/로그인·숨은 수집 API·모델/OCR을 사용하지 않았다.

결과: 고유238·개발141/평가36/시연49/격리12, 원ID860977 중복 관측1. 117항목/292 source spans 일치·오류0. 18페이지 모델과 설명서 후보 연결, 당시판 확인0. 현 후보 판본 날짜가 표시구매일보다 늦은38(개발18) 기록. 기존 게시일0·승인 주제0, 월/계절 분모0·ratio null. 긍정106/부정13/혼합16/불확실3/중립3은 기존 draft 산술이고 의미/승인 정확도 평가가 아니다.

새 후보: ML32WW1 글의 visible date/datePublished/dateModified 2024-07-20 일치. 작성자 모델 진술·사용/불편·미사용 조건을 구분했다. 인수한2025설명서를2024당시판으로 쓰지 않았다. Z330MEEF11 제휴 글은 published2025-09-19/modified2026-08-15·구매 진위/당시 내용 미확인으로 보류. 후보2의 날짜 근거를 기존141에 합산0.

원 실패: 첫 기사 parser의 void/self-closing 요소 깊이 처리로 본문 일부가 빠졌다. 원파일 보존 후 같은 entity로 오프라인 수정, 재GET0. 오프라인 감사기 최초 document_version·quarantined KeyError2는59행의 선택 필드 차이에 대한 reader 오류이며 원문/초안 오류로 보고하지 않았다. 원 코드를 private에 보존했다. 수정된 감사 결과만 유효 근거다.

한계: exact 구매 SKU·당시판본·공용 선택기능 전체 적용, 주제 승인/지적행, 같은 조건 경쟁제품 효과, 후기 진위/시장대표성/독립성 승인, 운영 사용 여부는 미확인. 공식FAQ는 고객 불편 분모가 아니다. Gold·최종 독립 채점을 수행하지 않았다. 모델 IDs/settings/input/output는 새로 생성되지 않았으며 동일 감사 코드 SHA/기준 commit과 원문 입력·출력·실패를 연결했다.

출력/JSON·링크·scope·원파일/hash·게시 Gitblob 확인 및 실제 PR/보고 수신은 상세 작업기록의 종료 부분과 별도 게시 수신증에 연결한다. 공유README/기존코드·자료/CSV/타창변경0, 자동화OFF 유지.

게시 정정 근거: 최초299head930e25247bd75a96e06640c3eebb05519115eadf 보존, staged 신규파일을 원본 목록에 넣은 reader 및 후속게시 gate 오류를 수정했다. 원본 목록은고정base4741만사용하고 정정117항목/292원문범위·17payload manifest·18Gitblob exact bytes를 재확인한 최종head를 유효 인수 근거로 쓴다.
