# 신진하 작업기록 — 운영 자료·집계·최종 출력 대조

- 기록ID: 신진하-20261007-OPERATION-AUDIT-01a10f51.
- 사용자 지시: 최신 PR190·194·196·200 및 승인 운영 인계 확인, 자료·집계·세 제품 출력 대조, 미수신 보고, 별도 작업 공간·새 폴더, 기존 코드/자료/개인 README 보존, 모델/OCR 새 호출 없이 PR 게시.
- 작업 공간: `codex/data-operation-audit-20261007T002145-01a10f51`, main9cd2d56.
- 착수 메일: 관련 LGAX GitHub 알림12개 검색·관련3개 원문 read-only 소비. 발송/읽음·라벨 조작0.
- GitHub: 정확 head·리뷰/댓글·CI·운영Issue28의 최신페이지·Project 항목 조회. PR194/186은 병합,190/196/200/198은 당시 OPEN. PM이 지시한 endpoint/viewer/snapshot 인계는 수신하지 못함.
- 현재 자신/CORE/WEB의 재개 요약과 고정 인계 확인. 개인 README는 사용자 지시에 따라 수정하지 않고 본 폴더에 기록.
- 수행: 고정7파일/177기록/원PDF3 해시, 보존15집계/108연결, WEB API→MCP→화면/내보내기, 과거3제품+식기세척기 반복 결과의 입력·출력·재현·질문/위반을 대조.
- 정정: 승인 main 설명서 팩의 리뷰0과 별도 보존 LG페이지 발췌3건을 구분. 원 발췌를 새 수집으로 세지 않음.
- 자체 도구 오류와 수정: PowerShell Git -c 인자 형식을 수정했고 fetch 전 실패라 원격/작업트리 변경없음. 수집기에서 contract_sha256의 문자열/경로목록 형태를 구분. 검수기에서 manifest가 있는 DemoDataset과 dataset_version가 있는 staging artifact 및 source id/evidence_id 형태를 구분. 원 자료 변경 없이 검수 도구만 수정하고 최종 결과로 대조 완료.
- 실제 수행 명령: `python read_sources.py`, `python collect_inputs.py`, `python collect_more.py`, `python build_audit.py`, `python write_reports.py`. 모두 이번 작업자가 작성한 호스트 stdlib 조회/분석 도구이며 저장소 스크립트를 호스트에서 실행하지 않음.
- 정적 대조: 3003항목 불일치0. 3148 tracked기존파일 바이트 변경0. 품질 PASS/운영 연결/독립 평가/부모Done 선언은 아님.
- R06: 과거2제품 최종 출력 신원 연결 확인, 전자레인지 출력없음. R07: 원 재현 수신증4건·runner/입력/출력 일치; 새 재현/모델 실행0. R08: 원 failed/held/failed와 valid=false/출력없음을 보존.
- 미수신: 승인 실제 운영 자료 응답, 운영팩/공통허용범위, 실제집계 응답, 최신PR190코드의 세 제품 고정 결과. 필요 필드는 operation-handoff-needed.json.
- 다음 담당: PM이 승인 운영snapshot/본인viewer/공통허용범위·새고정3제품결과를 인계하면 DATA가 해당 범위의 버전/ID/원문해시·집계를 대조. WEB 화면은 담당자의 동일버전 수신증을 소비. PM의 선택/주입/평가자 지정 업무를 DATA 완료로 쓰지 않음.
- 새 모델/OCR/운영HTTP/브라우저/저장소 suite 실행0. 설정/서비스/예약/기존 비용 및 실패 이력 조작0.
- PR 게시: 이 결과 폴더만 포함해 사용자 승인 범위로 게시. 게시 URL/HEAD는 PR 수신증에 기록하며 병합하지 않음.
