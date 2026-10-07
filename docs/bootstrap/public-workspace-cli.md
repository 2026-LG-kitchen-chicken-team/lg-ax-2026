# 공개 원문 작업실의 고정 자료 실행 진입점

`lgax_api.workspace_server`는 운영자가 고른 공개 `document_dataset`의 경로와 원파일 SHA256을 함께 받는다. HTTP·MCP 요청에는 경로·해시·새 출처 업로드 필드를 추가하지 않는다. 기존 공개 `lgax_api.server` 및 `/api/bootstrap`은 합성 자료 전용이다.

승인된 격리 운영 프로필에서만 아래 인자를 구성한다. DB는 원 합성·날짜 시연 DB와 별도로 두고, 포트는 실제 점유 확인과 고정 launcher 검수 후 선택한다. 아래의 해시·포트 자리표시는 실제 배포 설정이 아니다.

```text
python -m lgax_api.workspace_server
  --db /state/workspace-public.sqlite
  --credentials /auth/server-credentials.json
  --document-dataset /app/<reviewed-public-snapshot>.json
  --document-dataset-sha256 <exact-lowercase-64-character-file-sha256>
  --host 127.0.0.1 --port <approved-unused-loopback-port>
```

경로와 해시 중 하나만 지정하거나 `--dataset`, `--trend-metadata`, `--trend-metadata-sha256`, `--allow-candidate-trend-metadata`와 혼용하면 DB·서버를 만들기 전에 거절한다. 해시는 JSON 해석 전에 원파일 바이트와 대조한다. 같은 해시의 잘못된 JSON·중복 필드·비공개 자료·모델/문서/기능/근거 연결 오류도 정적 오류 메시지로 거절한다. 원파일 SHA는 작업실의 canonical dataset SHA와 구분한다.

공개 자료는 기존 `WorkspaceDocumentStore`로 읽는다. 내부 문서 버전 metadata가 포함된 canonical snapshot을 작업실 DB와 인증된 `/api/workspace/bootstrap`이 같은 방식으로 해시한다. 공개 bootstrap wire의 manifest는 이 SHA와 등록 모델·실행용 후기 수·한계 경고를 표시하며 `analysis_implemented=false`를 유지한다. 원 PDF 재등록·현재 원본 파일의 존재를 확인하는 진입점은 아니므로 이 해시 검증을 OCR·실시간 원본 대조·의미 품질의 증거로 쓰지 않는다.

기본값은 판단 OFF다. 인증된 프로젝트·요청 기록은 저장하되 run은 기존 `not_implemented`, output=null이며 보류 판단으로 바꾸지 않는다. `--enable-planning`을 명시한 경우에만 기존 서버 모델 설정을 사용하는 runner를 주입한다. 이 CLI 추가는 모델 선택·자동화 ON·모델 호출·비용 한도 변경이나 배포를 승인하지 않는다. 후기 근거가 없는 입력을 Agent가 검사한 경우의 `held`와 기본 저장 모드는 구분한다.

R5 실행 자료는 검증된 매뉴얼 3모델의 원문·기능과 구매 SKU가 확인된 실행용 후기만 사용한다. 현재 실행용 후기0이라는 사실을 보존한다. 새15모델의 PDP registry나 페이지 단위 연구 후기 표본을 manual/review Evidence로 자동 변환하지 않는다. 날짜가 구매일인 값을 게시일로 바꾸거나 페이지 표본을 특정 SKU 구매자의 수요로 표시하지 않는다.

최소 인수 순서는 다음과 같다.

1. 같은 고정 release의 source/의존/guard, 공개 snapshot 원파일 SHA, canonical SHA, 별도 DB·제품 전용 auth·빈 포트를 확인한다. 기존 운영 서비스·DB·원 실패·auth·모델/controller/자동화 OFF를 보존한다.
2. 무인증401, viewer 읽기와 쓰기403, 다른 소유자403, no-store, 잘못된 Origin403, private 진단 누출 차단을 확인한다. bootstrap→project→run의 자료·문서 버전과 SHA가 같아야 한다.
3. 원자료/조건/parent ID가 저장·재조회·DB 재열기에서 유지되고, 달라진 dataset은 과거 기록 읽기만 허용하며 추가 run은409로 거절하는지 확인한다. 실패·보류 run에 선택 가능한 후보를 만들지 않는다.
4. finite browser relay는 새 release의 소유 PID·source/DB/웹 dist binding을 먼저 검증하고 인증된 literal GET `/api/workspace/bootstrap`만 추가한다. 원 helper는 보존한다. 기존 읽기와 새 프로젝트/run POST는 별도의 고정 입력 body·횟수·예약/수신 검수 없이 확대하지 않는다. JSON/Markdown export는 동일한 실제 run ID·status·input/source 버전·원 근거와 대조한다.

`tests/test_workspace_public_runtime.py`는 zero-auth/network-none Docker에서 원파일 hash·옵션 충돌·공개 canonical 경계·권한·DB 저장을 검증한다. 후기0 보류 검사는 명시적인 fixture client를 쓰며 모델 생성0이다. 테스트 통과를 R5 실제 모델 품질·실제 운영 배포·사용자 효과·계정 내 MCP 발견·OS 재부팅/자동 시작·최종 제출 완료로 확대하지 않는다. 기존 `lgax_core.document_workspace` CLI는 당시 진입점으로 보존한다.
