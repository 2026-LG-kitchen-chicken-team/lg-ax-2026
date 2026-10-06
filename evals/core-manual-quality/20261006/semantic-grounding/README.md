# 기존 제품 근거와 신규 가설 후속 검증 구분

PM #11 댓글6015780670의 full-cap-v3 원 실모델 결과를 고정 PR1886153c238/Git blob으로 읽었다. 원 SHA·source428f237와 현재 semantic_review가 동일함을 확인했다. 새 가설 차이를 명확하다고 적은 검토가 그 가설의 설명서가 기존 원문에 없다는 이유로 uncertain이 됐고, 현재 제품의 공간 부재·바구니 전체 세척 단정은 satisfied로 남았다. 원 MANUAL001은 선반 분리·식품 이동만 설명한다. 원 결정은 correction2 소진 QUALITY_UNCERTAIN/held다.

semantic_review INSTRUCTIONS에 설명서 대조 대상이 현재 기능/조건임을 명시하고 신규 가설의 동작 원리가 원 설명서에 없다는 이유만으로 차이 검토를 보류하지 않도록 구분했다. 고객 리뷰와 제품 명세의 범위를 구분하며 현재 구조/기능의 근거 없는 확정 문구는 기존 unsupported_factual_claims violation으로 검토한다. 가설의 작동 방식/차이/후속 검증 전제는 기존 각 기준으로 별도 평가한다. 강제 통과·verdict 치환·검사 완화가 아니다.

AST에서 INSTRUCTIONS 값만 제외한 전체 모듈이 기존 source와 동일하다. 네 기준·schema·validator·인용·공유 correction2/hold gate·PM 어댑터/다른 담당 source는 변경하지 않았다. 새 prompt 뒤 실모델 효과는 미검증이며, PM 고정 model/source/input/잔여 누적 예산/중계 인계 뒤 검증한다. 원6독립 평가와 R6 ledger/유실/49277 추가관측을 보존한다.

[원 반례·자료 범위·소스 SHA](recorded-counterexamples.json) · [격리 검사](checks.json)

격리 회귀78건(실패0/오류0)·ruff·규칙 동일·기존8파일/231구간/28세션 보존·계약·phase2 검사가 통과했다. Docker network-none/UID65534/소스 읽기전용/인증·소켓 마운트0이며 신규 모델 호출0이다. 해당 두 CLI 오류는 원 입력 보존·환경 누락 거절을 확인하는 기대된 음성 검사다. 실모델 후속 품질은 아직 미검증이다.
