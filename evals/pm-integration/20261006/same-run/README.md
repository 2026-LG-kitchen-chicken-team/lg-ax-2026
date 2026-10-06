# PM 독립 검증 — 원 실패·보류의 같은 run 소비

2026-10-06 수동 PM 인수 작업의 소비 경로 검사다. 자동화 OFF를 유지한다.

## 확인한 범위

고정된 실제 모델 과거 기록 3건을 새 임시 작업실에 **재생**했다. 새 모델은 실행하지 않았다.
각 기록의 원입력과 전체 실행 결과를 보존하며 실제 loopback HTTP 서버에 저장한 뒤, HTTP와 실제 stdio MCP로 같은 project/run ID를 조회했다.
27B 냉장고의 `held` 1건과 8B 냉장고·전자레인지의 `failed` 2건은 모두 후보 0개로 유지됐다.

이는 실패·보류가 소비 단계에서 성공으로 바뀌지 않는지 확인한 결과다. 정상 결과·사용자 변경·적절한 보류의 의미 품질, 브라우저, 실제 운영 서버, 새 추론의 완료 증거는 아니다.

## 재실행

제품 코드는 자격증명이 없는 고정 Docker 실행 환경 안에서만 실행했다. 사용한 이미지·권한 경계·source archive 해시는 [validation.json](validation.json)에 있다.
실행 시 `/workspace`는 read-only, root filesystem은 read-only, network는 none이며 게시 자격증명과 AI profile은 마운트하지 않는다. 임시 작업실 토큰은 guest 안에서 생성하고 임시 SQLite와 함께 종료 시 폐기한다.

컨테이너 내부 명령:

```text
python evals/pm-integration/20261006/same-run/consume_recorded_runs.py --out /artifacts/consumption
```

원입력 manifest의 파일별 해시를 먼저 확인한다. 제품 모듈이 필요한 명령이므로 게시·개인 자격증명이 있는 호스트에서 실행하지 않는다.

## 출처와 결과

- [input-manifest.json](input-manifest.json): 원 모델 실행별 고정 commit, 결과 파일 SHA256와 데이터 SHA256. 역사상 모델 호출과 이번 신규 호출을 구분한다.
- [consumption-summary.json](consumption-summary.json): 실제 guest 실행에서 나온 상태·같은 ID·호출 수·한계. `status=pass`는 소비 경로의 결과이고 품질 성공은 아니다.
- [validation.json](validation.json): consumer commit `e2ed53d39affc1a286cd60aab6a41942ac93445e`, fixed supervisor source-proof 및 실행 경계, source 변경 없음, exit 0, artifact 해시.

HTTP/MCP 전체 readback은 각각 2,456,458 bytes이며 동일한 SHA256 `2331bf1c8b3a51bfc743d95a1ce0fb7d60e5ea1066054ab2d57d6e230a3f9a7e`다. 원 실행을 반복 포함하므로 저장소에는 중복하지 않는다. PM 비공개 실행 receipt가 guest 산출물 위치를 연결하며, 재실행하면 임시 run/project ID가 달라진다. 두 소비 결과의 내용·ID가 서로 일치해야 한다.

## 남은 검증

새 코어 정상·변경·보류 결과와 DATA collector의 집계 ID가 인계되면 같은 원본을 HTTP·MCP·브라우저에서 소비한다. 역사 재생과 새 모델 실행을 분리하고, 동향은 주제 언급 비율이며 감정·불편 비율이 아님을 유지한다. 다른 담당자의 작업·기록·운영 서비스를 이번 프로브에서 변경하지 않았다.
