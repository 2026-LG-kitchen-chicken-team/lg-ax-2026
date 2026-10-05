# 24개 개발 이슈의 실제 Project 상태 중계

`development-project-map-20261005.json`은 원 등록 수신증
`development-queue-issues-20261005.json`의 Issue/담당/부모/Project item 24개를
그대로 참조하는 별도 파생본이다. 원 수신증·원 23단위 계획·개발 registry·대장은
변경하지 않는다. 각 capability 전체 fingerprint를 추가하여 허용 경로·검사·담당의
오래된 매핑을 거부한다. 배포 plan의 source metadata만 재결속한 경우 cap 정의가
동일하면 fingerprint도 동일하다.

## 보호 배포 설정

PM은 검토된 파생본의 정확한 Git blob을 저장소 밖 보호 디렉터리에 복사하고
실제 배포 파일의 해시를 검사한 뒤 host config에만 다음 설정을 추가한다.

```json
{
  "development_issue_registry": {
    "path": "C:/LGAX/pm/config/development-project-map.json",
    "sha256": "f4bd9ac877b837e6a7cd1b23637299f227c467e9277d4c2d35f5184577f4ec23"
  }
}
```

위 경로는 배포 예시다. 실제 PM 보호 경로·source commit·map hash와 사전검사
결과는 운영 인수 기록에 남긴다. 파일은 일반 파일이어야 하며 저장소 내부 경로·
링크·128 KiB 초과·잘못된 해시·다른 Project/필드/담당/부모/편집 범위를 거부한다.
기존 `development_project_mirror` 캐시는 실제 적용 증거다. map hash를 바꾸면
PM이 기존 캐시를 보존하여 별도 버전으로 이관한 후 새 빈 캐시를 만들어야 한다.
기존 작업·회수·예산·부모 완료 대장은 초기화하지 않는다.

## 실제 상태와 표시

| 실제 근거 | 새 child Project Status | 다음 행동 |
|---|---|---|
| 미배정/선행·원 부모 PR·Worker 준비 대기 | Todo | 대기 또는 고정 Ready 배정 대기 |
| controller pending | Todo | 배정됨·Worker claim 대기 |
| running | In Progress | 구현·검사·자기 검수 |
| review_requested | In Progress | PR·CI·통합 확인 대기 |
| blocked/failed/orphaned/stopping | In Progress | 원 실패/lease/중단 확인, 자동 재시도 없음 |
| 원 PR의 revision_requested | In Progress | 원 PR 보존·새 bounded 작업/검수 대기 |
| 실제 accepted job + reconciled unit + 검증된 accepted ledger | Done | 개발 단위 인수 완료, 부모 품질·독립 평가·제출 별도 |

이 중계는 현재 controller job와 PM host의 capability 연계를 사용한다. 기존
수동 PR/전임 작업이 존재하더라도 실제 해당 단위 인수 증거 없이 Done을 만들지
않는다. 개발 단위 Done은 신청서 요구사항 verified나 원 부모 작업 Done이 아니다.

쓰기 대상은 기존 org Project1의 **Status·다음 행동·실행 증빙·최근 배정** 네 필드뿐이다.
정식 진행상태·팀원 인증보고·배정자·우선순위·요구사항·기한·설정·Issue close/PR은
이 중계가 변경하지 않는다. 실제 PM 계정·controller operator·ON을 확인하고,
현재 Issue ID/담당/marker/부모 sub-issue와 Project item/필드/옵션을 읽은 뒤 갱신한다.
Worker의 자유 텍스트·비밀정보·오류 전문을 게시하지 않고 고정 상태 설명과
실제 job/base/head/PR 링크만 게시한다.

`collect=False`와 OFF 조회는 외부 쓰기·인증·모델 호출을 하지 않는다. 변경 없는
상태와 heartbeat는 추가 API 갱신·AI 호출을 만들지 않는다. GraphQL 오류/부분 ACK/
불명 결과는 적용 캐시에 넣지 않는다. 다음 collecting tick에서 현재 필드를 읽고
부족한 값만 멱등 갱신한다. ACK 뒤 실제 값 재조회까지 성공한 항목만 캐시에 남긴다.
Project/필드가 조회 상한을 넘거나 관계·권한이 바뀌면 성공을 추정하지 않는다.

검사: `uv run --no-sync python -m unittest tests.test_automation_development_project -v`.
로컬 Mock 검사는 실제 보호 배포·실제 Project 쓰기 완료를 대신하지 않는다.
