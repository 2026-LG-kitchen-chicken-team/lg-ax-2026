# PM UI2 실제 영어 제목 후속 — CORE

PM PR284/c20df447 원 readback을 원바이트로 인수하고 한국어 요청의 사용자용 생성 언어 지침을 보완했다. [원 readback](live-revision-readback.json) · [수신과 한계](source-intake.json).

- 제목·조건·lineage·bundle pin·2콜 메타데이터를 인수했다. 전체 brief/native raw/usage가 수신됐다고 주장하지 않는다.
- public_planning/public_repair 공유 지침으로 한국어 요청의 제목·설명·장면을 한국어로 생성하고 원문 인용·제품명·ID·facts를 보존한다. 기존 원 응답을 번역하거나 덮지 않는다.
- [최초 검사](first-checks.json): 공개 기획/수정42·Ruff·규칙 byte·문서 탐색 PASS. 목차 저장에서 CRLF로 바뀐 원문 보존 실패를 [원 로그](first-member-log-preservation.log)에 남겼다. Git HEAD/시작 수신증 원 바이트를 대조해 담당자 추가 구간만 byte 삽입하도록 복구했다. 제품 코드와 검사 기준은 그대로다.
- 새 제품 모델 요청0/기존6 독립 재채점0. 실제 Qwen 효과·PM 채택/인수·전체 Done은 아직 미검증이다.

최종 [수신증](final-checks.json): 공개 기획/수정42·Ruff·규칙 byte·문서 탐색·개인 이관 보존 PASS. 원231구간/818663바이트/28세션·36Git 원본 pin 보존. [문서 재검사](final-doc-checks.json)만 다시 실행했고 제품 검사는 변경 코드가 동일해 재사용했다.
