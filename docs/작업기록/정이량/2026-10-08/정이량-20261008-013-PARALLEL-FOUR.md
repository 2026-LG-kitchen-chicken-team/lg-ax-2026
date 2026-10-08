# 정이량-20261008-013-PARALLEL-FOUR

KST 2026-10-08. 최신 직접 사용자 지시: “LLM이 동시에 4명다 요청 처리하게 바꿔”. 이전 다른 채팅의 순차 대기열 제안보다 실제 모델 병렬4를 우선한다. 기존 프로토타입 source0541/기록02ba991·PR284에서 이어 하며 완료한 기능을 새로 만들지 않는다.

편집 배정: PM root는 전용 모델 서빙 환경/격리검사/원격배포/실모델/기록, core_audit는 gateway durable job 및 기존테스트, remote_audit는 웹client/상태/poll/복구와UI테스트, remaining_and_data는 독립 큐 새테스트만 수행한다. 실제 사람이 직접 지시한 현재 AI 협업이며 개발 자동Worker/예약은OFF다.

GPU3 모델27B가 올라간 상태의 여유24,204MiB·GPU1/Naru 및 타GPU 프로세스 보존을 읽기 확인했다. 최신 사용자 실제 기획은완료된 뒤 배포한다. 기존HTTP는graceful drain하고소유web/model만개정하며tunnel은재시작하지않아주소를유지한다. 병렬4/context16384와token4096/pinned model/store/binary/keep_alive=-1 유지. 단일모델콜timeout은4병렬지연에맞춰기존ModelConfig상한내300초로서빙에만적용한다.

새게이트웨이는최대4실행/활동8접수/초과FIFO대기·세션활동1·소유자조회·input/owner/result SQLite보존을구현한다. HTTP202접수후GET상태를조회하며POST재전송없음. 원문GET/검색은계속사용한다. 모델병렬권고는[Ollama 공식FAQ](https://docs.ollama.com/faq)의VRAM/context증가조건과대조하며환경변수4만으로실제성공을주장하지않는다.

검사/배포/4독립세션실모델응답·기존서빙유지·의미품질제한은실제고정근거로완료보완한다. 새합성리뷰/Figma/새유료모델API0·CI상한/보호검사변경0. 실제모델동시처리와독립의미품질/전체Done은구분한다.
