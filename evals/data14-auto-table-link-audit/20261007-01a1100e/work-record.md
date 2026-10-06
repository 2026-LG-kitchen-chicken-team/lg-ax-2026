# 신진하 — 2026-10-07 — DATA14-AUTO-TABLE-AUDIT-01a1100e

## 지시·의도

사용자 지시: 기존 OCR·ocr-error-ledger·ocr-table-review-plan·PR191/193을 원본 PDF와 대조하고 자동 행·열·제품모델·숫자·단위·각주 연결의 실제 출력을 확인한다. 별도 작업 공간/새 고유 폴더만 쓰고 기존 코드·자료·개인 README 수정과 모델/OCR 재실행을 금지했다. 검수 가능한 부분은 PR로 제출하고 결함/필요 출력을 보고한다.

이 직접 지시를 따라 기존 개인 README는 읽기만 했다. 날짜·고유 기록 ID가 있는 상세 기록과 근거를 이 새 폴더에 보관한다. 자동화 OFF 유지. 모델/OCR 코드나 다른 팀원의 판단 코드는 실행/수정하지 않았다.

## 확인한 핵심 사항

- 고정 source main: `9cd2d56be52588764c18c109c9ffca4c104bd48c`.
- 별도 worktree: `.worktrees/data14-auto-table-audit-20261007-01a1100e`.
- branch: `codex/data14-auto-table-audit-20261007-01a1100e`.
- 새 경로: `evals/data14-auto-table-link-audit/20261007-01a1100e/`.
- PDF skill 적용: 원본 3개를 읽어 표지/관련 페이지 9장과 원 crop 좌표의14영역을 PDFium으로 렌더링하고 직접 보았다. PDF native text층은 문자 대조의 보조 근거다.
- PR191·193의 실제 merged/head와 PM 검수 댓글은 [github-sources.json](github-sources.json)으로 고정했다. PM의 부분 수동 인수를 자동 추출 승인으로 바꾸지 않았다.
- 보관 OCR-v3 70회 결과·runner SHA·ledger/plan 사본을 확인했다. `rec_text/rec_score`, regex 숫자/단위와 수동 지정 모델/열 metadata는 있으나 자동 구조 출력은 없다.
- PR191 19행과 PR193 22행은 원 ID를 유지해 별도 대조했다. 문자 8영역 일치/6영역 차이, 각주 번호의 본값 오염1사례를 기존 점수와 함께 보존했다.
- 24개 원문 참조에 행·열·모델·숫자·단위·각주/조건 6종 질문을 작성했다. 144질문 모두 자동 구조 출력 부재로 검증 불가이며 정확도/오류 건수는 null이다. 질문 수는 성능 표본/분모가 아니다.

## 내 작업에 미치는 영향

수동 crop에서 읽힌 값은 자동 모델/열·병합 셀·단위 상속·각주 연결을 증명하지 않는다. 실제 구조화 출력이 필요한 부분은 미완료로 유지하고, 이번 범위의 원문 대조와 검수표를 부분 제출한다. 특정 SKU 유형/부품, 모델별 기능 적용, 외부5 cm 출처는 이번 PDF만으로 확정하지 않는다.

## 선행 담당자·필요 산출물·협의

- DATA `@ginaginaring`: 보유 중인 기존 table/cell/header/footnote 구조 출력과 역사적14crop PNG 보관 위치·SHA. 없다면 생산 구현/출력 작업 범위를 별도로 받아야 한다.
- PM `@jeongiryang`: 이 부분 원문 검수의 인수와 구조 출력 제공/생산 담당·계약 조정. [required-outputs.md](required-outputs.md)에 필요한 정보를 구체화했다.
- CORE/WEB/공통 계약 코드를 수정하거나 다른 담당자의 진행·Done을 대신 기록하지 않는다. 이번 PR은 새 검수 자료만 포함한다.

## 실제 수행·근거

1. source commit의 기존 tracked 3,148개 파일 bytes/SHA baseline을 저장했다.
2. 원 PDF SHA·표지 개정·페이지/원crop 좌표를 대조하고 비교용 새 이미지를 직접 열었다.
3. 저장70시도와14영역, 두 과거 PR의41행, plan3건을 연결했다.
4. 현재 producer/parser/등록 source를 정적으로 읽고 실제 보관 JSON 키를 확인했다. 모델/OCR·생산 parser/등록 API 재실행은 없다.
5. `audit-builder.py.txt`는 stdlib와 PDF text층 읽기만으로 검수표/CSV·SHA·일관성 확인을 작성한다. 이 새 폴더 밖에 쓰지 않고 repository producer를 import하지 않는다. `verification.json`이 실제 확인 범위를 기록한다.
6. 게시 전 기존3,148파일·Git diff 경계를 다시 확인하고 새 산출물 SHA manifest와 PR을 연결한다. PM 검수·병합·부모Done은 대기 상태다.

## 보존한 진행 진단

- 앱 managed-worktree 도구는 이 umbrella 환경에서 고정 ref를 해석하지 못했다. 원본 checkout을 바꾸지 않고 기존 managed 저장소의 Git worktree 기능으로 위 별도 branch/check-out을 만들었다.
- 읽기 도중 Python 기본 CP949가 `∗` 출력에서 실패했고, JSON list를 dict로 읽은 프로브와 없는 검증 파일명을 찾은 검색이 실패했다. 읽기 전용 진단이며 입력 변형이나 모델/OCR 실행은 없었다. UTF-8 출력/실제 구조·경로로 다시 읽어 해결했다.
- 역사적 crop PNG 원파일은 고정 Git snapshot에 없으므로 원crop bytes 검증은 미확인으로 남겼다. 새 비교 렌더를 그 원파일인 것처럼 표시하지 않았다.

## 다음 행동·상태

원문/기존 출력 검수 자료는 PR 검토 요청. #14에 담당자를 태그해 실제 구조 출력과 보관 입력을 요청한다. 실제 연결 출력 수령·추가 구현 배정 후 별도 범위에서 대조할 수 있다. 이번 작업은 단계1~7 진행률이나 전체 #14 완료를 주장하지 않는다.
