# DATA #15 인수 준비·#16 운영 응답 대조

기준 main `9cd2d56be52588764c18c109c9ffca4c104bd48c`. 이번 사용자 지시에서 실행 가능한 자료 검수·소유 도구를 완성하고, 미게시 commit `66bd627be91e2438bb6a5c6413cece3f690d1049`의12개 파일을 원바이트 그대로 회수했다. 부모 Done·운영 배포·독립 평가 통과는 미완료다.

|범위|이번 실제 수행|남은 조건|
|---|---|---|
|#15|메타데이터23검사, private ZIP2개를 열지 않은 SHA 대조 PASS. 공개8입력 중복·independence=false 보존|PM 자료처분/교체·독립 검토자·승인 비공개 경로·실수신|
|#16·148|419개 메타데이터 대조 PASS. 새 GET3회는 로컬2연결 실패/공개health502|PM 운영팩·주제 승인 및 실제 운영 snapshot|
|운영 대조도구|현재 운영 project ID로 aggregate를 재계산, API/MCP·SQLite 저장/재개 snapshot·분모 전체 membership/원문·전페이지 비교|실운영 capture 미수신. match는 내용 정합만 의미|
|새 코드 검사|24 신규 회귀+기존 collector3+workspace22=49 PASS. 계약·지침·Ruff PASS. 빈 capture는 exit2/unconfirmed|GitHub CI·PM 검수/병합은 게시 뒤 확인|

[기존 미게시 실행 결과](../../data1516-followup/20261006T123152Z-01a10f51/README.md)는 소유 임시 서버에서 API75/MCP45·15query/15재개·12 status>=400 기록이다. 이번 새 runtime 횟수에 더하지 않는다. 개별12개 오류 payload가 저장되지 않았으므로 정확한4xx/오류코드까지 검증됐다고 주장하지 않는다. 기존 cleaning IDs/hash만으로 전체 분모 membership과 재개 후 원문까지 증명하지 않는다. 이번 [독립 메타데이터 검수](data16-audit.json)에 이 한계를 기록했다.

## 운영 대조 도구

입력은 PM이 승인 경로에서 확보한 실제 capture와 선택한 고정 dataset/annotation/date-source다. [템플릿](operating-snapshot-template.json)은 모두 null이며 운영 응답이 아니다. 한 query를 다음 필드로 수집한다.

- `project`: 실제 WorkspaceProjectSnapshot, `filters`: 실제 ReviewTrendRequest.
- `api_aggregate`, `mcp_aggregate`, `restart_aggregate`: 같은 query/운영 project에서 받은 원 aggregate.
- `stored_snapshot`, `restart_snapshot`: 각각 aggregate·metadata·memberships·evidence의 저장/재개 원본. API의 topic drilldown은 `__all__`을 제공하지 않으므로 전체 분모는 승인된 저장 snapshot으로 대조한다.
- `evidence_pages`: 요청 topic별 모든 실제 원문 페이지. offset/limit/total/next_offset·같은 project/aggregate·원문 전체 필드와 순서를 확인한다.
- 날짜가 구성된 팩에는 실제 date-source JSON 파일을 제공한다. 파일바이트 SHA와 canonical dataset/annotation SHA를 별도로 유지한다.

```text
python scripts/check_data005_operating_snapshot.py --snapshot PRIVATE_CAPTURE.json --dataset PINNED_DATASET.json --annotation PINNED_ANNOTATION.json --date-source PINNED_DATE_SOURCE.json
```

날짜가 전부 unknown인 원본 팩에서는 --date-source를 생략한다. 결과는 match(exit0)/mismatch(exit1)/unconfirmed(exit2)다. 누락을 빈 배열·0으로 채우지 않는다. 자기 선언 production_verified/PM approval을 신뢰하지 않으며 도구의 operating_origin_verified/PM_approval_verified는 항상 false다. 운영 출처/PM 승인 확인은 별도 인수 기록을 필요로 한다. 요청을 보내거나 서버·예약·모델·자료를 변경하지 않는다.

## 검수·실패·버전

[data15-audit.json](data15-audit.json)은 새23개 자료 검수와 기존156개 과거 검수를 구분한다. ZIP 항목·비공개 답안/원문을 열지 않았다. private 전달 manifest 현재 SHA는 미확인이다. CORE 의미 기준 수신은 사례 정답·독립성 승인과 다르다.

[소스 독립 검수](data16-tool-review.json)에서 빈 결과 페이지 중복 offset을 발견해 수정했다. [재검토](data16-tool-review-resolution.json)는 findings=[]이며 새 빈 페이지 회귀가 통과했다. 첫23개 검사 후 호스트 기록기의 raw bytes JSON 직렬화 실패, v2의 불필요 noqa3개 Ruff 실패를 원 로그로 보존했다. noqa 제거는 AST를 바꾸지 않았으며 [최종 코드 결속](final-code-binding.json)으로49개 검사 실행 source와 마지막 source를 연결한다. [v2](execution-checks-v2.json)·[v3](execution-checks-v3.json)에 명령·exit·이미지·실제 network-none/UID1000/readonly/zero-auth 경계가 있다. 처음23개와 최종24개를 합산하지 않는다.

[원 commit12파일 SHA](unpublished-original-manifest.json)·[최신 읽기 조회](fresh-operating-get.json)·[필요한 인계](PM-next-inputs.md)·[지시 관측](instruction-observation.json)을 보존했다. 원팩/기존 결과·개인/공용 README·공통 API/MCP·판단 코어·model client·운영 설정은 편집하지 않았다. 새 제품 모델/OCR 호출0이며 실제 고객 불만·시장 수요·효과를 이 합성 집계로 확정하지 않는다.
