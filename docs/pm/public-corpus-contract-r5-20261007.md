# R5 공개 자료 웹 연결의 계약 검토

PM 정이량은 사용자 실제 후기·DB/Excel·웹 연결 지시에 따라 기존 합성 자료 경계를 유지하면서 인증된 작업실의 공개 자료 조회를 추가한다. 기존 Manifest·DemoDataset·BootstrapResponse와 공개 API/MCP의 synthetic-only 정책은 바꾸지 않는다.

공통 JSON Schema에는 PublicManifest/PublicBootstrapResponse와 WorkspaceBootstrapResponse(oneOf 기존 합성/새 공개)를 추가한다. 공개 응답은 Product/Review/Evidence의 source_kind=public을 검사하며 기존 Feature/원문·ID·버전 계약을 그대로 쓴다. 실제 후기의 구매SKU 미확인으로 실행용 후기가0일 수 있으므로 공개 manifest review_count0을 허용한다. 합성 manifest는 기존 최소1과 analysis_implemented=false를 유지한다.

소비자는 인증된 `GET /api/workspace/bootstrap`과 WorkspaceClient/bootstrap→useLiveWorkspace→App이다. 공개 `/api/bootstrap`에는 새 자료를 노출하지 않는다. source store 원 snapshot의 canonical SHA와 작업실 project SHA를 일치시키고 계약 버전0.1.0의 additive 정의를 같은 release에서 배포한다. 기존 합성 소비자/자료팩은 변경하지 않고, 구버전 작업실에 신규 bootstrap이 없으면 명시적인 연결 오류로 표시한다. 서로 다른 자료 버전의 프로젝트는 이어 쓰지 않는다.

판단 실패의 공개 진단에는 고정 코드·이유와 입력 근거/검사된 Need·Gap·연결 Concept ID만 허용한다. 필요한/누락 근거 배열·질문 종류와 이미 존재하는 Need의 구조화 모순을 보여주되 provider 문자열·private 경로·임의 오류 텍스트를 보내지 않는다. Concept에는 model_id가 없으므로 허용 Gap 및 입력 근거로 인가한다. 독립 검수에서 발견한 Concept ID 소실 P2는 실제 snapshot 회귀로 수정한다.

검사는 Python/Ajv 같은 정본, 실제 인증 HTTP 응답·무인증401·no-store·동일 SHA·공개 synthetic 서버 거절, 원문/내보내기 projection과 웹 계정 전환/연결해제 자료 폐기를 포함한다. 자료 조회의 성공과 실제 모델/의미 품질·전체18모델 실행·게시일/시즌 동향 검증을 구분한다. 정확 구매SKU와 게시일을 추정해 채우지 않는다.
