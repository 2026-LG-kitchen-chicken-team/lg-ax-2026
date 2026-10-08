# R9 소비 인수·원문 경계 검수

신진하 / ginaginaring · `DATA-R9-CONSUMER-01a114f6` · 2026-10-08 KST.

시작 main `dc0ccc05916c637b2e0c2cc268a061dfa655c0b7`, PR262 최종 head `a6da6784db60e99645fd57017d37ba1403af9cd1`/CI4 성공·병합을 인수했다. 공통 계약·생산 코드·자료·공유 README는 수정하지 않았다.

## 완료한 작은 단위

- PM009/E056의 **최신 정상·조건 변경2실행**을 기존 semantic-review.json의5실험과 분리해 인수표를 만들었다. 최신 run은 `run-1f83d846191941aea21153897b944ec1`과 `run-754268c6b0cb41bba50c5b8d713332d9`다. 실제 원출력/실행 code·loaded SHA·모델 digest/usage/같은 HTTP-MCP 쌍은 미수신이다.
- 기존 PM16 findings를 원 JSON pointer와 해시로 재사용했다. 옛 정상·revision 오독, 선택 실험의 주체/청소 실패 암시, 지침 echo, truncation을 최신2실행의 새 오류나 해결로 판정하지 않았다.
- 위 findings의 원문 경계를 위한 **개발 후기4·공식 p49 발췌2, 인용14개**를 원 ID·Unicode `[start,end)`·텍스트SHA·판본·locator에 연결했다. 이6개는 inherited findings의 참고 source이며 최신 실제 selected membership 수신을 뜻하지 않는다.
- selected 참고6 Source는 PR254와 R9에서 객체 전체가 같다. 원 PDF SHA·native2발췌·p49 이미지의 조건표를 대조했다. 배우자/구매자, 구매 기대/실사용 성과, 시간순서, 혼합 문구, 설치기사 의도의 고객 인식, 공용 설명서 적용 미확인을 보존했다.
- #14 기존5셀 sidecar와 실제 CORE 수동 읽기 회신은 재사용했다. sidecar의 과거 ACK pending 문구는 원파일에 보존하고 최신 인증된 수신 링크로 범위를 분리했다. **자동 graph/adapter 수신·자동 정확도·실제 운영 소비는 미확인**이다.
- #15의 기존 발신 검사는 재실행하지 않았다. 실제 CORE 회신의 수신0(2026-10-07T16:44:02Z)과 기대 ZIP 11,106bytes/11entries를 분리했다. **발신 SHA를 수신 SHA로 복사하지 않았다.** 승인 전송·Gold·채점자·동일입력 원출력이 미수신이다.
- 작업 중 병합된 PR265/main `36bd1c5e60d220baebba9f7d76de6cba05cf2627`의 실제 CORE metadata를 추가 인수했다. 같은6 source ID/본문SHA/판본과 기존5run의 선언SHA가 일치했다. 이 CORE manifest에는 최신2run이 없으며 full raw/동일 HTTP-MCP 미수신을 명시한다. 참고5 안내서 ZIP은 다른 사용자 창이 이미 인수 중이므로 중복하지 않았다.

## 주요 파일

| 파일 | 읽을 내용 |
| --- | --- |
| [source-boundaries.json](source-boundaries.json) | 참고6 Source·14원인용·주체/시점/양면/문서 적용 경계. 승인 annotation/Gold/자동 추출 아님 |
| [pm-findings-reuse.json](pm-findings-reuse.json) | 기존5실험16 findings의 원 pointer. 최신 run으로 자동 승계하지 않음 |
| [intake-status.json](intake-status.json) | 기존5 + 최신2 보고와 실제 수신을 구분. 원출력·자동표·ZIP actual 값은 null/false |
| [recipient-references.json](recipient-references.json) | GitHub에서 실제 읽은 기존 CORE 회신의 author·시각·body SHA·URL. 새 회신 아님 |
| [core265-intake.json](core265-intake.json) | 새 CORE265 metadata의 실제 수신·6 source/5이전run 대조. 최신2 원출력과 구분 |
| [handoff-request.md](handoff-request.md) | PM/CORE가 기존 결과로 제공할 최소 인계 단위와 인수 조건 |
| [verification.json](verification.json) |12입력 pin·참고6객체·14인용·완료 승격 거절6개. 모델 품질 검사가 아님 |
| [input-pins.json](input-pins.json) | 고정 Git blob11개와 현재 DATA authored spec1개를 구분한 byte/SHA/출처 |
| [artifact-manifest.json](artifact-manifest.json) | 이 폴더의 최종 파일 SHA·byte 크기. manifest 자기 해시는 제외 |

## 자기 검수와 재현

실행코드 [verify_consumer_handoff.py](verify_consumer_handoff.py)는 stdlib만 사용하며 제품 모듈을 import하지 않는다. fixed Git blob의 raw bytes를 별도 입력 폴더에 옮겨 아래처럼 승인된 기존 image에서 실행했다. [실제 invocation](history/invocation-1.json), [원 로그](history/check-1.log), [exit0](history/result-1.json)을 보존했다.

```text
docker run --rm --network none --read-only --user 65534:65534
  --cap-drop ALL --security-opt no-new-privileges
  --mount type=bind,source=<fixed-input-copy>,target=/inputs,readonly
  --mount type=bind,source=<checker-copy>,target=/work,readonly
  --mount type=bind,source=<new-output-dir>,target=/out
  --workdir /work
  sha256:d2b9d2d0d1da29f3226a8293340d63f58877a03b7189d3982123ff6995e8e01c
  python -I -S -B verify_consumer_handoff.py --inputs /inputs --out /out
```

입력/root 쓰기 거절·UID65534 확인, network none, 인증/Gold/private 원입력 mount0. 6개 probe는 받은 적 없는 출력/자동 정확도/ZIP 수신 SHA/평가점수/부모Done이나 서로 다른 조건의 A/B 승격을 거절하는 **metadata-only protocol 검사**다. 새 모델/OCR/기존225검색·50ZIP검사·생산자 감사·서비스 재시작0이다.

추가 CORE265 인수는 [verify_core265_delta.py](verify_core265_delta.py)로 새 metadata만 대조했고 기존 검사를 반복하지 않았다. [별도 실행](history/invocation-core265.json)/[exit0 로그](history/core265.log)를 보존했다. Windows가 기록한 첫 stdout/invocation/exit 원본은 scratch에 그대로 있고 게시 사본만 Git 속성에 맞춰 LF로 정규화했다. [원본 해시와 위치](history/capture-line-endings.json)에서 구분한다.

## 한계·다음 실제 인수

실행 report 파일의 첫 scope 문구는 retained2를 설명하지만 배열은5실험이고, 최신2는 별도 PM009/E056에만 있다. 이 차이를 원문 보존한 채 인수표에서 구분했다. 최신2의 raw JSON을 받으면 SHA/원facts/실제 선택목록/부모 brief·조건을 검증한 뒤 **새로 바뀐 필드만** 원문에 대조한다. 공개 report 인용을 모델 원응답으로 바꾸지 않는다. 정상과 revision은 조건이 달라 순수 통제 A/B가 아니다.

보고된 `complete`는 생성 흐름 상태다. 원 facts 보존·파일 무결성·지침 변경·CI·병합이 의미품질/분류 승인/독립평가/전체 부모Done을 대신하지 않는다. 출력 truncation의 설정4096을 실제 토큰 사용량으로 계산하지 않는다. 승인 없는 기간/시장 비율·임의 진단/회복·구매 SKU/구매시점판을 추가하지 않는다.

Refs #14, #15, #234, PR257, PR258, PR262. 전체 R9 자료·운영 감사와 추가 설명서/게시일 수집은 다른 사용자 창의 범위를 유지한다.
