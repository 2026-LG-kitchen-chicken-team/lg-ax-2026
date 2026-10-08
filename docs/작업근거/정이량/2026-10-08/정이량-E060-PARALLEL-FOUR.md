# 정이량-E060-PARALLEL-FOUR

KST 2026-10-08. 최신 직접 사용자 지시: “LLM이 동시에 4명다 요청 처리하게 바꿔”. 이전 다른 채팅의 순차 대기열 제안보다 실제 모델 병렬4를 우선한다. 기존 프로토타입 source0541/기록02ba991·PR284에서 이어 하며 완료한 기능을 새로 만들지 않는다.

편집 배정: PM root는 전용 모델 서빙 환경/격리검사/원격배포/실모델/기록, core_audit는 gateway durable job 및 기존테스트, remote_audit는 웹client/상태/poll/복구와UI테스트, remaining_and_data는 독립 큐 새테스트만 수행한다. 실제 사람이 직접 지시한 현재 AI 협업이며 개발 자동Worker/예약은OFF다.

GPU3 모델27B가 올라간 상태의 여유24,204MiB·GPU1/Naru 및 타GPU 프로세스 보존을 읽기 확인했다. 최신 사용자 실제 기획은완료된 뒤 배포한다. 기존HTTP는graceful drain하고소유web/model만개정하며tunnel은재시작하지않아주소를유지한다. 병렬4/context16384와token4096/pinned model/store/binary/keep_alive=-1 유지. 단일모델콜timeout은4병렬지연에맞춰기존ModelConfig상한내300초로서빙에만적용한다.

새게이트웨이는최대4실행/활동8접수/초과FIFO대기·세션활동1·소유자조회·input/owner/result SQLite보존을구현한다. HTTP202접수후GET상태를조회하며POST재전송없음. 원문GET/검색은계속사용한다. 모델병렬권고는[Ollama 공식FAQ](https://docs.ollama.com/faq)의VRAM/context증가조건과대조하며환경변수4만으로실제성공을주장하지않는다.

검사/배포/4독립세션실모델응답·기존서빙유지·의미품질제한은실제고정근거로완료보완한다. 새합성리뷰/Figma/새유료모델API0·CI상한/보호검사변경0. 실제모델동시처리와독립의미품질/전체Done은구분한다.

## 첫 실제 실행의 제한과 수정 방향 — 14:19 KST

- 게이트웨이 worker4 배포 source `5beedded4717415ad9c5cc081a017cd55b319509`의 실제 독립 세션4/선택 실제원문6/공개 POST4는 모두 완료·저장 및 목표/선택근거 대조 일치였다. GET 자료200, 타 세션 job/run404. 그러나 모델은 `OLLAMA_NUM_PARALLEL=4`에도 `-np 1`·`n_seq_max=1`이었다. 이 결과를 실제 모델 병렬4 성공으로 채택하지 않는다.
- [Ollama scheduler 원문](https://github.com/ollama/ollama/blob/main/server/sched.go)의 qwen35 계열 강제1 분기와 원격실로그가 일치한다. 처음 설정만으로 충분하다고 예상했던 판단은 수정한다. 기존 모델·양자화를 바꾸지 않고 같은 bundled llama-server의 텍스트 전용4슬롯 경로를 검증한다.
- native binary `234b05b2138264f8fb263c3205e85f4c290e8afe5067e280a4f6f90cdac5696b`·commit `0f3a71be1`·원 GGUF `f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d`·manifest25b843 고정. 슬롯별16K/총65536, KV분리·context shift OFF·이미지 encoder 제외·GPU3 유지. 참고 [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- serving 전용 adapter가 정확한 Qwen think=false 단일 사용자 렌더링, native schema·기존 로컬 검사, 실제 tag sampling(top_k20/top_p0.95/min_p0/temperature0/seed42), 토큰/시간 계측과 원 파일/실 props before-after 검증을 유지한다. global 모델/코어 계약/다른 서비스는 편집하지 않는다.
- 초기 웹 상태3개가 다른 컴포넌트에 잘못 선언돼19실패한 것을 올바른 scope로 옮겼다. optional React props 타입 지정 오류도 수정했다. 최종 WEB57 PASS/선택자료3 SKIP, safe-ci4 PASS, tsc/build PASS. 각 실패 receipt를 보존하며 검사 기준을 낮추지 않았다. native 추가 이후 backend 및 실제4슬롯 검증은 아직 진행 중이다.

## 실제 GPU4 병렬 완료 — 14:37 KST

- 배포 source `e4092eb25503a691e540fcea9224c5e85bf000bc`. 같은 Qwen27B manifest/GGUF와 기존 bundled llama-server로 전환하고 고정 CUDA backend SHA·GGML_BACKEND_PATH/LD_LIBRARY_PATH·명시적 CUDA0를 적용했다. GPU3 소유 PID1216649의 VRAM20,374MiB 적재와 실제 처리 중20,394MiB/4슬롯 동시 활성·GPU사용87%를 확인했다. GPU1 보호PID445778은 살아 있고 다른 프로세스/공간을 변경하지 않았다. 현재 native 로그는 전체 레이어 offload 숫자를 출력하지 않으므로 과거 Ollama의66/66 로그를 이번 근거로 재사용하지 않는다.
- 실제 공개 원문6(후기4/설명서2)·서로 다른 브라우저 세션4에서 동시에 POST했다. 14:34:13 시작, 14:36:02~44에 네 기획 모두 complete/콘셉트1/저장GET 일치. 서버 처리109.530/122.718/151.074/129.222초. native 원trace를 고정4run만 읽기 대조해 discover/plan/부분수리 총9콜 EOS·native alias/slot/Schema/실토큰을 확인했다. 슬롯은0~3 동시 활성이고 문맥16K씩 분리. 타 세션 job/run404·자료 GET200·목표/선택ID 분리 모두 확인했다. 구조적 완주이며 독립 의미 품질은 미승인이다.
- 실제 Chrome의 다섯 번째 요청은 대기순서1 표시 후 실행으로 전환됐고, 대기 중 ‘냄새’ 검색/원문 필터가 작동했다. POST 자동 재전송0. 대기·실행 상태와 복구 조회를 추가했으며 쿠키/브라우저별 독립 저장 경계는 유지한다.
- 전환 중 실제 사용자 요청1건(14:21:59~14:23:01)을 완료한 뒤 배포했고 사용자 중단0. model/web만 변경·터널 재시작0/동일 공유URL 유지. 세 서비스 active·Restart=always·RuntimeMaxUSec=infinity, native sleeping=false. 시간/유휴 종료를 설정하지 않았으며 장애·재부팅/tmpfs 재확보·Quick Tunnel 주소 변경의 기존 한계는 유지한다. 개발 Worker/예약 OFF다.
- 최종 backend88 PASS 및 규칙/계약/phase2/navigation PASS(실모델0·격리 Docker). WEB57 PASS/선택DATA3 SKIP·safe-ci4·tsc/build PASS의 고정 source5be와 배포 source의 apps/web/contracts byte diff0. 가짜 성공/검사 완화/지원 API 호출은 없다.
- 실패 보존: 초기 Ollama queue4지만 모델강제1, 첫 native CPU fallback에서4기획 모두300초 timeout/needs_sources/콘셉트0(원trace 독립 확인), 초기 WEB19 ReferenceError 및 TS2769 두 실패를 보존한다. CUDA 경로 누락을 수정한 뒤 위 GPU실제4 시험으로 재검증했다. 공개 API가 raw model_calls를 제거한다는 사실을 반영해 public 결과와 private metadata readback을 분리했다.
- 고정 상세는 [실행 증거 묶음](../../../../evals/pm-r9/20261008/parallel-four/serving-proof.json). 실제 배포 완료와 미병합 PR284·main eab85d4·CI/독립품질/부모 Done은 별개다. Actions 월5달러·보호 규칙을 유지한다. Figma0·새 합성리뷰0·새 유료모델API0.

14:40 KST 종료 확인: 다섯 번째 Chrome 요청도 기획 초안 complete/run-21d84422678346d8b6a630ec971f8672로 표시됐다. 대기14:34:45~14:36:02 후14:37:28 완료이며 POST 재접수0.14:40:35 읽기 확인에서 모델PID 동일·GPU3 20,396MiB 상주·is_sleeping=false·세 서비스active/NRestarts0/RuntimeMaxUSec=infinity, 종료예약 없음. 새 모델 호출 없이 확인했다.

독립 증빙 보완: 고정GPU4run의 registered R9 pack raw SHA fbc233a429c6ec1ceeb1571ce509ecad7d9494fe5388a0524fd3e64bfa0639ff, 선택6 source_facts/선택subset/정렬·사용자 선택목록 SHA 전부 기대값과 일치. 이 대조는 읽기 전용 metadata이고 원문/질문/owner 출력0·새 모델 호출0이다. Notion LG 페이지/대시보드에14:42 KST 실제4 배포 결과를 삽입했으며 새 본문 재조회와 PR284 공유를 종료 확인한다.
