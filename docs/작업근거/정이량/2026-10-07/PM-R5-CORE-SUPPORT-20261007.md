# PM-R5-CORE-SUPPORT-20261007 근거

수행자는 PM 정이량의 보조 AI이며 황대겸의 수행·자기보고·개인 원문을 대신하지 않는다. base `1f3f4ecb93fdd945850a1e9f790bc37766b2355c`에서 CORE 판단 파일·관련 Skill·회귀만 변경했다. 외부 게시·모델 호출·자동화 ON은 0이다.

원 3 JSON의 완전 바이트는 PM 인계 commit `814fe2fbcd3b752ff6400d8a08671dce7bdd2d80`의 `evals/pm-integration/20261007/live-originals/manifest.json`과 Git blob에서 직접 대조했다. manifest SHA `e3222917396f9c8083077c69c132bb4507f7984e83d0d5e3469bd96bbad6051c`. 원 정상/변경/부족 SHA·bytes는 manifest와 일치한다. 선택 artifact SHA `a1c25f1c405c2da887d52dd4b56639b6d7eddb7c9deb33a92a6d9bb29129e9cf`이며 원 입력·rejected_output와 원 call의 context/data가 각각 정상 indices `[4,5]`, 변경 `[3,4]`, 부족 `[3]`에서 완전히 일치했다. 원문은 변경하지 않았다. 이 대조는 stdlib JSON/Git bytes만 다룬 host metadata 점검이며 제품 코드를 실행하지 않았다.

첫 검사 source `04716a13dbdc62364392ee83ea2cc8570c9182bc`, 실행 ID `pm-r5-core-59605dd7aa284b91a20482355d79b63e`. 고정 source-proof 검증한 metadata wrapper SHA `aebff37bc64edc1ddbb31abe2d0fc308e547b1f45840f8c23a1d092ad75456ba`, guest bootstrap SHA `47b07b4840ff3766f7a7d1ebdafdc0f6700ed05c3e739f26176225254bdfbaf0`, archive SHA `01a5fb0027b595b55dc84d4533b7dd7d8f3138c00218423dfd199748cb381cd5`. image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`, role validator, uid1000, readonly root/source, caps dropped, no new privileges, network none, mounts `/workspace`·`/artifacts`, publisher credentials/AI profile 없음. source_changed `[]`, model_calls0, network_calls0.

155검사 중 153통과, 새 fixture setup2개 실패를 보존한다. semantic fixture의 `output_sha256` 누락과 질문 있는 hold shape fixture의 `hold_reasons` 누락이었다. 원3 실제 반례 거절·원 입력/출력 digest·기존 회귀는 통과했다. 제품 판단 코드를 느슨하게 바꾸지 않고 두 fixture의 의도한 입력을 명시해 고쳤다. 검사 재실행은 이 수정에만 따른 것이며 결과는 후속으로 기록한다. 첫 shell 인자에서 잘못 복사한 SHA는 wrapper의 인자 검증에서 거절되었고 archive/제품 실행 전에 종료했다.

이 검사는 원 모델 응답 재현과 MockTransport 회귀이며 실모델 의미 품질 PASS가 아니다. 조건 JSONSchema의 Python 검사와 Ollama native 지원은 다르다. 새 no-candidate 선언의 구조화된 누락 주장은 코드가 대조하지만, 자유문장의 주장이나 잘못 분류한 질문 의미까지 자동 증명하지 않는다. 기존 shared2수정·raw response/trace·failed/held·독립 의미 검수를 유지한다. 원 15generations/91587tokens와 이전53/193708 및 unknown 이력은 수정하지 않는다.
