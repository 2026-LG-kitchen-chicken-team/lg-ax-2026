# 2026-10-06 프로젝트 문서 탐색 이관

사용자는 이전 개인 기록의 보존 이관처럼 저장소 문서 경로·정본·이력을 분석하고 비효율을 개선하도록 직접 승인했다. 이번 단계는 **큰 공통 입구5개를 짧은 현재 탐색 입구와 불변 원문으로 나눈 문서 변경**이다. 첫3원문 단계 뒤 PM 후속 지시로 루트 README·현재배정을 같은 방식으로 추가했다. 모델 호출·제품 기능·서비스 배포·상태/권한·자동화 ON·팀원 성과·노션 동기화는 수행하지 않는다.

- 고정 원 source commit: `0078975ef4579008eb7c5921541122a8f569ce3a`
- 원 파일5개: `docs/인수인계.md`, `docs/진행체크리스트.md`, `harness/README.md`, 루트 `README.md`, `docs/pm/현재배정.md`
- 원문 `161,753`바이트는 `originals/{원경로}`에 전체를 그대로 보존한다. 상대 링크도 원문 일부이므로 변환하지 않는다.
- 기존 경로는 현재 업무의 짧은 입구와 원 heading/순서를 유지하는 호환 목차다. 원 내용은 각 과거 heading의 ‘당시 원문’으로 읽는다. 원문의 ‘현재·최신·ON’은 당시 기록이며 현재 지시가 아니다.
- 원문 상대 링크는 [원래 위치 기준 탐색](links.md)에서 조회한다. physical archive가 아닌 manifest의 `original_base_directory`를 기준으로 해석하고, 필요하면 고정 commit의 원 경로를 확인한다.
- [manifest](manifest.json)는 원 경로·Git blob·SHA256·body bytes·원 heading/line/anchor·해당 새 path·링크 해석·보호 파일의 이관 당시 SHA를 포함한다. 원본 재현은 archive 파일 바이트 자체와 원 Git blob의 일치다.
- [총괄 감사](audit.md)에는 최소 변경 선정 이유·전체 탐색 경계·다음 단계와 한계를 기록했다. [문서 정본/작성 위치](../../../README.md)가 향후 탐색 기준이다.

## 정적 검증

```powershell
python scripts/check_document_navigation.py --check-protected --check-source-git
python scripts/check_document_navigation_counterexamples.py
```

저장소 루트에서 수행하는 stdlib 정적 검사다. 애플리케이션 import·테스트·모델·서비스·네트워크·파일 변경은 없다. 원바이트/SHA·전체 heading/중복 순서·호환 backlink·원 위치 기반 링크·현재 입구 링크·보호 파일의 이관 당시 바이트를 확인한다. `--check-source-git`는 로컬 Git의 고정 source blob을 읽어 원문 전체 바이트와 직접 대조하며 네트워크를 호출하지 않는다.

두 번째 반례 검사는 필요한 정적 문서107개만 별도 `private/runtime` 임시 fixture에 복사한다. fixture 정상 통과→archive바이트/원heading/역링크/이전검사증빙 훼손 거절→원 fixture 복구 통과를 확인하고, 절대 경로 경계를 검사한 뒤 임시 fixture만 정리한다. 추적 문서·제품·원 archive는 변경하지 않는다. Windows subprocess의 출력 인코딩은 `-X utf8`로 고정한다. 실제 결과는 [현재 정적 검사 증빙](validation.json)에 있고, [첫3원문 검사의 원바이트 증빙](validation-3sources.json)도 그대로 보존·검증한다.

이관 이후 작성자의 정상 기록/README 갱신을 금지하지 않는다. 그 뒤 일상적인 검사에는 `--check-protected`를 빼고 `python scripts/check_document_navigation.py`를 사용한다. 보호 SHA는 이관시 무변경 감사 기준이며 현재 진행 수치를 잠그는 운영 정책이 아니다. 전체 개인 기록의 기존 검사는 별도 `scripts/migrate_member_logs.py --verify`를 승인된 환경에서 수행한다.

## 향후 보완·보존 범위

- 개인기록330개 Markdown, 기존 원 snapshot8개/분할231개/자동 세션28개와 owner 갱신 구역, 공식 원문, Skill 경로를 변경하지 않았다. 전체 자료/실행 README·하네스 JSON/원 실행 hash도 이동하지 않았다.
- 루트 README·현재배정의 원0078975 Git blob과 현재 root/분리 worktree의 바이트가 일치함을 확인하고 4·5번째 source로 추가했다. 두 파일은 기존 보호374목록에 없었으며, 이제 원본문은 불변 source·기존 경로는 현재 입구로 구분한다. 현재배정의 새 업무 지시/완료값은 추가하지 않고 PM의 후속 문서를 연결할 수 있게 둔다.
- 진행 중 PM 개인010, 운영 큐와 AGENTS/CLAUDE는 변경하지 않는다. 최신 운영값을 하드코딩하지 않고 현재 지시·직접 조회·원 근거로 안내한다. PM이 공통 지침 두 개에 이 입구를 동일하게 연결하고 별도 변경 범위를 검토한다.
- 원 markdown의 단순 링크/heading 분석은 코드 fence·reference-style·backtick 경로/JSON 정책 전체를 대신하지 않는다. 최종 인수 때 diff 허용 범위와 고정 path/hash 의존을 함께 대조한다.
