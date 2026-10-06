"""PM date pack (PR #188, pm-synthetic-trends.v1) over every model × month/season, recomputed independently (record 최길웅-20261007-044).

Each aggregate is recomputed from the raw dataset/annotation bytes with this file's own rules (KST day for day/instant
dates, exact dedup key, season = Mar–May/Jun–Aug/Sep–Nov/Dec–Feb with Jan/Feb in the prior winter year) and compared
with the real workspace API and a real MCP stdio server: buckets, denominators, per-topic evidence IDs, null ratios for
empty buckets, every non-empty bucket × topic evidence page (text, model, document version, source, locator against the
dataset) and the MCP query/saved/evidence results. Tokens are never printed or stored. No model is called.

The dates are PM's constructed demo values, not publication dates; counts are topic mentions, not complaint ratios.
"""
import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[5]
KST = timezone(timedelta(hours=9))
SEASON = {3: "SPRING", 4: "SPRING", 5: "SPRING", 6: "SUMMER", 7: "SUMMER", 8: "SUMMER", 9: "AUTUMN", 10: "AUTUMN", 11: "AUTUMN",
          12: "WINTER", 1: "WINTER", 2: "WINTER"}
SEASON_START = {"SPRING": 3, "SUMMER": 6, "AUTUMN": 9, "WINTER": 12}


def local_day(row: dict) -> date | None:
    value = row.get("published_at")
    if value is None:
        return None
    if row["date_precision"] == "day":
        return date.fromisoformat(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(KST).date()


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def periods(granularity: str, start: date, end: date) -> list[dict]:
    result = []
    if granularity == "month":
        cursor = date(start.year, start.month, 1)
        while cursor < end:
            nxt = add_months(cursor, 1)
            result.append({"bucket_id": f"MONTH-{cursor.year:04d}-{cursor.month:02d}", "period_start": max(cursor, start), "period_end_exclusive": min(nxt, end),
                           "partial_period": cursor < start or nxt > end})
            cursor = nxt
        return result
    name = SEASON[start.month]
    year = start.year - 1 if start.month in (1, 2) else start.year
    cursor = date(year, SEASON_START[name], 1)
    while cursor < end:
        nxt = add_months(cursor, 3)
        result.append({"bucket_id": f"SEASON-{cursor.year:04d}-{SEASON[cursor.month]}", "period_start": max(cursor, start), "period_end_exclusive": min(nxt, end),
                       "partial_period": cursor < start or nxt > end})
        cursor = nxt
    return result


def expected_aggregate(rows: list[dict], model: str, version: str, source_id: str, granularity: str, start: date, end: date) -> dict:
    scoped = [row for row in rows if row["model_id"] == model and row["document_version"] == version and row["source_kind"] == "synthetic" and row["source_id"] == source_id]
    known = [row for row in scoped if local_day(row) is not None]
    in_period = [row for row in known if start <= local_day(row) < end]
    unique: dict = {}
    for row in sorted(in_period, key=lambda item: (local_day(item), item["review_id"])):
        unique.setdefault(row["dedup_key"] or row["review_id"], row)
    topics = sorted({topic for row in scoped for topic in row["topic_ids"]})
    buckets = []
    for period in periods(granularity, start, end):
        members = [row for row in unique.values() if period["period_start"] <= local_day(row) < period["period_end_exclusive"]]
        total = len(members)
        buckets.append({"bucket_id": period["bucket_id"], "period_start": period["period_start"].isoformat(),
                        "period_end_exclusive": period["period_end_exclusive"].isoformat(), "partial_period": period["partial_period"], "total_reviews": total,
                        "topics": {topic: sorted(row["evidence_id"] for row in members if topic in row["topic_ids"]) for topic in topics}})
    return {"counts": {"input_review_count": len(rows), "excluded_out_of_scope_count": len(rows) - len(scoped), "in_scope_review_count": len(scoped),
                       "excluded_undated_count": len(scoped) - len(known), "excluded_outside_period_count": len(known) - len(in_period),
                       "duplicate_count": len(in_period) - len(unique), "eligible_unique_review_count": len(unique),
                       "unclassified_review_count": sum(row["classification_status"] == "unclassified" for row in unique.values())},
            "topics": topics, "buckets": buckets}


def structured(result) -> dict:
    data = getattr(result, "structuredContent", None)
    if data is None:
        data = json.loads(next(item.text for item in result.content if item.type == "text"))
    data = data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
    return data.get("data", data) if isinstance(data, dict) else data


async def mcp_leg(url: str, credential: Path, case: dict, cells: list[tuple[str, str]]) -> dict:
    params = StdioServerParameters(command=sys.executable, args=["-X", "utf8", "-m", "lgax_mcp.workspace_server", "--url", url, "--credential-file", str(credential)], cwd=str(ROOT))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        query = structured(await session.call_tool("review_trends", {"filters": case["filters"]}))
        saved = structured(await session.call_tool("get_review_trends", {"project_id": case["project_id"], "aggregate_id": case["aggregate_id"]}))
        pages = {}
        for bucket_id, topic_id in cells:
            pages[f"{bucket_id}|{topic_id}"] = structured(await session.call_tool("trend_evidence", {"project_id": case["project_id"], "aggregate_id": case["aggregate_id"], "bucket_id": bucket_id, "topic_id": topic_id}))
        return {"query": query.get("aggregate", query), "saved": saved.get("aggregate", saved), "pages": pages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18883")
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True, help="data/demo/review-trends-dated in the PR #188 checkout")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = {name: (args.pack / name).read_bytes() for name in ("dataset.json", "annotation.candidate.json", "date-schedule.json")}
    dataset, annotation = json.loads(raw["dataset.json"]), json.loads(raw["annotation.candidate.json"])
    version, source_id = dataset["manifest"]["version"], dataset["reviews"][0]["source_id"]
    reviews = {item["id"]: item for item in dataset["reviews"]}
    evidence = {item["id"]: item for item in dataset["evidence"]}
    rows = annotation["rows"]
    token = json.loads(args.credential_file.read_text("utf-8"))["token"]
    api = httpx.Client(base_url=args.url, headers={"Authorization": f"Bearer {token}", "Origin": "http://127.0.0.1:5173"}, timeout=30)
    templates = {item["product_group"]: item for item in json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))}
    scopes = [("month", "2026-06-01", "2027-02-01"), ("season", "2026-06-01", "2027-03-01")]
    out: dict = {"kind": "pm_dated_pack_scope_matrix", "observed_at": datetime.now(UTC).isoformat(), "server": args.url, "dataset_version": version,
                 "files_sha256": {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()},
                 "pack_facts": {"reviews": len(rows), "dated": sum(row["published_at"] is not None for row in rows), "undated": sum(row["published_at"] is None for row in rows),
                                "instant_dates": [{"review_id": row["review_id"], "published_at": row["published_at"], "kst_day": local_day(row).isoformat()} for row in rows if row["date_precision"] == "instant"]},
                 "cases": []}
    for product in dataset["products"]:
        model = product["model_id"]
        request = dict(templates[product["product_group"]], model_ids=[model], dataset_version=version)
        created = api.post("/api/workspace/projects", json={"name": f"R4 PM 날짜팩 범위 검증 {model}", "request": request, "document_versions": {model: product["document_version"]}})
        created.raise_for_status()
        project_id = created.json()["data"]["project"]["id"]
        for granularity, start, end in scopes:
            filters = {"project_id": project_id, "model_id": model, "source_ids": [source_id], "dataset_version": version, "start_date": start, "end_date_exclusive": end,
                       "granularity": granularity, "topic_ids": [], "source_kind": "synthetic", "timezone": "Asia/Seoul"}
            base = f"/api/workspace/projects/{project_id}/review-trends"
            response = api.get(base, params={key: value for key, value in filters.items() if key not in ("project_id", "topic_ids")})
            response.raise_for_status()
            aggregate = response.json()["data"]["aggregate"]
            aid = aggregate["aggregate_id"]
            want = expected_aggregate(rows, model, product["document_version"], source_id, granularity, date.fromisoformat(start), date.fromisoformat(end))
            checks: dict = {}
            checks["counts_equal_independent"] = aggregate["counts"] == want["counts"]
            checks["buckets_equal_independent"] = [(b["bucket_id"], b["period_start"], b["period_end_exclusive"], b["partial_period"], b["total_reviews"]) for b in aggregate["buckets"]] == \
                [(b["bucket_id"], b["period_start"], b["period_end_exclusive"], b["partial_period"], b["total_reviews"]) for b in want["buckets"]]
            checks["topic_ids_equal_independent"] = all({t["topic_id"]: t["evidence_ids"] for t in got["topics"]} == exp["topics"] for got, exp in zip(aggregate["buckets"], want["buckets"]))
            checks["ratios_null_only_when_empty"] = all((t["ratio"] is None) == (b["total_reviews"] == 0) and (t["ratio"] is None or abs(t["ratio"] - t["topic_review_count"] / b["total_reviews"]) < 1e-12)
                                                         for b in aggregate["buckets"] for t in b["topics"])
            checks["empty_bucket_warning"] = all(any(b["label"] in w and "없습니다" in w for w in aggregate["warnings"]) for b in aggregate["buckets"] if b["total_reviews"] == 0)
            checks["api_requery_same"] = api.get(f"{base}/{aid}").json()["data"]["aggregate"] == aggregate
            cells = [(b["bucket_id"], t["topic_id"]) for b in aggregate["buckets"] for t in b["topics"] if t["topic_review_count"]]
            pages, page_ok = {}, True
            for bucket_id, topic_id in cells:
                page = api.get(f"{base}/{aid}/evidence", params={"bucket_id": bucket_id, "topic_id": topic_id, "offset": 0, "limit": 50}).json()["data"]
                pages[f"{bucket_id}|{topic_id}"] = page
                ids = sorted(item["id"] for item in page["evidence"])
                expected_ids = next(b for b in want["buckets"] if b["bucket_id"] == bucket_id)["topics"][topic_id]
                for item in page["evidence"]:
                    source = evidence.get(item["id"]) or {}
                    review = next((r for r in reviews.values() if r["evidence_id"] == item["id"]), {})
                    page_ok &= (item["text"] == source.get("text") == review.get("text") and item["model_id"] == model and item["document_version"] == product["document_version"]
                                and item["source_id"] == source_id and item.get("locator") == source.get("locator"))
                page_ok &= ids == expected_ids
            checks["api_evidence_pages_match_dataset"] = page_ok
            case = {"model_id": model, "granularity": granularity, "project_id": project_id, "aggregate_id": aid, "filters": filters}
            via_mcp = asyncio.run(mcp_leg(args.url, args.credential_file, case, cells))
            checks["mcp_query_same_id"] = via_mcp["query"].get("aggregate_id") == aid
            checks["mcp_saved_identical"] = via_mcp["saved"] == aggregate
            checks["mcp_evidence_pages_identical"] = via_mcp["pages"] == pages
            case.update({"checks": checks, "counts": aggregate["counts"], "dataset_sha256": aggregate["dataset_sha256"], "annotation_sha256": aggregate["annotation_sha256"],
                         "buckets": [{"bucket_id": b["bucket_id"], "label": b["label"], "partial_period": b["partial_period"], "total_reviews": b["total_reviews"],
                                      "topics": [{"topic_id": t["topic_id"], "count": t["topic_review_count"], "ratio": t["ratio"], "evidence_ids": t["evidence_ids"]} for t in b["topics"]]} for b in aggregate["buckets"]],
                         "warnings": aggregate["warnings"], "evidence_cells_checked": len(cells), "ok": all(checks.values())})
            out["cases"].append(case)
            print(json.dumps({"model": model, "granularity": granularity, "ok": case["ok"], "cells": len(cells), "failed": [k for k, v in checks.items() if not v]}, ensure_ascii=False))
    out["result"] = "scope_matrix_ok" if all(case["ok"] for case in out["cases"]) else "scope_matrix_mismatch"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out["result"])
    return 0 if out["result"] == "scope_matrix_ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
