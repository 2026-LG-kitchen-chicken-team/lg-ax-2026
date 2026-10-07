# WEB O-R8-2 후기 document_version 독립 대조

기록 ID `DATA-WEB-VERSION-01a1100e`. 2026-10-07 착수, 최종 ID·URL·basis 보강 대조 2026-10-08 00:07:24 KST.

- 요청: [WEB O-R8-2](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/6#issuecomment-6039996324).
- 소비 main: `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`.
- PM producer: `5fdb3ad55349726fbe03c9f69651f895d73e8f10` ([PR245](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245)).

## 확인한 의미

후기 `document_version`은 **그 후기가 실린 페이지 모델에 연결한 참고자료 버전**이다. 후기 본문 자체의 판본, 실제 구매 모델, 구매 당시 적용 설명서를 확인한 값이 아니다.

1. `public_review_collection.py` 199~200행은 제품 카탈로그의 `manual_version`과 `document_version`을 후기 record로 복사한다. 제품18개 카탈로그의 `document_version_basis`는 기존 설명서판 또는 공식 제품 페이지 스냅샷을 구분한다.
2. `build_research_bundle.py` 115행은 record에 `document_version` 키가 있으면 그 값을 보존하고, 키가 없으면 `manual_version`을 사용한다. 추가 원문59건에는 이 키가 없어서 관련 설명서값을 상속한다. 현재 개발141건 중36건이 이 fallback 경로다.
3. R8은 `manual_time_alignment=current_reference_only_not_purchase_time_verified`와 `purchased_model=null`을 유지한다. 이번 감사도 구매 모델·구매 당시 설명서 확인 건수는0이다.
4. ResearchSource 계약은 nullable string의 형태만 정의한다. WEB의 공통 '문서판' 문구로는 참고 설명서판과 제품 페이지 스냅샷의 성격을 충분히 구분하지 못한다.

## 실제 개발 후기141건

| 제품군 | 참고 설명서판 | 제품 페이지 스냅샷 | 합계 |
|---|---:|---:|---:|
| 냉장고 | 20 | 28 | 48 |
| 식기세척기 | 16 | 32 | 48 |
| 전자레인지 | 15 | 30 | 45 |
| 전체 | **51** | **90** | **141** |

같은 개발 후기가 기본3묶음, 공식확장3묶음, 냉장고 경쟁자료1묶음에 나타나는 **330개 위치**를 대조했다. 이를330개의 독립 후기로 세지 않았다. 같은 ID의 원문·SHA·페이지 모델·버전·미확인 보존은 모두 일치했다. `source_id=LGE-R8-REVIEW-{original_review_id}`, locator의 원 ID, 원문 URL과 카탈로그 basis도 확인했다. 상세141행은 [review-version-lineage.csv](review-version-lineage.csv), 위치330행은 [bundle-version-lineage.csv](bundle-version-lineage.csv)를 따른다.

## WEB 인계 문구와 PM 결정

- 설명서 참고값: **페이지 모델의 참고 설명서 판**.
- 제품 페이지 값: **페이지 모델의 제품 페이지 스냅샷**.
- 종류를 구분할 metadata가 없는 후기의 안전한 공통 문구: **페이지 모델의 연결 참고자료 버전**.
- 공통 보조문구: **후기 판본·구매 모델·구매 당시 설명서 판 확인 아님**.

DATA는 현재 고정 값의 생성 경로를 확인해 이 의미와 문구를 추천한다. 정식 계약 의미 및 `document_version_basis` 전달 방식은 PM, WEB 표시 수정은 WEB 담당 범위다. prefix만으로 미래의 임의 버전을 공식 설명서로 확정하지 않는다. 기존 값·본문·schema·생산 파일을 여기서 변경하지 않는다.

## 근거와 재현

- [audit-result.json](audit-result.json): 메타데이터 일치, 표시 의미의 주의점, 한계·비실행 값.
- [source-pins.json](source-pins.json), [producer-main-source-byte-bridge.csv](producer-main-source-byte-bridge.csv): producer/main/소비 checkout의 관련19파일 원바이트·SHA 동일.
- [audit_versions.py](audit_versions.py): stdlib로 고정 JSON/Git objects를 읽는 독립 비교기. 생산 helper·모델·서비스를 import하지 않는다.
- 실행 명령: `python -X utf8 evals/data-web-version-audit/20261007-01a1100e/audit_versions.py`. source `ef29aa8`의 새 worktree에서만 실행하며 원 source JSON을 다시 생성하지 않는다.
- 검사 전후 기존 tracked **4,232파일 SHA256 보존**, 기존 코드·원자료·개인 README 수정0.
- 새 모델/OCR/수집/운영HTTP·DB생성·재시작0. D4 독립성·표본/분할 감사, 실제 WEB 화면 수정·다운로드, 새 운영 DB/API 인수·모델 의미품질의 통과 근거는 아니다.
