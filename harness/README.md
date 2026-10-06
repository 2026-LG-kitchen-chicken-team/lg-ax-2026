# LG AX 개발 하네스 입구

현재 개발은 [phase2](phase2/README.md)를 사용한다. [PM 현재 배정](../docs/pm/현재배정.md), [문서 정본·작성 위치](../docs/README.md), [공통 실행 안내](../docs/bootstrap/README.md)를 함께 읽는다.

```powershell
uv run python scripts/phase2.py status
uv run python scripts/phase2.py next --member 정이량
uv run python scripts/phase2.py packet <작업ID>
uv run python scripts/phase2.py validate
```

담당자 이름과 작업 ID는 실제 배정에 맞춘다. 명령은 저장소 루트에서 승인된 실행 환경으로 수행한다. 하네스는 상태·작업 패킷·검사 도구이며 자체 AI 실행기가 아니다. 자연어 요청을 받은 현재 AI가 실제 작업·검증·기록을 수행한다. 검사 통과·개별 검증·PM 검수·실제 병합·통합 확인·완료를 구분한다. 자동화는 새 사용자 ON 지시 전 OFF다.

**현재 기준 파일**

- [phase2 상태·작업](phase2/README.md), [신청서 31개 요구](phase2/requirements.json), [GitHub 연결](phase2/github.json)을 따른다. 변동하는 수치·현재 실행 버전은 직접 조회와 원 근거로 확인한다.
- [project.json](project.json)은 공모전 전체 정보·역사 상태, [AtoZ 사용법](AtoZ_사용법.md)·[atoz.json](atoz.json)·[atoz_state.json](atoz_state.json)과 `runs/`의 선정 기록은 탐색·접수 당시 근거다. 이전 AtoZ `finish`를 현재 개발 완료로 사용하지 않는다.
- 공식 자료·계약·실행 증거의 원 경로와 해시를 보존한다. 미완료 모델 품질·외부 AI 연결·평가·제출을 문서 정리로 완료하지 않는다.

**과거 하네스 안내**

이전 README 전체는 [원바이트 원문](../docs/history/project/20261006/originals/harness/README.md)에 보존했다. 아래 원 제목은 기존 anchor를 유지하는 탐색 목차이며 [이관 설명](../docs/history/project/20261006/README.md)과 [원래 위치 기준 링크 안내](../docs/history/project/20261006/links.md)를 따른다. 당시의 ‘현재 AtoZ·다음 설계’ 설명은 현재 개발 모드가 아니다.

<!-- document-navigation:legacy-anchors:start -->

# LG AX AtoZ 하네스

[당시 원문 — 원 경로 harness/README.md, 1행](../docs/history/project/20261006/originals/harness/README.md#lg-ax-atoz-하네스)

<!-- document-navigation:legacy-anchors:end -->
