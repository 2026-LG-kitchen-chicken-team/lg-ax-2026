# 날짜가 있는 별도 합성 동향 시연 자료

원 `data/demo/dataset.json`의 36개 합성 리뷰 문장을 새로운 `DEMO-TREND-*` review/evidence ID와 `PM-TREND-DEMO-REVIEWS-v1` 출처로 복사한 별도 자료다. 원 36개 리뷰·8열 CSV·DATA 후보 sidecar의 null 날짜는 변경하지 않았다. 제품/설명서도 합성 원자료를 재사용한다.

- dataset 버전: `pm-synthetic-trends.v1`. 원 자료의 `0.1.0`과 구분한다.
- 날짜: `date-schedule.json`의 명시적 demo 값이다. 5개는 null/unknown으로 유지하며 KST 연도 경계도 포함한다. sidecar 날짜 provenance의 SHA는 이 파일의 실제 원바이트 SHA다. 실제 고객 게시일이나 수요/계절성 근거가 아니다.
- 주제: PR176의 7개 언급 후보 매핑을 원 review ID로 조회하는 고정 rule이다. 후보 ID와 taxonomy 이름을 보존하며 감정 극성·불만률로 바꾸지 않는다. 날짜 시연은 리뷰별 주제 연결의 최종 의미 승인이 아니다.
- 날짜/원문/주제는 API/MCP 요청으로 제출하거나 승인할 수 없다. 서버 운영자가 아래 파일과 SHA를 명시한다. 원 자료와 시연 자료는 별도 작업실 DB를 사용한다.

날짜는 원 리뷰의 행 번호에 따른 6~12월 시연 배치이며 실제 게시 시점을 추정하지 않았다. 행 1·2는 10월 비교용, 행 9는 `2026-12-31T15:00:00Z`(KST 2027-01-01) 경계용이다. 행 6·10·20·30·36은 미상값 처리 시연을 위해 null로 두었다. 전체 36건 중 날짜 배정 31건·미상 5건이며, 기간·제품·출처 필터와 중복 제외 뒤의 고유 리뷰 수가 실제 각 집계의 분모다. FRIDGE-A의 2026년 10월 시연은 분모 3·청소 관련 언급 1이다. 이 숫자는 고객 불만·수요·계절성의 측정값이 아니다.

| 후보 topic ID | 일반 언급 범위 |
|---|---|
| `cleaning` | 청소 관련(긍정·불편 모두 포함) |
| `temporary_storage` | 임시 보관 관련 |
| `food_findability` | 식품 위치 확인 관련 |
| `manual_guidance` | 설명·조작 안내 관련 |
| `dish_loading_guidance` | 식기 배치 안내 관련 |
| `rotating_arm_clearance` | 회전 날개 간섭·여유 관련 |
| `heating_preset_management` | 가열 설정 저장·재사용 관련 |

분류 후보의 기술 연결과 “주제 언급 비율” 표시를 검토하는 범위이며, 향후 실고객 자료를 사용할 때의 날짜 확인이나 리뷰별 감정 극성·분류 정확도 승인과 구분한다.

## 파일 고정값

| 파일 | SHA256 |
|---|---|
| 원 dataset bytes | `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0` |
| 원 DATA candidate bytes | `0b3d75727a6c5c33379672494bbed6e0e729f80b441c23197889ea275d801117` |
| [dataset.json](dataset.json) bytes | `a2c9c260316c1e8067531e7ba9e42ffec5338363f782092fea0f5cf1449d2b89` |
| dataset canonical | `6c8767513709f2a4a745c6dd8e43061af1be541887f8cd2bca1ab4a40db187f1` |
| [annotation.candidate.json](annotation.candidate.json) bytes | `101b0560337fbbb61f1b4117e2ef47562aacae458d0db5a044c5e36ae2ea1d79` |
| annotation canonical | `6a23e26343802dc2b4495e8da1e3efc6ffa9ac03cab3a0ed98bee1abc479093a` |
| [date-schedule.json](date-schedule.json) bytes | `7d528dfc50b8e0474b455327852e363d52603fe5fab0270c75dad9f4430d1f70` |

## 명시적 운영 연결

기존의 승인된 본인 작업실 토큰 파일을 사용한다. 이 문서는 토큰 발급·모델 실행·서비스 배포·자동화 ON 지시가 아니다. 서버 측 파일 선택만 추가하며 기본 실행은 collector 미연결 501을 유지한다.

```powershell
python -m lgax_api.server --dataset data/demo/review-trends-dated/dataset.json
python -m lgax_api.workspace_server --db <별도_시연_DB> --credentials <본인_승인_토큰파일> --dataset data/demo/review-trends-dated/dataset.json --trend-metadata data/demo/review-trends-dated/annotation.candidate.json --trend-metadata-sha256 101b0560337fbbb61f1b4117e2ef47562aacae458d0db5a044c5e36ae2ea1d79 --allow-candidate-trend-metadata
```

기존 private MCP는 위 작업실 API URL을 그대로 proxy한다. 모델 호출 옵션은 켜지 않는다. 웹 bootstrap과 작업실 API는 같은 dataset 파일을 선택해야 한다. 원 작업실 DB에 다른 dataset을 덮어 연결하지 않는다. 새 기획 요청의 `dataset_version`은 `pm-synthetic-trends.v1`, 문서 버전은 선택한 제품의 기존 합성 `1.0`이다.

고정된 원 DATA candidate를 미리 볼 때는 별도 DB에서 원 dataset `0.1.0`과 원 candidate 파일/SHA를 선택한다. 원 36개 날짜가 없어 FRIDGE-A 범위10개는 undated10·분모0·ratio=null인 빈 결과가 맞다. candidate preview 플래그는 실제 고객 자료나 리뷰별 주제 분류를 승인하는 권한이 아니다.

실제 고립 HTTP/MCP·재시작·원3PDF 등록 검증과 실패/한계는 [PM 연결 검증](../../../evals/pm-data-integration/20261006/README.md) 및 그 실행별 raw SHA 수신증을 따른다. 운영 적용·브라우저 UI·외부 계정 MCP·실모델 품질은 이 자료팩의 작성만으로 완료되지 않는다.
