# DATA16/148 고정 development 인계 자기 검수

[자료·사용법](../../../data/research/r8-public-research-20261007/trend-annotations/01a114f6/README.md), [생성기](../../../data/research/r8-public-research-20261007/trend-annotations/01a114f6/build_development_handoff.py).

## 실제 실행

- 입력: PR254 head94b560de72f91795cfd50aada9e17d6773383ae1과 PM PR245 병합ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f의 고정 Git blob. [pins](../../../data/research/r8-public-research-20261007/trend-annotations/01a114f6/source-pins.json).
- image `sha256:d2b9d2d0d1da29f3226a8293340d63f58877a03b7189d3982123ff6995e8e01c`, user10001:10001, `network none`, root/source/code read-only, `cap-drop ALL`, `no-new-privileges`, tmpfs64MiB. 인증/원 worktree/.git/private mount0.
- 호스트는 Git blob 읽기·격리용 복사·Git/GH 게시만 수행했다. repo 생성기/검수/집계 코드는 위 Docker에서만 실행했다.
- [생성 검수](verification.json): 개발141, 정확 인용292, 반례12쌍, metadata 변조6개 거절, 기존 집계기 빈 날짜36query PASS.
- [고정 출력 재검수](fixed-output-verification.json): pin65와141원 Source의 byte/canonical equality·본문/URL/selector/hold·분할238·비개발제외97·292인용 범위·membership 재계산 및 기존 집계기36replay PASS. 각 granularity의 미상 날짜 제외 합계141, 시간 분모0·비율null.
- 이 검사는 작성자의 source binding/계산 자기 검수다. 독립 의미 채점/Gold/PM 승인/운영 웹 소비/부모 Done이 아니다.

## 게시·수신 확인

- 완료 단위B를e52cd06dc790328dd29f1e4c0d2ba3498fe7c63b로추가했다. [원격 게시 검증](remote-publication-e52cd06.json):31개변경file Git blob이원격tree와일치, 표sidecar/annotation/source/date sidecar4파일은GitHub실제byte를읽어고정SHA와대조PASS.
- e52cd06의필수CI Python/WEB4SUCCESS를조회했다. PMreview요청을남겼으며검토승인/병합은아니다.
- [CORE/WEB 실제 수신증](recipient-receipts.json):CORE의d58c23b표sidecar수신/수동소비사전검토, WEB의e52cd06후기sidecar/source수신·무결성확인회신을인증된GH로읽었다. WEB로컬검수코드/receipt파일은공개미수신이므로새독립자동실행증거로세지않는다.
- source/draft/artifact파일SHA는그대로이고, 이번후속은문서/수신기록만추가한다. 원summary의승인필드는생성시점snapshot이며현재실제읽기수신상태는별도수신증을따른다. 자동graph/승인adapter·운영화면/PM의미승인/부모Done은미완료다.

## 원 실패와 수정

1. [build-1.log](build-1.log), exit1: 원v2에는 `original_text_sha256` 등이 없었다. 원 필드를 채우지 않고 record/bundle의 선언과 부재를 분리했다. source record의 후기ID/HTML SHA/문서버전 부재도 null로 보존했다.
2. [build-2.log](build-2.log), exit1:807886의 짧은 반복 인용 anchor가 두 위치에 걸렸다. 원 전체 반복 문장으로 인용을 바꿔 유일한 범위를 고정했다.
3. [build-3.log](build-3.log), exit0: 최초 source binding PASS. 이후 의미 자기검토로850388 성능 미체감을 확정 부정/혼합으로 세지 않고 긍정+미확인,824618/860946 일반 성능을 세척 상세 주제로 추정하지 않도록 seed를 보완했다.
4. [build-4.log](build-4.log), exit0: 최종292인용/141draft/12반례/36query PASS.
5. [verify-1.log](verify-1.log), exit0: 최종 고정 출력36replay와 membership·파일SHA 대조 PASS.

실패 로그를 보존하고 최종 통과로 이전 실패를 지우지 않았다. 모델/OCR·새 수집·서비스/DB/restart0이며 최초 재생부터 네트워크를 차단했다.

## 재현

해당 두 고정 commit의 `source-pins.json` 경로를 인증 없는 source-copy에 준비하고 이 생성기/seed·검수기를 별도 code-copy로 넣는다. source/output 위치를 사용자가 선택한 경로로 맞춘다. 전체 repo나 인증/운영 폴더를 mount하지 않는다.

```sh
python /code/build_development_handoff.py --source /source --output /out --seeds /code/annotation-seeds.draft.json
python /code/verify_development_handoff.py --source /source --artifacts /artifacts --report /out/fixed-output-verification.json
```

두 실행은 위 Docker 경계 안에서 수행한다. `/source/data/`와 `/source/pm/` 아래에 pin의 상대 경로를 보존하고 `/source/source-pins.json`을 둔다. `/artifacts`는 첫 실행의 고정 output을 읽기 전용으로 제공한다. 새 날짜/토픽을 채우거나 승인되지 않은 원문 투영을 운영 WorkspaceStore에 등록하지 않는다.
