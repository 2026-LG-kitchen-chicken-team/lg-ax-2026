# 정이량-E056-FUNCTIONAL-PROTOTYPE

2026-10-08 KST · PM009의 실제 변경·수신·검사 근거. 본인 연결 조회와 수동 실행만 기록한다.

- 시작 main: `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`.
- CORE 고정 head: 247 `7ef977e269233480e535e1186334e52cdfb234ce`, 248 `68b822108f8bdbadb2352ffa0554ab332c1d0db2`, 251 `d9a50b93a728123f12abe4a83d53d84ac1f6c5bd`.
- WEB 고정 stack 최종 head: 261 `c0116fb026eabd24a6d2276451cea86070205ee4`; 선행249/250/253/255/256/260 commit을 보존한다.
- 새 PM 작업 branch에서 원 head들을 merge했다. 기존 CI 결과는 해당 head의 구조 검증 근거로 재사용하며 새 통합·제품 품질 증거로 바꾸지 않는다.
- owner README 충돌의 원본·합친 SHA와 block 밖 byte 보존 근거는 비공개 로컬 `work/r9-owner-readme-union.json`에 있다. Git merge 원 부모/원 commit도 보존한다.
- 메일 확인: Gmail query `after:2026/10/07 (LG OR 해커톤 OR lgax OR 기획) -in:trash -in:spam` 최근10건과 CORE251/WEB261의 후속3건씩. 개인정보·발송주소·메일 헤더는 Git에 복사하지 않는다. 첫 페이지 이후 메일은 미조회다.

## 필요한 변경 검사

- targeted commit `e99de0fd546c67822b60a11f56dda2ef3be2bbaa`: 40검사 PASS, 실행ID `pm-four-fast-a0ed522164d4429982f07a4efc8dd4cf`.
- 같은 commit CORE149검사 PASS, 실행ID `pm-four-fast-03cad4c6a9fb4b74a9ee21e73549e0fe`.
- 두 Docker receipt 모두 readonly root/소스·network none·UID1000·capabilities drop·no_new_privileges·인증/AI profile mount 없음, source_changed=[]·model_calls=0이다. image pin `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`. private/runtime의 각 receipt와 executor.log를 보존한다.
- 최초 연결 검사 실패는 새 테스트의 토큰 길이·HTTP422 기대값 설정 오류였다. 원 실패를 보존하고 수정했다. 제품 의미 실패나 실모델 실패로 표현하지 않는다.
- WEB47 관련검사·build/typecheck PASS와 CORE 새 native 경계9검사의 하위 실행 근거를 재사용한다. 원격 필수 CI는 새 통합 head를 별도로 확인한다.

## 실제 자료 인수

R9 운영 입력 SHA: 냉장고 `523dcf1ec8e4291dc73bd0b51cea0be4765912e9e5b7993cf1d55af389876655`, 전자레인지 `c9cf7d3d9f8853ceaa49c853dafc4a7ae6745508aa6519676a77ba40b9b334ae`, 식기세척기 `fbc233a429c6ec1ceeb1571ce509ecad7d9494fe5388a0524fd3e64bfa0639ff`. 원문184·개발후기141은 원 자료 그대로다. 공식 PDF16 URL/고유15개 수신은 공개 `manual-intake.manifest.json` 및 `manual-intake-checks.json`에 원 SHA·bytes와 연결한다. PDF/private 이미지·토큰은 Git에 넣지 않는다.

## 실모델·원문·연결 결과

- 27B digest `25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e`, context16,384/output4,096/temp0/seed42/thinkfalse, 실제 normal와 condition 각2call·0repair. source_facts73/부모 revision/API↔stdio MCP 동일성을 확인했다. 원 실패/원응답은 private trace에 남긴다.
- 독립 의미 대조와 실제 지침 수정의 범위는 [`evals/pm-r9/20261008/semantic-review.json`](../../../../evals/pm-r9/20261008/semantic-review.json)에 있다. 원 차단 사례 두 종류가 재발하지 않았지만 새 과장·귀속·행동 순서 오류를 발견해 전체 품질 승인하지 않는다.
- selected6 실행 `run-de49db0645744cf0bede63db0ed030e0`: discover1call·item_issues0·수리0, plan은 입력6500char초과로 호출되지 않았다. 수동 CLI9000char로 수정하고 같은 원문 범위로 새 실행을 확인한다. 모델4call·문제1개·수리2·원문1000char 한도는 유지한다.
- CORE251 최신 후속 `f02f9c561c86ad74217f29eabfeb71eae290af43`를 별도 검수·merge했다. 직전3실험과 해당 후속의 의미 검증은 구분한다.
- targeted65PASS 실행 `pm-four-fast-fbf88a8d247e41f389dc630a50f9a3e9`, commit `9fd8c9c10530a8ae8f6b77c68807f6b2976467b6`; fixed validator/Docker 조건과 source_changed=[]/model_calls0 그대로다.
- WEB 공식 안내서 새 focused6검사·build/typecheck PASS. 현재8bundle등록·문서참고5/리뷰0, 원문 선택 역할/domain/SHA/fullfacts 검증·late download 폐기·HTML 화면삽입 없음.
- 실제 브라우저가 만든 JSON은204824bytes, bundle+normal brief ID 일치. 최종 파일명/Save As 미확인은 별도로 남기고 다운로드 bytes 수신만 기록한다.
- 실제 안내서 API↔stdio MCP 전체 응답 동일, 원5source/facts/locator·SHA `dfd4d3c3f5e6284fddc24b91b7a3e4529faeb6bb38858244f42729d9d6a51856` 보존. HTML11256bytes/MD8481bytes, 새모델0회. 참고자료 목적과 공용 문서·구매SKU/게시일 미확인 표시를 확인했다.
- selected6 후속 `run-134d345ae29d4db98d98e2b579d5016d`: 입력9000에서 길이차단0, discover+repair_fields2call·공유수리1·문제0. 지침 echo로 생긴 원자료 밖1분은 검사가 보류했다. 원 실패 응답과 수리 응답을 보존하고 일반 지침의 자료/규칙 경계만 보완했다.
- 모델 없는 CLI9000 구성 신규2검사와 해당 파일 Ruff PASS; 이 검사를 실제 prompt/token/품질 검증으로 확대하지 않는다.
- `run-4b4769df607a4552800cfbddccb3a476`: discover1call·output_truncated, 성공한 처리 고객0/인용률null. raw/usage가 adapter의 길이 오류 이후 생성되지 않는 trace 공백도 독립 검수에 기록했다. 이것을 실제 토큰4096 측정 또는 의미품질 통과로 바꾸지 않는다.
- 공통 출처 지침을244자로 줄이고 기대 시간의 구체 숫자 예시를 삭제해 규칙과 원문을 분리했다. trusted native 의견 지침과 원schema/수치검사/2수리/4call은 그대로다. 지정3검사 및 두 파일 Ruff PASS; 실제 정상/조건 후속은 별도 결과다.
- 첫 LG 전용 모델 종료 receipt: owned_server_stopped=true, existing_services_changed=false, foreign_process_signals=0, gpu_after_cleanup used6321MiB/free42220MiB/util0. 새 추가 유한 수동 세션의 receipt를 원 세션 파일과 구분해 보존한다.

새 통합 head 필수CI·원격 병합은 결과 확인 후 추가한다. 본 기록은 부모 Done·외부 사용자 테스트 완료를 주장하지 않는다.
