# PM의 팀원 PR 산출물 인수

2026-10-04. 담당자가 제출한 원본 PR·개별 실행 근거를 PM이 인수하는 절차다. PM이 담당자의 `owner_finish`를 대신 실행하거나 팀원 수행 기록을 새로 만들지 않는다.

## 인수와 검수·완료의 구분

`scripts/receive_submission.py`는 실제 GitHub 인증 계정이 PM `jeongiryang`인지 확인하고, 작업 담당 계정이 작성한 PR의 고정 head에서 원본 근거를 확인한다. 통과하면 별도 PM 인수 수신증과 작업의 `pm_intake`를 연결하고 `individual_verified`까지만 기록한다. 담당자의 원본 근거·과거 owner_finish 이력은 보존한다. 개별 실행 내용은 담당자가 보고한 것이며 이 도구가 검사 자체를 다시 실행하지 않는다.

PM 승인·실제 병합·병합 commit의 통합 실행·최종 Done·요구사항 verified는 기존 phase2의 별도 절차로 판정한다. 로컬 상태를 갱신한 사실만으로 GitHub Project나 PM 승인 스냅샷이 변경되지 않는다. 공유·공식 동기화는 실제 검수와 main의 검증 뒤 PM이 수행한다.

## 실제 확인하는 항목

- GitHub `/user`의 실제 인증 PM 계정, 작업별 등록 이름·계정, 실제 PR author를 대조한다. 로컬 `--actor`나 commit 작성자 이름을 로그인 인증으로 사용하지 않는다.
- PR은 `jeongiryang/lg-ax-2026`의 같은 저장소 head/base이며 main 대상의 열린 비초안 PR 또는 실제 merged PR이어야 한다. 닫혔지만 병합되지 않은 PR은 받지 않는다. stacked PR은 선행 작업을 검수한 뒤 실제 base를 main으로 조정하고 다시 조회한다.
- 원본 JSON은 실제 PR head의 tracked regular blob과 로컬 근거의 바이트·SHA256이 같아야 한다. JSON의 task ID·owner·허용 execution_kind·passing checks·코드/자료/출력 해시와 한계를 검사한다. 원본 body·이메일·인증 토큰은 PM 수신증에 넣지 않는다.
- tested commit은 전체 SHA이며 PR head의 조상이어야 한다. 검사 이후 근거만 추가한 commit은 허용하되 검사한 코드/자료 바이트가 PR head에서도 같아야 한다. 출력 파일도 PR head의 고정 blob·로컬 파일·기록 해시와 일치해야 한다. Git replacement를 사용하지 않는다.
- 선행 작업이 모두 Done이고 필요한 확장이 실제 채택돼야 한다. 의존 대기 중 산출물 검토는 가능하나 이 명령은 수신증·작업 상태를 쓰지 않고 거절한다. 선행 완료 후 같은 원본 버전을 다시 확인한다.
- PM 승인 이후/병합 이후/최종 완료 작업을 인수로 다시 열지 않는다. 이미 기록된 담당 근거가 다르면 덮어쓰지 않고 명시적인 수정 제출을 요청한다. 적용 직전 task/dependency 파일과 PR head를 재조회해 중간 변경을 거절한다.

GitHub 계정/PR 출처 확인은 해당 계정이 제출했다는 증거다. 테스트의 진실성·개발자의 실제 신원·사용성/성능·요구 충족을 독립 인증하지 않으므로 PM은 원 출력과 변경 내용을 검수하고 필요한 실행을 직접 확인한다.

## 실행

필요한 원본 PR commit과 근거 파일은 먼저 읽기 가능한 로컬 이력에 확보한다. 이 도구는 자동 fetch·checkout·GitHub 변경을 하지 않는다. 새 수신증 경로는 저장소 안의 공개 가능한 JSON이어야 하며 기존 파일을 덮어쓰지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/receive_submission.py P2-WEB-001 --pr 36 --evidence evals/web/20261004/p2-web-001/individual-evidence.json --receipt evals/pm-web-integration/web001-intake.json
```

기본은 실제 계정/PR과 고정 근거를 확인하는 미리보기다. 파일·작업 상태·원격 상태를 변경하지 않는다. PM이 검토한 같은 명령에 `--apply`를 추가하면 로컬 수신증과 작업 JSON만 기록한다. 수신증에는 PM·제출 계정·PR URL/head·확인일·원본 근거 경로/해시·tested commit·완료된 선행 작업·한계를 남긴다.

WEB001은 담당 개별 근거가 이미 등록되어 있으므로 기존 `phase2.py review`로도 이어갈 수 있다. WEB002의 최신 제출은 `evals/web/20261004/p2-web-002-r2/individual-evidence.json`이며, WEB001의 실제 완료와 PR37의 main 대상 확인이 선행이다. 원본 첫 실행과 r2를 섞지 않는다. 이 문서 작성은 두 작업의 PM 승인·병합·전체 완료 보고가 아니다.

```powershell
uv run --no-sync python -X utf8 -m unittest tests.test_receive_submission -v
uv run --no-sync python -X utf8 scripts/phase2.py validate
```

단위 검사는 임시 Git 저장소와 모의 GitHub 응답을 사용한다. 실제 팀원 실행·실제 PM 접수 성공을 증명하지 않는다. 실제 인수·검수·병합·통합 기록은 정이량의 작업기록/근거에 별도 연결한다. `phase2.py validate`는 수신증 존재·SHA·작업/PM/담당자/PR·고정 원본 근거·tested commit·의존을 오프라인 검사한다. 실시간 GitHub 인증을 재실행하거나 담당자의 테스트 수행·의미 품질을 독립 입증하지 않는다.
