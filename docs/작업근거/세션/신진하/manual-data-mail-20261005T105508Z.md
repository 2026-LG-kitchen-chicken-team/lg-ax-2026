# manual-data-mail-20261005T105508Z — 구현 근거와 검사 대기

- 담당자/수행 AI: 신진하/Codex 단일 모델. 확인일 2026-10-05, 기록 시각 20:08 KST.
- 연결: [동일 세션 작업기록](../../../작업기록/세션/신진하/manual-data-mail-20261005T105508Z.md). 원 사용자 요청과 전달된 PM 지시 전문/발췌·해석은 작업기록에 구분해 보존했다.
- PM 식별: PM-20261005-AUTO-7f4770dc93e76d05 / Issue13 comment5991958336, PM-20261005-AUTO-1ff99fd83676d52a / Issue13 comment5992248482. 출처는 사용자 전달이며 메일/GitHub 직접 대조는 수행하지 않았다.
- 근거 종류: 로컬 코드와 계약 읽기, 허용 파일 작성, 소스 검토, sha256sum. 테스트/모델 실행 증거가 아니다.

## 계약 의미와 구현 선택

`review_csv.py`의 FIELDS는 id/model_id/text/source_kind/document_version/source_id/row/evidence_id이고 기존 Repository는 36개 동등성 전송 도구다. 새 import는 같은 헤더로 임의의 승인된 새 리뷰를 받고 Review.locator.row 및 대응 Evidence를 생성한다. origin.end_row와 원본 SHA는 canonical entity 밖에 보존한다. identity 값은 padding을 거부하고 text는 공백·한글·개행·수식 그대로 보존한다.

`documents.py`의 sha256은 원 PDF 바이트, text_sha256은 excerpt UTF-8, start_char/end_char는 추출 페이지에서의 0-based half-open 문자 위치, document_version은 제품과 근거에 공통인 버전이다. `document_store.py`는 Review/Evidence 원문 필드 동등성과 모델/버전 연결을 검사한다. 새 API는 이 의미를 유지하며 같은 텍스트라도 다른 버전이면 VERSION_MISMATCH다. 삭제 None은 SOURCE_MISSING, 변경 바이트는 SOURCE_CHANGED, 다른 인용 원본 해시는 SOURCE_MISMATCH, 인용 자체 해시는 TEXT_HASH_MISMATCH, 실제 범위와 다른 인용은 QUOTE_MISMATCH다.

## 실제 행동과 미실행의 경계

허용 네 코드/테스트 파일과 자기 두 세션 문서만 생성했다. 터미널에서 로컬 경로 검색·읽기·시각 조회·파일 해시 계산을 수행했다. 테스트, import smoke, py_compile, 하네스 상태 변경, Git 명령, commit/push, 네트워크, GitHub/controller/메일/인증파일 접근, 하위 에이전트 실행은 하지 않았다. source 검토에서 입력 alias·물리 행·행/문단 경계·해시와 버전 분리를 확인했지만 실제 실행 성공을 선결정하지 않는다.

Git128은 사용자와 기존 로컬 기록에서 인계된 blocked 실패 이력이다. 새로운 재현/원인 진단/수리가 아니며 이전 blocked 실행·예산·기록은 그대로 보존했다. 자동 controller lease 획득이나 PR 완주를 주장하지 않는다.

## validator 예정 명령·입력·판정

작성본 SHA256 (로컬 `sha256sum` 실제 출력, 세션 문서 자체 해시는 포함하지 않음):

| 파일 | SHA256 |
|---|---|
| packages/core/src/lgax_core/review_import.py | 2e80bb767fe4e4e2e094d64c064a00385f84ffba54c54f039dc9e725a2e50f20 |
| packages/core/src/lgax_core/source_ranges.py | a6a46e4868e9f8a88de86f5c6bd6b3b7672d89a3ee13ceb77d4e7c165b7e9687 |
| tests/test_review_import.py | 8fedff9dfec0b82fc4658436d875bc198145783d62ae4dd41b5bb63a0a7d3004 |
| tests/test_source_ranges.py | e38ac8b4e75c44f1458998f362180a87084e5cfa64fe4dce306769e8c23d7a48 |

읽은 공통 계약 SHA256: `d7cf46d9a980b00ad786ec46feaf3d31e4094f56ff0899d8bab59bdf95a9bad5`.
읽은 review_csv.py SHA256: `d0ea7093c8bdffcca4bdc4bb17669f62d27f603fefe7d99df6b8d15e0d3a8612`.
읽은 documents.py SHA256: `6b66ead753aa9bec0890a4ad55d22345ef36852b0045c781ed25f46825b3577c`.
읽은 document_store.py SHA256: `d101613f981ce92bab376692b04831ab3b3f25416e94c495c4042e40a68a4b45`.
Git/원격 조회를 하지 않았으므로 commit 및 원격 main과의 동등성은 미확인이다.

인증 없는 별도 validator에서 기존 잠긴 환경으로 수행할 예정이며 본 세션에서는 실행하지 않았다:

```sh
uv run --no-sync python -m unittest discover -s tests -p 'test_review_import.py' -v
uv run --no-sync python -m unittest discover -s tests -p 'test_source_ranges.py' -v
uv run --no-sync python -m unittest discover -s tests -p 'test_document_registration.py' -v
uv run --no-sync python -m unittest discover -s tests -p 'test_document_plan_history.py' -v
uv run --no-sync python scripts/check_contracts.py
```

새 테스트 입력은 테스트 내 SYNTH 모델/출처/한국어 CSV/텍스트/합성 binary이며 실제 고객 자료/PDF가 아니다. CSV 테스트는 공개 API로 새 입력 수용·원본 hash/BOM·quoted comma/multiline·물리 행·중복/잘못된 모델·없는 출처·손상 UTF-8·한도·외부 변경을 구분한다. source 테스트는 공개 capture/verify API로 한국어 CRLF·page/line/paragraph/section·원문 삭제/변조·다른 버전·잘못된 위치·없는 인용·외부 추출 snapshot 불변을 구분한다. 실제 결과/exit/성공 개수는 현재 **미측정**이다.

## 지지하는 주장과 한계

재사용 가능한 순수 로컬 API와 실패 사례 테스트가 작성됐다는 코드 근거다. 원본 영구 저장, 승인 인증, PDF/OCR 추출 fidelity, 실제 고객 수요/실모델 평가, 자동 PR/CI/병합/부모 Done/최종 제출의 근거가 아니다. 외부 pages는 trusted extraction 입력이며 반환 receipt에서 이를 명시한다. CSV 승인 목록과 현재 원문 읽기는 호출자 책임이고 네트워크 조회는 없다.

다음 행동: validator 실제 실행 결과 기록 → 실패가 있으면 정확 사례와 traceback으로 허용 파일 수정 → 별도 권한/절차에 따른 PM 인수. 본 모델의 테스트 미실행은 직접 사용자 제약을 따른 것이며 성공으로 채우지 않는다.

## 실행자 확인·현재 결과 — 2026-10-05 20:27 KST

사용자 실제 요청: “깃 128오류가 난데 이거 해겨래”, “추가사항: 깃 오류 해결하고 정이량에게 온 메일 작업 실행해”. 아래 모델 기록의 직접 지시 인용은 실행자가 모델에게 전달한 범위 제한 prompt이며 사용자의 실제 발화를 그대로 인용한 것이 아니다. 실행자는 연결된 자기 Gmail에서 PM 배정 알림 메일을 읽었고 Issue13의 [CSV 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-5991958336)·[인용 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-5992248482)에 연결했다.

Git128은 실제 동일 옵션의 worktree 생성에서 `Filename too long`으로 재현됐다. 원 상태에서 fetch/기본 조회는 PASS였으며 긴 경로가 checkout을 막았다. Worker 전용 Git의 core.longpaths=true와 짧은 state/execution/auth 실제 폴더로 복구했다. 같은 Limited 예약 작업에서 fetch·checkout·최장219자 소스 파일의 Python 읽기 PASS, 새 Pythonw preflight의 계정/컨테이너 로그인/중앙 연결 PASS를 확인했다. Windows 전체 긴 경로 설정 변경은 도구 정책이 차단해 수행하지 않았으며 현재 값0을 유지한다. 원 token/로그/실패 checkpoint와 전용 AI 로그인은 같은 볼륨에서 원본 이동하여 보존했고 인증 복사/재로그인/다른 계정 사용은 없다.

생성은 실제 고정 Docker 모델 컨테이너에서 1회 수행했다. CLI turn.completed와 schema 결과 원본을 보존했다. 도구 반환 단계의 오래된 긴 AI cache 경로 정리 오류로 daemon exit code는 private 결과에 보존되지 않았으므로 그 코드를0이라고 추정하지 않았다. 새 짧은 전용 profile로 원 로그인과 캐시를 옮기고 모델을 재호출하지 않고 같은 생성물을 검증했다. 원 로그 SHA256 `bc0cdb6c02cac3bd9fb4a0201a6586b2891c656001cc317bc99c8f1e6487142b`. 실제 CLI usage: input645006/cache-input566784/output17517/reasoning-output1436(청구액이 아니며 cache/reasoning을 별도 더해 전체 사용량으로 만들지 않음).

검사는 원 AI 프로필도 mount하지 않고 network=none인 별도 validator의 소스 복사본에서 실행했다. 결과: test_review_import.py: 9개 PASS, test_source_ranges.py: 10개 PASS, test_document_registration.py: 10개 PASS, test_document_plan_history.py: 4개 PASS — 총 33개. 검사 후 모델 소스와 validator 기존 파일의 bytes/hash를 대조했고 변경이 없었다. 비밀/링크/허용 경로 검사를 통과한 일반 파일6개만 게시 clone으로 반입했다. 코드 자체는 검증한 bytes를 유지한다. 토큰·private 로그·메일 주소를 공유하지 않는다.

이 결과는 사용자 승인 수동 복구 PR이며 이전 auto28a/auto7f/auto1ff blocked 기록·원 시도/예산·controller lease를 변경하지 않는다. 부모 Done, 자동 무인 개발 완주, PDF/OCR 정확도, 실제 고객 자료 확보·새 API/UI 통합을 주장하지 않는다. 두 API를 실제 등록/검색 경로에 연결하는 별도 단위와 PM 독립 검수·병합·통합 인수는 후속이다. 자기 Worker는 실제 숨김 Limited 프로세스로 다시 가동하고 새 승인 패킷을 기다린다.
