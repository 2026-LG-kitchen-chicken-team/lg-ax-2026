# DATA14-AUTO-TABLE-AUDIT-01a1100e 근거

## 불변 입력과 검수 대상

- source commit `9cd2d56be52588764c18c109c9ffca4c104bd48c`; 파일 SHA/Git blob은 [source-manifest.json](source-manifest.json).
- 보관 OCR: `evals/data003-live/20261005/ocr-v3/results.json`; 같은 bytes를 PR191 `inputs/results.json`에서도 확인.
- ledger/plan: `evals/data003-compare/20261006-01a10834/prepared/`의 원파일과 PR191 보관 사본.
- PR191 head `21d5aaecf77ffe343d293be0f51f42fa8dba33bb`; [PM 검수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/191#issuecomment-6015688103).
- PR193 head `7be3a7bb27d93ffe50a64b0115ee5014518b2612`; [PM 검수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/193#issuecomment-6015787482).
- 당시 status/head/merge 정보와 위 댓글은 [github-sources.json](github-sources.json)에 보관했다. 수동 검수 인수와 자동 레이아웃 성공을 구분한다.

## 원본 PDF

| 모델 | 문서 개정 | 원본 SHA-256 | 직접 본 물리 페이지 |
| --- | --- | --- | --- |
| T876MEE1H1 | MFL71401557 Rev.00_032526 | `d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815` | 1,19,22 |
| DUE6BGL2E | MFL71959117 Rev.07_030626 | `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5` | 1,23,57 |
| MW23FDI | MFL68822538 Rev.00_120925 | `3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc` | 1,17,37 |

새 page/region 렌더 manifest는 원본 SHA·페이지·좌표·렌더러·DPI·새 raster SHA를 연결한다. historical crop SHA와 새 렌더 SHA를 다른 필드로 보관했다. PDF native text층은 `native-source-text/`에 보관하며 구조 결론은 직접 본 PDF 레이아웃을 근거로 한다.

## 검수표의 단위와 한계

- [recognition-review.csv](recognition-review.csv): 기존14영역의 source gold/저장 OCR·문자/숫자/단위·JSON pointer·manual bbox.
- [manual-reference-review.csv](manual-reference-review.csv): PR19119 + PR19322행을 PR/원 ID별로 대조. 중복 사례는 합치거나 성능 표본으로 더하지 않음.
- [link-review.csv](link-review.csv): 24참조 × 6연결 = 144검수 질문. manual reference/자동 observed null/검증 불가/사유가 별도 열.
- [plan-review.csv](plan-review.csv): 계획3건의 원문 기대값 일치와 6종 자동 연결 검증 불가.
- [processing-path-inventory.json](processing-path-inventory.json): saved JSON 키·현재 고정 source 코드/SHA/행 번호. 과거70회 runner와 합성2문장 smoke 코드도 구분.
- [findings.json](findings.json): 확정 문자/평가 오류와 출력 부재·적용성 미확인·historical PNG 부재.
- [verification.json](verification.json): 실제 read-only 일관성/보존 확인. 새 모델/OCR·생산경로 실행·저장소/운영 시험은0.

## 재검산 명령

기존 producer를 실행하는 명령이 아니다. 별도 작업 폴더에서 PDF 라이브러리가 있는 Python으로 다음 **새 검수 helper만** 실행했다. helper는 입력을 읽고 이 고유 폴더의 검수 자료만 쓴다.

```text
python evals/data14-auto-table-link-audit/20261007-01a1100e/render-source-regions.py.txt
python evals/data14-auto-table-link-audit/20261007-01a1100e/audit-builder.py.txt
```

이번 파일들의 SHA는 [artifact-manifest.json](artifact-manifest.json), 기존3,148개 파일 bytes baseline은 [protected-baseline.json](protected-baseline.json)에 있다. manifest 자체와 게시 후 Git head는 자기참조 해시를 피하기 위해 별도 게시 증빙으로 연결한다. 자동 출력/운영 성능·PM 승인·#14 전체 완료는 미확인 상태를 유지한다.
