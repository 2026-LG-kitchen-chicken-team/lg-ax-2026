# 신진하 — R1 fixed-output audit 및 DATA005 collector 근거

- 근거 ID: `신진하-E-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e`
- 관련 기록: [신진하-20261006-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e](../../../작업기록/신진하/2026-10-06/신진하-20261006-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e.md)
- 담당/AI: 신진하 / Codex · 확인일: 2026-10-06 17:34 KST
- 기준 main: `531e2be` (PR #171 PM closeout) · branch `codex/data005-review-trends-20261006`

## 핵심 검증 결과

### 황대겸 고정 결과와 원문

- 산출물 pin: commit `9c7188a29138f43b377c2cac763ab954bc802330`; 입력 source-code commit `45fe0f23afb9c68e115088cef9e10cd122d181f1`.
- `source-manifest.json` raw SHA-256: `d35f1741ab6cfcb197344439bfef791c9516bccbb22f7e44c40e6c5c4be9f1b0`.
- 원 결과 byte SHA:
  - 8B fridge `91bbb9aa695d298b80b0e10c1f0abc5e643ca0f6790ec1194f5303c7230747d6`
  - 8B microwave `a0483657fef00979717bfa8b27ec0710c2314e748780e2d97e83043a188bea01`
  - 27B fridge `009c0bb2df3caeaf3c60b130fb5cbd7ea98b020dc17695d4e2a9a92a80b87803`
- 각 결과의 `original_input.sources`를 `data/demo/dataset.json`과 read-only 비교했다. 비교필드: `id`/evidence ID, `source_type`, `model_id`, `document_version`, `source_kind`, `source_id`, `locator`, 정확한 UTF-8 text. 8B/27B 냉장고는 `11/11`, 전자레인지는 `4/4` exact match. 다른 제품/model/document version 혼입은 없었다.
- 냉장고 manual `MANUAL-001` page 1/section `선반 분리` + review IDs 001–010 rows 2–11. 전자레인지 `MANUAL-005` page 5/section `설정 저장과 호출` + review IDs 034–036 rows 35–37.
- 모든 예시는 dataset version `0.1.0`, source kind `synthetic`다. 모델/status/semantic findings는 `../작업기록/신진하/2026-10-06/신진하-20261006-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e.md`와 `data/research/P2-DATA-002-fixed-output-audit-20261006/result-comparison.md` 참조. 실제 SKU/customer/독립 성능 결론으로 확장하지 않는다.

### 원자료 byte 무결성

| 파일 | 기준 SHA-256 | 결과 |
|---|---|---|
| `data/demo/dataset.json` | `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0` | `Get-FileHash` 결과 일치, review count 36 |
| `data/demo/dataset.json` canonical | `8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03` | PM intake/source summary의 canonical digest와 일치 |
| 기존 review CSV | `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9` | `Get-FileHash`와 importer test에서 일치, 36행/8열 |
| 새 sidecar candidate | `3939b5eec99f4637dec60a84802052577711ea8242718d296d0977c466afe5a8` | 36 review ID 전체 기록, published date 없음은 null/unknown/null |

Importer의 새 NFC/NFD test는 두 Unicode 본문을 각각 원문 그대로 유지하고 CSV 원 bytes/hash가 바뀌지 않는 것을 검사했다. 이 검사는 고정 output-source 비교 및 실제 API 등록/재시작과 별개다.

### 집계 계산

- 2026-10 `FRIDGE-A`, source `REVIEWS-CSV-v1.0`: input 36; out-of-scope 26; in-scope 10; undated 10; outside 0; duplicate 0; eligible unique 0. Bucket denominator 0, `ratio=null`, `evidence_ids=[]`.
- In-memory test-only winter `[2026-12-01, 2027-03-01)` KST: in-scope 10, undated 6, outside 2, duplicate 1, eligible 1, denominator 1; `TREND-EVIDENCE-001` is present in full `__all__` and `cleaning` membership.
- In-memory test-only leap day `2028-02-29`: one denominator shared by both topic counts; `TREND-EVIDENCE-003` occurs once in each matching membership.
- Binding failures: wrong source, model, document version, and duplicate key with changed raw text all reject before returning an aggregate. All three successful collection results passed `validate_trend_collection`.
- Collector is pure DATA calculation and exposes explicit PM injection factory. It is not wired into `workspace_trends`; default None/501 remains.

## 실행 명령/상태

Python 3.11 from the existing environment; no install, live service, GPU, model call, or automatic job retry.

```powershell
$py = '..\..\team-lg-ax-2026\.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
$tests = @('tests/test_review_trends.py','tests/test_review_import.py','tests/test_document_registration.py','tests/test_source_ranges.py')
foreach ($t in $tests) {
  & $py -X utf8 -c "import runpy,sys; sys.path[:0]=['apps/api/src','packages/contracts/src','packages/core/src']; sys.argv=['$t']; runpy.run_path('$t',run_name='__main__')"
}
```

| 검사 | 수치 | 증거/제약 |
|---|---|---|
| trend collector | 3 passed | empty/null, KST winter/dedup, multi-topic denominator/leap, incorrect bindings |
| importer | 10 passed | NFC/NFD fidelity and original CSV bytes/hash |
| document registration | 10 passed | cross product/version/raw identity atomic reject |
| source range | 10 passed | invalid source/version/locator and citation range reject |
| workspace trend gateway | 22 executed; 5 cleanup errors | Local TestClient and MCP mock HTTP calls returned 200 including evidence route, but Windows TemporaryDirectory cleanup could not unlink locked SQLite files; overall test command failed. Uses existing synthetic `FixtureCollector`, not DATA sidecar. Do not label pass. |

The latest #13 manual report (16:56 KST, [comment 6011937003](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011937003)) recorded HTTP 409 because another same-account manual reservation was active. This evidence is not a live upload/search/restart run. The responsible owner/PM must confirm release and approved test resource before that execution.

Latest main PR #171 adds a PM closeout: [api-mcp-path.json](../../../../evals/pm-prototype/20261006/closeout/api-mcp-path.json) reports all 10 API/MCP checks passed at 2026-10-06 17:04 KST, using `tests/test_workspace_trends.py::FixtureCollector`, aggregate `TREND-069f73cc8b40e07533a38f7feea9ac4e25f84ed6430ee22dbf9a311c17ce920e`, and one eligible fixture review. [validation.json](../../../../evals/pm-prototype/20261006/closeout/validation.json) explicitly records `actual_DATA_collector=false`, `actual_customer_dates=false`, `planning_accept=false`, no model calls, and no source changes. This is positive fixture-consumption evidence, separate from this collector's status and the actual 36-row result (zero eligible due to missing dates).

## GitHub routing

- `#13`: fixed-output comparison table and exact blockers, tagged to CORE `@unknownamed` and PM `@jeongiryang`; the source reviewer’s progress is not an approval.
- `#148`: DATA collector code/data/tests, tagged to PM `@jeongiryang` for candidate-sidecar/runtime approval and WEB `@choigilung` for consumption handoff.
- `#16`: formal partial progress report per user instruction. Preserve the separate current issue body status “PM 미채택 확장” until PM reconciles it with current assignment; no automatic adopt/Done/status receipt was recorded here.
- `#15`: user-provided `review requested` remains distinct from approved. PR #167 merge does not certify external private transfer (`external_transfer_complete=false`).

No private evaluation documents, credentials, or hidden answers were included in public output. User-directed public comments will contain only hashes, synthetic example IDs, summary defects, code/test paths, and next actions.
