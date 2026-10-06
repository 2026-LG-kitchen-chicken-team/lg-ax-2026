# OCR 원본 검수 상세 기록 — 신진하-20261006-OCR-01a10f51

- 직접 사용자 요청: #14 남은 OCR 표·숫자·단위·각주를 기존ledger/plan과 원 PDF로 검수하고 새 작업공간/고유폴더를 사용하며 기존 코드·자료·개인README를 수정하지 말 것. 모델/OCR 재실행 없이 결과·미확인과 PR 게시 요청.
- 해석: 기존70회 결과의 원문/행·열·모델 조건을 수동 대조한다. 모델/OCR0, 새자동표 정확도null, 소비코드/기존gold와개인README 불변이다. 최신 직접 지시 때문에 기존README 갱신 규칙은 이번 작업에 적용하지 않았다.
- 작업 공간: 별도 Git worktree/branch `codex/data003-ocr-review-20261006T111943Z-01a10f51`; app managed 생성은root origin/main ref 부재로 실패해 실제 프로젝트 Git으로 새 checkout을 만들었다. 기존 checkout은 손대지 않았다.
- 기준: main `a3452a29180f7996a06ca141d9c416a31513587c`; 원 ledger/plan/corpus6파일과 PDF3개를 SHA 대조/동결했다. 과거crop manifest는 preserved publication의 SHA64d3844...와 각 ledger bbox를 일치 확인했다.
- 실제 작업: 표지·관련6쪽 전체를 Poppler로 렌더/시각 확인했고 원14 bbox를 원 PDF에서600dpi로 재렌더하여 확인했다. 식기 표지의 문서번호를 상세 렌더로 확인했다. 새OCR/model import/호출·자동화/예약 변경은 없다.
- 발견: 공백5·각주 기호1, Max/각주 index/물리량·mm머리글·병합셀·같은값 다른열·현재 인용ID 맥락을 기록했다. 정확 source14/plan3 확인과 자동레이아웃미측정을 구분했다. 기존숫자/단위성적을 새성능으로 쓰지 않았다.
- 초기 도구 실패: crop manifest가 published prepared/historical에 없어 FileNotFound를 보존했다. 기존private-preserved 입력경로와 승인SHA로 읽어 모델/OCR 재실행 없이 복구했다.
- 소통/출처: 본인 GitHub ginaginaring/Issue14·최근댓글·열린자기PR을 실제 읽었고 관련Gmail을읽기전용검색했다. 주소/접속값은공개문서에옮기지 않았다. 새PR은 완료조건중부분검수이며 #14Done/PM승인은별도다.
- 산출물: 새folder `evals/data003-ocr-review/20261006T111943Z-01a10f51`만 추가한다. 기존source/ledger/plan/README들의 byte보존 및변경경로검사는별도JSON이다.
- 남은 일: 자동구조화표 결과/소비경로의단위·모델열·조건대조, T876정확유형/구성품, 출처차이처분, PM검수·최종인수. 사용자새설치/모델선정/로그인필요없음. 이번지시의PR게시까지진행하며 병합/Done은수행하지 않는다.
