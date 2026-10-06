# 운영 자료 일치 여부 — 읽기 조회 결과

**판정: 미확인.** 2026-10-06 20:50 KST의 기존 주소 GET 6건에서 운영 자료 응답을 확보하지 못했다. 연결 실패를 자료 불일치나 서버 OFF로 단정하지 않는다. PR183 기준 자료와 고정 main의 7개 자료 파일은 Git 원바이트가 일치한다.

| 기준 자료 묶음 | 자료집 버전 | 모델 / 리뷰 / 근거 | PR183 ↔ 고정 main | 공개 API의 실제 값 | 작업실의 실제 값 | 운영 일치 |
|---|---|---|---|---|---|---|
| 원 날짜 미상 합성 개발 예시 | `0.1.0` | 5 / 36 / 42 | 일치 | 미확인 | 미확인 | 미확인 |
| LG 공식 설명서 원문 범위 | `lg-manual-scope-20261006.3-pm-intake` | 3 / 0 / 21 | 일치 | 미확인 | 미확인 | 미확인 |
| DATA 별도 구성 날짜 시연 | `synthetic-dated-demo.20261006.v1` | 5 / 36 / 42 | 일치 | 미확인 | 미확인 | 미확인 |

위 건수는 서로 독립인 자료 버전의 크기다. 합성 리뷰36건을 두 번 합산해 고유 리뷰72건으로 보고하지 않는다. LG 설명서 묶음의 실제 고객 리뷰는0이며, 다른 기존 PDP 리뷰 자료팩의 전체 확보량을 뜻하지 않는다. 날짜 시연에는 구성 날짜9/미상27이 있고 원래 리뷰의 날짜를 실제 고객 날짜로 채운 것이 아니다.

| 확인 축 | 기준 자료에서 확보한 값 | 운영에서 확인한 값 |
|---|---|---|
| 자료집 버전 | 위 3개 버전, 파일 SHA·canonical SHA 별도 | 미확인 |
| source ID·자료 ID | 177개 메타데이터 행(근거105/리뷰72), 자료 묶음별 분리 | 미확인 |
| 제품 모델 | 합성5개, LG `T876MEE1H1`·`DUE6BGL2E`·`MW23FDI` | 미확인 |
| 문서 버전 | 합성의 원래 행별 버전(제품 기본값과 다른 행도 보존); LG 개정은 아래 표 | 미확인 |
| 원문 위치·해시 | locator·JSON pointer·정규화하지 않은 text UTF-8 SHA | 미확인 |
| 실제/합성·자료 범위 | `public` LG 설명서와 `synthetic` 개발/날짜 시연 분리 | 미확인 |

| LG 모델 | 문서 개정 | 원 PDF의 선언된 SHA256 | 설명서 근거수 |
|---|---|---|---|
| `T876MEE1H1` | `MFL71401557 Rev.00_032526` | `d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815` | 8 |
| `DUE6BGL2E` | `MFL71959117 Rev.07_030626` | `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5` | 7 |
| `MW23FDI` | `MFL68822538 Rev.00_120925` | `3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc` | 6 |

PDF 원문은 이번에 다운로드·재해시하지 않았다. 위 값은 PR183의 승인 계획에 기록된 원 PDF pin이다. 근거별 text SHA는 이번에 Git 원문에서 직접 재계산했다. 공용 설명서 연결은 모든 선택 기능의 SKU 적용 확정이 아니며 [별도 SKU 확인 PR187](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/187)의 미확인4건을 유지한다.

## 조회 증거와 제한

| 요청 | 승인 문서의 주소 | 결과 | 확인 시각(KST) |
|---|---|---|---|
| Q001 GET | `http://127.0.0.1:18867/health` | URLError; HTTP 응답 없음(세부 사유 미기록) | 2026-10-06T20:50:01.969037+09:00 |
| Q002 GET | `http://127.0.0.1:18867/api/bootstrap` | URLError; HTTP 응답 없음(세부 사유 미기록) | 2026-10-06T20:50:04.007984+09:00 |
| Q003 GET | `http://127.0.0.1:18867/api/products` | URLError; HTTP 응답 없음(세부 사유 미기록) | 2026-10-06T20:50:06.019437+09:00 |
| Q004 GET | `http://127.0.0.1:18869/health` | URLError; HTTP 응답 없음(세부 사유 미기록) | 2026-10-06T20:50:08.025640+09:00 |
| Q005 GET | `http://127.0.0.1:18869/api/workspace/projects` | URLError; HTTP 응답 없음(세부 사유 미기록) | 2026-10-06T20:50:10.067053+09:00 |
| Q006 GET | `https://eryang-lab.tailb7c3c1.ts.net/lg-ax/health` | HTTP502 | 2026-10-06T20:50:12.101764+09:00 |

- 공개 외부 주소는 **MCP** 주소다. 외부 공개 REST API나 외부 작업실 주소를 추정하지 않았다. MCP health 실패만으로 REST API의 데이터나 버전을 판단하지 않는다.
- 현재 본인 작업실 client/주소를 확보하지 못했다. controller 자격증명·옛 테스트용 workspace 자격증명을 전용하지 않았고 요청 토큰은0건이다. 인증된 작업실 조회·프로젝트 ID·dataset SHA·실제 원문 조회는 미실행이다.
- 코드의 공개 API 기본 자료는 합성 예시이며 작업실은 승인 자료를 주입할 수 있다. 따라서 공개/비공개의 **전체 자료 범위가 동일해야 정상이라는 조건을 만들지 않는다**. 연결 복구 뒤 공통 허용 범위의 동일 ID/모델/버전/해시와 비공개 전용 범위의 노출 경계를 비교해야 한다.
- 기존 합성 자료의 제품 기본 문서 버전과 다른 행은 버전 필터 회귀용 입력일 수 있다. 원문을 바꾸거나 불일치 오류로 단정하지 않고 `version_differs_from_product_default_records`에 ID와 행별 버전을 보존했다.
- `GET /api/workspace/projects/{id}/review-trends`는 코드상 새 집계를 저장할 수 있어 호출하지 않았다. 재조회에는 이미 존재하는 aggregate ID의 읽기 경로만 사용한다. 새 프로젝트/집계/문서/모델 실행을 만들지 않는다.
- 배포·재시작·설정/인증 변경·예약 조작·모델 호출0. 실제 운영 결과가 없으므로 새 등록→파싱→조회 전체 성공이나 #13/#16 Done을 주장하지 않는다. PR183의 기존46 HTTP 요청은 과거 loopback 검증이며 이번 운영 요청과 분리했다.

## 파일과 재확인 방법

- [expected-inventory.json](expected-inventory.json): 3묶음의 모델/ID/source ID/버전/위치/text SHA, 원문을 포함하지 않는 기준 목록.
- [source-comparison.csv](source-comparison.csv): 기준177행과 공개 API·작업실의 미확인 상태. 제품 모델별 필터로 확인한다.
- [query-evidence.json](query-evidence.json): GET6건의 주소·시각·HTTP 상태·제약.
- [verification.json](verification.json): 실제 정적 대조·파일 해시·코드/자료 버전·미실행 범위.
- [remaining-pm-work.md](remaining-pm-work.md): 최신 PM R4와 각 담당의 남은 행동.

자료 기준 PR183 head `8fbe6ded37f7e515ce66c24d3dc8558f8281a9fc`, 비교 고정 main `b160c18a643c362dcf3923ac49742a05f7bb537d`. 제출 commit은 이 폴더와 같은 PR의 HEAD다. JSON의 text SHA는 해당 고정 commit의 `reference_path`/`reference_json_pointer`에서 text를 읽어 UTF-8로 그대로 인코딩해 재계산한다. 파일 SHA·원 PDF SHA·text SHA·canonical 자료 SHA는 서로 비교하지 않는다.

현재 다음 하나는 **PM이 승인된 운영 읽기 주소와 본인 viewer 연결 또는 비밀 없는 버전/해시 응답을 인계하는 것**이다. 인계 후 같은 기준 목록에 실제 응답을 연결하고 일치/불일치를 판정한다. 사용자가 주소를 모른다고 답했으므로 추가 주소 질문을 반복하지 않는다.

추가 기록(2026-10-06T21:13:31.164759+09:00): 제출 branch는 최신 main `9d7c896e2cea62914ceeb3b957e3a535ccc4d47f`를 병합했다. 기존 R4/계획보호 PR194·189 병합을 남은 작업 표에 갱신했다. 기준7자료 바이트는 여전히 동일하며 기존 GET6건을 새로 실행한 것으로 바꾸지 않았다.
