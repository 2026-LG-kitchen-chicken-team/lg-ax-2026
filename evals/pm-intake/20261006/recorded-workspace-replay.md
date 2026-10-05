# 실제 모델 출력의 HTTP·MCP 저장/조회 재검증 · 2026-10-06

## 작업 지시와 해석

PM이 이미 실행한 냉장고·식기세척기·전자레인지의 기본/조건 변경 6개 결과를 그대로 보존하면서 실제 Workspace SQLite, localhost HTTP API, MCP stdio SDK에서 같은 ID와 원입력을 조회할 수 있는지 확인하도록 지시했다. 추가 모델 호출이나 제품 소스 수정은 이 작업 범위에 없다.

`replay_workspace.py`는 실행 녹화 파일을 반환하는 전용 평가 runner를 주입한다. 실제 제품 자료 조회로 조립한 입력이 녹화 당시 `original_input` 및 입력 hash와 정확히 같을 때만 해당 기록을 반환한다. 원본 출력 byte hash·생산자 요약의 상태·실제 호출 수·내부 수정 회차도 확인한다. 불일치이면 실패하며 성공 fixture를 만들거나 모델을 다시 호출하지 않는다.

## 검증 범위

- 무인증 Docker 내부에서만 평가 코드를 실행한다. SQLite, localhost HTTP 서버, 인증 토큰과 MCP 인증 파일은 한 실행의 임시 영역에 생성한다. GitHub·controller·PM·AI 인증정보는 들어가지 않는다.
- 실제 HTTP POST로 제품군별 프로젝트 1개와 기본/변경 실행 2개를 저장하고 GET로 다시 조회한다. private 저장 내용은 원본 녹화와 동일하고 HTTP 반환은 제품의 기존 진단 가림 규칙 `public_run`과 동일해야 한다.
- 변경 실행을 만들고도 이전 실행의 요청·자료·결과가 바뀌지 않아야 한다. 사용자 조건 변경 회차 0/1, Agent 내부 수정 회차 0~2, 이전 실행 ID를 구분해 확인한다.
- 원 6개는 보류 1·실패 5다. 이 상태를 유지하고 화면용 후보는 0개여야 한다. 원 모델 호출 23회는 역사 기록이며 이번 재검증의 새 모델 호출은 0회다.
- 인증 없는 조회는 401, 같은 소유자의 viewer 읽기는 허용, viewer 쓰기 및 다른 소유자의 조회는 403이어야 한다. 거절된 쓰기로 runner가 실행되어서는 안 된다.
- 실제 MCP SDK가 stdio 자식 서버를 실행해 초기화·7개 도구 발견·프로젝트/이력/실행 조회를 수행한다. source PYTHONPATH를 명시하고 게스트에서 만든 인증 파일만 사용한다. HTTP와 MCP의 프로젝트 ID·실행 ID·공개 snapshot이 모두 같아야 한다.
- 원본 입력 파일·품질 요약·dataset은 검사 뒤 hash가 같아야 한다. 결과 파일에는 임시 인증값을 남기지 않는다.

## 재실행

고정 무인증 validator에서 원본 6개와 `summary.json`을 같은 상대경로에 제공하고 다음 argv를 실행한다.

```text
python evals/pm-intake/20261006/replay_workspace.py
```

기본 기록 경로는 `evals/pm-intake/20261006/live-quality/original-six`, 원 입력은 `evals/pm-intake/20261006/core/cases`, 자료는 `data/demo/dataset.json`, 산출물은 `/artifacts/recorded-workspace-replay`다. `--records`, `--inputs`, `--dataset`, `--artifacts`로 검토한 입력 경로만 지정할 수 있다. 산출물 하위 폴더가 이미 있으면 덮어쓰지 않고 실패한다.

생산자 요약의 입력·dataset SHA는 원 파일 bytes를 해시한다. Agent의 `input_digest` 및 WorkspaceStore의 dataset SHA는 canonical JSON 내용을 해시하므로 서로 다른 값이다. 도구는 원 파일 SHA를 먼저 확인하고, 별도 canonical SHA와 실제 자료 조회 입력을 함께 보존한다. 두 규약을 같은 SHA라고 가정하지 않는다.

`summary.json`, `http-readback.json`, `mcp-readback.json`은 실제 실행이 끝난 뒤에만 생성한다. 이 문서를 작성한 것만으로 검사 통과를 뜻하지 않는다. source commit·검사 조건·실제 결과는 후속 근거에 연결한다.

## 주장하지 않는 범위

이 검사는 **이미 실행한 모델 결과의 저장/조회 재현**이다. 새 모델 실행·실제 브라우저 조작·ChatGPT/Claude 외부 연결·운영 배포·상품기획 품질 통과의 증거가 아니다. 원 합성 입력의 품질 실패·비용·수정 예산은 유지하며, 통합 조회 성공으로 기존 품질 실패나 전체 신청서 요구사항을 완료로 바꾸지 않는다.
