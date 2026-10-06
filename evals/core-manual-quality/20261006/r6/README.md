# R6 실제 모델 검증 — 연결 중단 원 근거

2026-10-06 19:39~19:42 KST. 사용자 직접 지시 “실모델 품질 검증도 하자 왜안하는지 모르겠네”로 현재 CORE의 효과를 검증했다. 실행 소스는 PR182의 당시 head `8bf6ddf8624938cb70eab3c67e7f6ba95685e8c0`이다. 이후 PM이 PR branch에 main을 반영 중이므로 해당 branch를 중복 편집하지 않고 별도 근거 branch에서 기록했다. 최신 remote head의 성공으로 이 과거 head 실행을 대신하지 않는다.

고정 Qwen3 8B digest·temperature0/seed42/context16384/output8192/thinkfalse와 R2 원 입력3개를 유지했다. Docker는 network none/UID65534/readonly source와 root/drop ALL/no-new-privileges/인증 mount0였다. 새 모델 설치·공통 어댑터 편집·Worker ON은 없다.

정상 사례의 Need 첫 호출은 실제 HTTP200/done 응답을 받았다. 9개 Need의 `unresolved`에 누락 사실 대신 Need ID9개가 있으며 질문은 비어 있다. 코어는 `HOLD_WITHOUT_QUESTIONS`로 거절했고 revision1 요청에는 실제 unresolved/hold_reasons/questions를 담은 R4 수정 피드백이 전달됐다. 원 선언을 자동 수정하지 않았다. R5 누락 리뷰 ID 피드백은 이 첫 선언에서 누락 complaint가 없어 작동 효과를 판정할 수 없다.

두 번째 실제 POST는 `RemoteDisconnected`로 응답이 유실됐다. 실행/토큰 사용 여부는 미확인이다. 자동 재전송0, 컨테이너 제거와 접속 복구 뒤 본인 예약 HTTP200 해제를 확인했다. 완주한 Agent 결과는0개이고 정상accept·조건변경accept·자료부족의 적절한hold·같은 완료run WEB/MCP·독립 품질/PM Done은 미완료다. 조건변경/설명서 누락 사례는 시작하지 않았다.

새 시도2회·수신1회·관측2349입력+2158출력=4507토큰. 원R4 9회/39726토큰을 보존해 누적시도11회/상한24회·관측44233토큰+유실호출 미확인 사용량으로 기록한다. 미확인 사용량을0으로 초기화하지 않는다.

[manifest](manifest.json)는 원 입력SHA·소스SHA·Docker 경계·시도 ledger와 파일SHA를 연결한다. [첫 요청](01-needs.ollama-request.json), [실제 응답 원바이트](01-needs.ollama-response.json), [응답이 유실된 수정 요청](02-needs-revision.ollama-request.json)은 인증정보 없는 원 제품 HTTP body다. 해당 응답 파일은 만들지 않았다.

다음 행동: PM이 유실 요청의 prompt SHA `1928d852bce89c625d581f3000a28301f6401f7a7073a85e22ad8e3c688f7e2b`와 gateway metadata를 대조해 실행·사용량·중계 상태를 확인한다. 원 실패/비용을 보존하고 고정 유한 후속 검증에서 아직 시작하지 않은 사례와 정상 사례의 처리 방법을 확정한 뒤 이어간다. 문서 원문 대조는 작성자의 관찰이며 기존 여섯 사례 독립 AI 평가를 재사용/재채점하지 않았다.

문서/원 데이터 검사: Windows 파일 쓰기의 CRLF 변환 때문에 최초 개인 README 이관 검증이 실패했다. 기존 원바이트를 소유자 갱신 구역 밖에 그대로 복원한 뒤 zero-auth Docker 규칙·기록 이관·계약/하네스·3원 입력SHA·Ruff·MCP stdio fixture5호출 검사가 통과했다. [원 실패](checks/original-readme-crlf-failure.txt)와 [수정 후 로그](checks/verified-static.txt)를 모두 보존한다. 이 정적/fixture 검사는 실모델 완주나 같은 완료run 웹/MCP 품질 검증이 아니다.
