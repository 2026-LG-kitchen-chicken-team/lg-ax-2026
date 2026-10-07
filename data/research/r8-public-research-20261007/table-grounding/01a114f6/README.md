# DATA14 두 페이지의 표·Evidence 관계

입력은 고정 DUE6BGL2E 설명서 p57과 MW23FDI p37이다. PDF·판본·native page text·기존 전체페이지 render·canonical dataset의 바이트/SHA를 table-evidence-sidecar.json에서 연결한다.
기존 원문의 시각 확인과 native 문자열 범위에 기반한 별도 관계 자료다. 새로운 automatic producer graph/승인 adapter는 미수신이며 자동 정확도·오류 건수는 null이다.

| 대상 | 적용 관계 | 기존 Evidence | 주의할 연결 |
|---|---|---|---|
| DUE6BGL2E | DUE6****E 모델 열의 빌트인 치수 | DATA003-DUE6BGL2E-D03 | 815mm의 왼쪽 프리스탠딩 상판제거 조건과 오른쪽 빌트인 조건을 합치지 않는다. |
| DFE 프리스탠딩 참조 | 일반 높이845mm, 상판제거 시815mm | 같은 넓은D03 인용 안의 참조 열 | DUE 대상 값으로 잘못 선택하지 않는다. |
| MW23FDI 소비전력 | 전기 입력1570W, 두 모델 열 공통 셀 | DATA003-MW23FDI-M06/M07 | 고주파 출력으로 재명명하지 않는다. |
| MW23FDI 고주파 출력 | 최대1000W와 시간 조건 각주1 | DATA003-MW23FDI-M06 | M07에는 출력/각주가 없으므로 M07만 연결하지 않는다. |

각 cell/footnote는 native page의 0-based end-exclusive 문자 범위·내용 SHA·짧은 anchor를 가진다.
연속 canonical 인용은 그대로 해시/범위/locator로 참조하고 떨어진 셀을 새 연속 인용처럼 작성하지 않았다.
header/column 관계는 원 render를 읽은 Codex의 source-derived 해석이다. native 문자 선택을 자동 table/OCR 의미 정확도로 주장하지 않는다.
feature_ids의 빈 배열은 유지했고 canonical Schema/CORE 어댑터·생산 파일은 변경하지 않았다.

build_table_sidecar.py는 기존 native/parser 파일에서 이 별도 자료를 재생성한다.
verify_table_sidecar.py는 원 파일/인용·조건·단위·각주 연결을 대조하고 잘못된 높이/조건/M07출력/전력종류/누락각주의 다섯 메모리 변조를 거절한다.
격리 source의 network=none/auth=none Docker에서 실행한 결과와 실제 CORE 수신은 업무 evals/인계 기록으로 연결한다.
