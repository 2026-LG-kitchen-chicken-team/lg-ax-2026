<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/신진하.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 14617..16149 · 원문 행: 64..70

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
### 신진하-E013-ci-recovery — 게시 후 옛 입력 버전 회귀 실패 복구

- 기록007-ci-recovery / 2026-10-05 / 신진하. 직접 브라우저에서 PR74 author ginaginaring/Open/non-draft/main 대상37파일과 head3cbcc64, Issue12 자기보고5983852638을 확인했다. 게시 승인 자체를 성공으로 바꾸지 않고 실제 URL을 연결했다.
- 실패: GitHub Actions run37230410141/job111518700660의485회귀 중1실패. `tests/test_data001_connections.py:67`은 canonical `.2` 자료에 stage123 `.1` 입력의 원문을 기대했다. 데이터/입력의 과거 버전은 수정하지 않는다. 해당 테스트 입력 경로를 stage45 `.2`로 변경해 기존 scope 및 DATASET_MISMATCH 검사를 유지했다. 공통 runtime·Schema/PM 코드 변경 없음.
- 검사/버전: `stage45/ci-recovery.json`은 초기 원격 실패를, `connection_regression.json`과 `full_regression_after_ci_fix.json`은3cbcc64+명시한 테스트 변경 SHA에서 실행한 명령·결과를 보존한다. 기존76HTTP/17검사의 canonical source/data SHA는 그대로다. 전체 raw 회귀 로그는 tmp에만 보관하며 가상 예시 원문을 PR로 옮기지 않는다.
- 복구 게시: 사용자 승인한 동일 PR74에 변경과 실제 결과를 push하고 PR 설명/같은 새 full commit의 개인 두 문서·인증 Issue 보고를 갱신한다. 최종 CI·ACK는 실행 후 실제 링크로 확인한다. 실제 AI0·고객리뷰0·비공개 평가 ZIP 미전송·#12/PM 완료 미확인을 유지한다.


<!-- member-log:body:end -->
