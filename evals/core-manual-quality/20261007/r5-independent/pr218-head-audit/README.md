# PR218 고정 head의 CORE 독립 검수

기록 ID: CORE-R5-PR218-AUDIT-01a10729-01 / 황대겸 / 2026-10-07 KST.

검수 대상은 [PR218](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/218)의 head `0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d`, base `2d2b27c87d8d536e1c8f7219bfbaf74f64eb8f2b`이다. 실제 병합 `8ec1e8a51faabd6db032e52245680bef4229f93f`의 CORE/관련 Skill Git diff도0이었다. 이 검수는 제품 코드를 수정하지 않는다.

## 실제 확인

- 고정 image `sha256:36ad082dbccf05bc9cff7c4dc5766e9ab7ed8c42198b0b731cf3831c546aaaf0`, UID65534, networknone, read-only, 인증정보/소켓 mount0에서 관련 회귀166건 PASS/skip0. [검사 수신](checks.json)과 [로그](core-regression.txt)를 읽는다.
- PM이 추린 counterexamples SHA `a1c25f1c405c2da887d52dd4b56639b6d7eddb7c9deb33a92a6d9bb29129e9cf`: 원3 입력·거절출력 및 선택5호출의 data/request_context가 보존된 전체 원본의 정확 subtree다. [원문/자료 해시 대조](counterexample-data-check.json).
- 원3의 Gap27개에서 Need/리뷰/기능 설명서 ID와 model/version·지원 선언·잔여 상태·질문을 현재 CORE 반환값과 직접 대조했다. 정상·변경 각각 explicit_supported9/remaining8/resolved1, 설명서 부족 unmentioned9/unknown9/candidate0이었다. 이는 원 모델 선언과 연결이 보존된다는 증거이며 선언의 자연어 의미 정답을 승인하지 않는다. [전체 연결](mapping.json).
- 변경 CONCEPT002/003의 MANUAL001 누락은 후보·Gap·Need·누락 ID를 포함한 피드백으로 유지된다. 정상 후보에 이미 있던 RE008과 차별점 검수 항목의 인용 누락을 구분하고, 질문 없는 held 수정은 거절한다.
- 기존 무후보 원 응답은 새 필수 선언 필드가 없어 거절된다. 동일 Need 누락 주장을 새 필드에 넣은 authored fixture는 실제 NEED006→RE007과 모순이라 거절된다. 실제 설명서 부족에 맞게 작성한 별도 fixture는 held를 유지한다. 이 fixture를 새 실모델 결과로 표시하지 않는다.
- 고정 연구 records/manifest4 SHA와 실행 dataset SHA를 대조했다. 실행 dataset은 제품3/설명서 Evidence21/Feature9/후기0이며 feature↔manual ID·모델·판본이 연결된다. 연구238/평가 후보36을 확인된 구매 모델·게시일 또는 독립 품질 분모로 승격하지 않는다.

## 재현과 한계

검사 pattern은 checks.json에 고정돼 있다. unittest loader로 해당9 pattern을 기존 고정 Docker에 모아 실행했으며 원본 snapshot SHA는 검사 전후 동일했다. Mapping 재현기는 [verify_mapping.py](verify_mapping.py)이며, 동일 head 전체 저장소를 `/source`에 읽기 전용 mount하고 기존 image의 `/opt/lgax-venv/bin/python -I -B -X utf8`로 실행한다. 재현기와 [source-manifest.json](source-manifest.json)을 같은 audit 폴더로 따로 mount한다. 프로젝트 import 전에 Git blob·원 snapshot과 대조한 CORE/계약 Python 전체 및 schema38파일의 inventory·각 SHA·합성 digest를 확인한다. manifest 자체 SHA도 재현기에 고정되어 있어 다른 manifest나 다른 소스는 import 전에 exit2로 실패한다. 출력 `source_binding`은 실제 확인한 source ref·manifest digest·source digest를 담으며 런타임 Git HEAD 조회로 표현하지 않는다. networknone/UID65534/read-only/cap-dropALL/no-new-privileges/pids128/memory512m/cpu1/tmpfs64m을 사용한다. 호스트 인증 환경에서 제품 코드를 import하거나 새 image를 pull하지 않는다.

첫 mapping 시도는 Docker pipe 권한 오류로 실행0, 권한 경계가 허용된 같은 격리 실행은27행 대조 통과였다. 첫 전체 source export의 Windows 긴 경로 실패를 보존하고 새 짧은 scoped snapshot으로 검수했다. 최초 native GitHub 최종조회도 sandbox socket 제한으로 실패한 후 읽기 전용 재조회됐다. 제품/원 결과를 수정해 검사를 통과시키지 않았다.

PR221 리뷰5437222152 후 [source-binding-checks.json](source-binding-checks.json)의 고정 Docker4검사에서 정확 소스의27행/원 mapping cases 일치와, 첫 프로젝트 import에 실패 marker를 넣은 CORE 변경·미고정 Python 추가·manifest 변조의 import 전 exit2를 확인했다. 원 mapping/입출력·counterexample 대조·checks.json·166건 로그는7ecda6a의 원바이트와 동일하다. 166건 전체 검사나 모델 배치를 다시 실행하지 않았다.

작성 시점 `2026-10-07T02:46:42.770929Z`에 받은 전달 실패 보고는 [PM E049의 native 중단 실험](../../../../../docs/작업근거/정이량/2026-10-07/정이량-E049-REAL-PROTOTYPE-R5.md)이다. 식별 근거는 원 closure SHA `0477a92526cd519f32f69f5cfbcf27872c001e4ef7ef19a578b7d6fea6392fa1`, exact source `e1a6ec794039aca6278f415bd5aaef901cf3f920`이다. 당시 CORE 수신은 PM의4known/22,189토큰＋1unknown·finaloutput/run0 보고까지였고 해당 closure 원문·study_id 문자열·semantic_review 최종 응답은 인계되지 않았다. 원 실패와 불명 비용을 보존하며 이 식별자를 이후 실행에 붙이지 않는다.

`2026-10-07T03:13:25Z` [PM 리뷰5437222152](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/221#pullrequestreview-5437222152)로 별도 study `live-intake-8ec1e8a51faa-122b-r5-deferred-normal-native-http-fresh-20261007-bounded8-100k`, source `8ec1e8a51faabd6db032e52245680bef4229f93f`의5회/33,237토큰 정상 런타임 전달 완료·독립 의미 검수 FAIL을 수신했다. 이 최신 보고는 앞선 전달 실패가 현재에도 계속된다는 뜻이 아니다. CORE가 새 원 input/output/trace를 독립 대조한 증거는 아직 아니며 quality PASS·변경/설명서 부족 사례 승인·실제3제품 완주·부모 Done으로 확대하지 않는다. 현재 별도 PM CORE 수정/통합 검수의 정확 head와 고정 원 결과 인계 후 본인 의미 대조를 이어간다. 신규 모델0/기존 원15회91587토큰 보존/원6 AI 채점 반복0. 자동 재POST/추가 비용은 없다.
