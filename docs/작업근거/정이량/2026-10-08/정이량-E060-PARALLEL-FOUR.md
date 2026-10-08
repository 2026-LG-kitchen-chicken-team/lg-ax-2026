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
