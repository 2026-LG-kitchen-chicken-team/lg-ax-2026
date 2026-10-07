"""Read immutable Git evidence and write only this acceptance-audit directory.

No source helpers are imported; no network, server, SQLite, ZIP or model is run.
"""

import csv
import hashlib
import io
import itertools
import json
import subprocess
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "1f25e547f46ef155798fbc27f35aa2c7098ae912"
PRODUCER = "0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d"
CAPTURE = "06701a5979920abb6d18da039056b64af6c84df9"
CANDIDATE = "d5d33c46a5f27d7ccd805713c784ec4c9f0ace55"
PACK = "data/research/r5-public-reviews-20261007/"
ART = "evals/data456-r5-verification/20261007-01a10c5c-bf12d6e3/"
CAND = "evals/data15-candidate-preparation/20261007-01a10600/"
GH = "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/"
CHECKS = []
SOURCES = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
    )


def read(commit, path):
    raw = git("show", commit + ":" + path)
    SOURCES[commit + ":" + path] = {
        "commit": commit, "path": path, "bytes": len(raw), "sha256": sha(raw)
    }
    return raw


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def load(commit, path):
    return json.loads(read(commit, path), object_pairs_hook=unique_fields)


def check(name, observed, expected, pointer=None):
    CHECKS.append({
        "check": name, "passed": observed == expected,
        "observed": observed, "expected": expected, "source_pointer": pointer,
    })


def write(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def table(name, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (OUT / name).write_text(buffer.getvalue(), encoding="utf-8", newline="\n")


def norm(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def audit_manifest():
    manifest = load(CAPTURE, ART + "artifact-manifest.json")
    rows = []
    for item in manifest["files"]:
        path = item["path"]
        if path.startswith("/") or ".." in path.split("/"):
            raise ValueError("Manifest path is outside frozen artifact directory")
        raw = read(CAPTURE, ART + path)
        check("PR226 bytes " + path, len(raw), item["bytes"])
        check("PR226 SHA " + path, sha(raw), item["sha256"])
        rows.append({"path": path, "bytes": len(raw), "sha256": sha(raw),
                     "matches_manifest": len(raw) == item["bytes"] and sha(raw) == item["sha256"]})
    check("PR226 manifest paths unique", len({r["path"] for r in rows}), len(rows))
    table("PR226-artifact-byte-audit.csv", rows)


def audit_population():
    first = load(PRODUCER, PACK + "fixed18/records.json")
    second = load(PRODUCER, PACK + "balanced-pilot-v2/records.json")
    expected = load(CAPTURE, ART + "research-population-audit.json")
    for profile in ("fixed18", "balanced-pilot-v2"):
        for name, expected_sha in load(PRODUCER, PACK + profile + "/files.json").items():
            if name == "public-reviews.sqlite3":
                continue
            check("R5 published SHA " + profile + "/" + name,
                  sha(read(PRODUCER, PACK + profile + "/" + name)), expected_sha)
    ids = {r["original_review_id"] for r in first}
    additions = [r for r in second if r["original_review_id"] not in ids]
    check("sidecar new unique projection", additions == load(
        PRODUCER, PACK + "balanced-pilot-v2/new_unique_records.json"), True)
    rows = [(r, PACK + "fixed18/records.json", i) for i, r in enumerate(first)]
    rows += [(r, PACK + "balanced-pilot-v2/records.json", i)
             for i, r in enumerate(second) if r["original_review_id"] not in ids]
    overlap = []
    primary = {r["original_review_id"]: r for r in first}
    for r in second:
        if r["original_review_id"] in ids:
            old = primary[r["original_review_id"]]
            same = old["text_sha256"] == r["text_sha256"] and norm(old["text"]) == norm(r["text"])
            check("overlap has same body " + r["original_review_id"], same, True)
            overlap.append({"id": r["original_review_id"], "text_sha256": r["text_sha256"],
                            "same_normalized_body": same, "retained": "fixed18"})
    membership = []
    pages = defaultdict(list)
    for r, path, index in rows:
        rid = r["original_review_id"]
        check("public Korean text SHA " + rid, sha(r["text"].encode()), r["text_sha256"])
        quarantine = r.get("quarantined", False) or r["split"] == "quarantine"
        normalized_sha = sha(norm(r["text"]).encode())
        row = {
            "original_review_id": rid, "split": r["split"], "quarantined": quarantine,
            "displayed_page_model": r["displayed_model_id"],
            "actual_purchased_model_id": r["actual_purchased_model_id"],
            "published_at": r["published_at"], "purchase_date": r.get("purchase_date"),
            "text_sha256": r["text_sha256"], "normalized_text_sha256": normalized_sha,
            "source_url": r["source_url"], "source_locator": r["source_locator"],
            "source_file": path, "source_json_pointer": "/" + str(index),
            "fixed_original_link": GH + "blob/" + PRODUCER + "/" + path,
            "manual_version": r.get("manual_version"),
            "date_basis": r.get("date_basis"),
            "quality_flags": r.get("quality_flags", []),
            "counted_in_research_population": not quarantine,
            "counted_in_monthly_population": not quarantine and r["published_at"] is not None,
        }
        membership.append(row)
        pages[row["displayed_page_model"]].append(row)
    check("unique original IDs", len({r["original_review_id"] for r in membership}), len(membership))
    split = dict(Counter(r["split"] for r in membership))
    research = [r for r in membership if not r["quarantined"]]
    intersections = []
    for left, right in itertools.combinations(("development", "independent_evaluation", "demonstration"), 2):
        for field in ("original_review_id", "normalized_text_sha256"):
            shared = sorted({r[field] for r in membership if r["split"] == left}
                            & {r[field] for r in membership if r["split"] == right})
            check("split overlap " + left + "/" + right + "/" + field, len(shared), 0)
            intersections.append({"left": left, "right": right, "field": field, "shared": shared})
    comparison = {"raw_rows": len(first) + len(second), "unique_rows": len(rows),
                  "split_counts": split, "quarantine_excluded": len(rows) - len(research),
                  "research_denominator": len(research),
                  "unknown_posting_date_excluded": sum(r["published_at"] is None for r in research),
                  "monthly_denominator": sum(r["published_at"] is not None for r in research),
                  "exact_SKU_eligible_reviews": sum(r["actual_purchased_model_id"] is not None for r in research)}
    for key, value in comparison.items():
        check("independent PR226 population " + key, value, expected[key])
    check("PR226 membership row count", len(membership), len(expected["membership"]))
    projected = [{k: r[k] for k in old} for r, old in zip(membership, expected["membership"])]
    check("all PR226 membership fields", projected == expected["membership"], True)
    page_rows = []
    for model, members in pages.items():
        eligible = [r for r in members if r["counted_in_research_population"]]
        page_rows.append({"displayed_page_model": model, "unique_rows": len(members),
                          "quarantined": len(members) - len(eligible),
                          "research_denominator": len(eligible),
                          "unknown_posting_date_excluded": sum(r["published_at"] is None for r in eligible),
                          "monthly_denominator": sum(r["published_at"] is not None for r in eligible),
                          "topic_numerator": None, "topic_ratio": None,
                          "member_original_review_ids": "|".join(r["original_review_id"] for r in eligible)})
    for old in expected["page_models"]:
        row = next(r for r in page_rows if r["displayed_page_model"] == old["displayed_page_model"])
        check("page research denominator " + row["displayed_page_model"],
              row["research_denominator"], old["research_denominator"])
    tz = timezone(timedelta(hours=9))
    windows = []
    for name, start, end in (("2026-10", "2026-10-01T00:00:00+09:00", "2026-11-01T00:00:00+09:00"),
                             ("2026-winter", "2026-12-01T00:00:00+09:00", "2027-03-01T00:00:00+09:00")):
        included = []
        for r in research:
            if r["published_at"] is None:
                continue
            date = datetime.fromisoformat(r["published_at"])
            if date.tzinfo is None:
                raise ValueError("Publication timestamp has no declared timezone")
            if datetime.fromisoformat(start) <= date.astimezone(tz) < datetime.fromisoformat(end):
                included.append(r["original_review_id"])
        windows.append({"window": name, "start_inclusive": start, "end_exclusive": end,
                        "timezone": "Asia/Seoul", "denominator": len(included), "member_ids": included,
                        "topic_numerator": None, "topic_ratio": None,
                        "boundary_with_real_dated_records_verified": False})
    summary = {**comparison, "removed_duplicate_observations": overlap,
               "unknown_posting_date_unique_total": sum(r["published_at"] is None for r in membership),
               "quarantine_and_unknown_date_intersection": sum(r["quarantined"] and r["published_at"] is None for r in membership),
               "exclusion_union": len(membership) - comparison["monthly_denominator"],
               "exclusion_order": ["dedup original ID (same body required)", "quarantine", "unknown published_at"],
               "research_rating_counts": dict(Counter(str(r["rating"]) for r, _, _ in rows
                                                     if not (r.get("quarantined", False) or r["split"] == "quarantine"))),
               "split_intersections": intersections, "windows": windows,
               "topic_numerators": None, "topic_ratios": None,
               "topic_annotation_approved": False,
               "scope": "frozen public research sample; not customers, purchased SKU or operating data",
               "model_input_eligible_rows": sum(bool(r["eligible_for_model_input"]) for r, _, _ in rows)}
    check("rating denominator", sum(summary["research_rating_counts"].values()), len(research))
    check("PR226 rating counts", summary["research_rating_counts"], expected["research_rating_counts"])
    write("trend-recalculation.json", summary)
    table("review-membership.csv", membership)
    table("page-model-denominators.csv", page_rows)


def audit_capture():
    saved = load(CAPTURE, ART + "isolated-HTTP-SQLite-capture.json")
    src = saved["source_commit"]
    plan = load(src, saved["document_plan"]["path"])
    dataset = load(src, saved["execution_dataset"]["path"])
    check("original plan SHA", sha(read(src, saved["document_plan"]["path"])), saved["document_plan"]["raw_sha256"])
    check("original dataset SHA", sha(read(src, saved["execution_dataset"]["path"])), saved["execution_dataset"]["raw_sha256"])
    expected_evidence = {r["id"]: r for r in dataset["evidence"]}
    pdfs = {}
    for doc in plan["documents"]:
        path = "data/sources/lg-manuals-20261005/" + doc["product"]["model_id"] + "-" + doc["sha256"][:12] + ".pdf"
        raw = read(src, path)
        check("original PDF SHA " + doc["document_id"], sha(raw), doc["sha256"])
        pdfs[doc["document_id"]] = {"path": path, "bytes": len(raw), "sha256": sha(raw)}
    capture_rows = []
    scope_rows = []
    for i, cap in enumerate(saved["captures"]):
        if cap["json"] is not None:
            raw = json.dumps(cap["json"], ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
            check("JSON serialized SHA " + str(i), sha(raw), cap["response_sha256"], "/captures/" + str(i))
            check("JSON serialized bytes " + str(i), len(raw), cap["response_bytes"])
            kind = "parsed JSON reconstructed with explicit compact UTF-8 serialization"
        else:
            doc_id = cap["path"].split("/")[-2]
            original = pdfs[doc_id]
            check("PDF response SHA " + str(i), cap["response_sha256"], original["sha256"])
            check("PDF response bytes " + str(i), cap["response_bytes"], original["bytes"])
            kind = "declared response SHA and size against immutable original PDF"
        capture_rows.append({"capture_index": i, "phase": cap["phase"], "service": cap["service"],
                             "method": cap["method"], "path": cap["path"], "status": cap["status"],
                             "bytes": cap["response_bytes"], "sha256": cap["response_sha256"], "comparison_scope": kind})
        parsed = urlsplit(cap["path"])
        if cap["method"] == "GET" and cap["json"] and cap["status"] == 200:
            data = cap["json"].get("data", {})
            if parsed.path.startswith("/api/evidence/") and parsed.path != "/api/evidence/search":
                ev = data["evidence"]
                check("single evidence original equality " + str(i), ev == expected_evidence[ev["id"]], True)
            if parsed.path == "/api/evidence/search" or parsed.path.endswith("/evidence"):
                search = data.get("search", cap["json"])["data"]
                params = parse_qs(parsed.query)
                model = params["model_id"][0]
                version = params.get("document_version", [search["document_version"]])[0]
                for ev in search["items"]:
                    check("search model scope " + str(i) + "/" + ev["id"], ev["model_id"], model)
                    check("search version scope " + str(i) + "/" + ev["id"], ev["document_version"], version)
                    check("search source equality " + str(i) + "/" + ev["id"], ev == expected_evidence[ev["id"]], True)
                scope_rows.append({"capture_index": i, "path": cap["path"], "status": 200,
                                   "model_id": model, "document_version": version,
                                   "returned_evidence_ids": "|".join(ev["id"] for ev in search["items"]),
                                   "returned_items_match_frozen_originals": True})
        if "unregistered-research-SKU" in cap["path"] or "unapproved-version" in cap["path"]:
            expected_status = 422 if "/api/workspace/" in cap["path"] else (400 if "unapproved-version" in cap["path"] else 404)
            check("unknown model/version rejection " + str(i), cap["status"], expected_status)
            check("rejection no successful body " + str(i), cap["json"].get("ok"), False)
            scope_rows.append({"capture_index": i, "path": cap["path"], "status": cap["status"],
                               "model_id": None, "document_version": None,
                               "returned_evidence_ids": "", "returned_items_match_frozen_originals": None})
    before = [(i, c) for i, c in enumerate(saved["captures"]) if c["phase"] == "before-restart"]
    after = [(i, c) for i, c in enumerate(saved["captures"]) if c["phase"] == "after-restart"]
    check("restart capture pair count", len(before), len(after))
    pairs = []
    for (bi, b), (ai, a) in zip(before, after):
        bvalue = {k: v for k, v in b.items() if k != "phase"}
        avalue = {k: v for k, v in a.items() if k != "phase"}
        check("entire recorded response pair " + str(bi) + "/" + str(ai), bvalue == avalue, True)
        pairs.append({"before_index": bi, "after_index": ai, "service": b["service"],
                      "method": b["method"], "path": b["path"], "status": b["status"],
                      "sha256": b["response_sha256"], "recorded_fields_equal": bvalue == avalue})
    check("DB full snapshot equality", saved["DB_before"] == saved["DB_after"], True)
    db = []
    for database, snapshot in saved["DB_before"].items():
        for name, rows in snapshot["tables"].items():
            db.append({"database": database, "DB_sha256": snapshot["sha256"], "table": name,
                       "row_count": len(rows), "before_after_equal": True,
                       "rows_canonical_sha256": sha(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode())})
    doc_gets = {c["path"].split("/")[-1]: c["json"]["data"] for _, c in before
                if c["status"] == 200 and c["path"].startswith("/api/documents/") and not c["path"].endswith("/original")}
    for record in saved["DB_before"]["documents"]["tables"]["documents"]:
        stored = json.loads(record[2], object_pairs_hook=unique_fields)
        check("DB document vs GET " + record[0], stored == doc_gets[record[0]], True)
    for doc in plan["documents"]:
        record = doc_gets[doc["document_id"]]
        for key in ("document_id", "sha256", "product", "document_version", "source_kind", "url"):
            check("document identity " + doc["document_id"] + "/" + key, record[key] == doc[key], True)
        check("document selected features " + doc["document_id"], record["dataset"]["features"] == doc["features"], True)
        for selection in doc["selections"]:
            ev = next(e for e in record["dataset"]["evidence"] if e["id"] == selection["evidence_id"])
            check("selected Korean excerpt " + ev["id"], ev["text"], selection["excerpt"])
            check("selected page " + ev["id"], ev["locator"]["page"], selection["page"])
    bootstrap = next(c["json"]["data"] for _, c in before
                     if c["path"] == "/api/workspace/bootstrap" and c["status"] == 200)
    for key in ("products", "reviews", "features", "evidence"):
        check("bootstrap source " + key, bootstrap[key] == dataset[key], True)
    compatibility = load(CAPTURE, ART + "consumer-source-compatibility.json")
    compat = []
    for old in compatibility["sources"]:
        path = old["path"]
        frozen = sha(read(src, path))
        current = sha(read(BASE, path))
        compat.append({"path": path, "tested_source_SHA": frozen, "publication_base_SHA": current,
                       "byte_equal": frozen == current, "execution_at_publication_base_verified": False})
    bridge = load(CAPTURE, ART + "source-main-bridge.json")
    changed = git("diff", "--name-only", "-z", src, BASE, "--",
                  *bridge["critical_code_data_scopes"]).decode("utf-8").split("\0")
    changed = [path for path in changed if path]
    write("capture-current-main-bridge.json", {
        "captured_execution_source": src, "publication_base": BASE,
        "critical_scopes": bridge["critical_code_data_scopes"], "changed_paths": changed,
        "scope_bytes_identical": not changed,
        "selected_PR219_consumer_files_byte_identical": all(r["byte_equal"] for r in compat),
        "runtime_at_publication_base_verified": False,
        "historical_response_receipts_are_not_current_runtime_receipts": True,
    })
    write("capture-audit-summary.json", {
        "source_commit": src, "frozen_capture_head": CAPTURE,
        "recorded_HTTP_responses": len(saved["captures"]),
        "JSON_serialization_reconstructions": sum(c["json"] is not None for c in saved["captures"]),
        "PDF_declared_hash_size_comparisons": sum(c["json"] is None for c in saved["captures"]),
        "recorded_restart_pairs": len(pairs), "DB_snapshot_full_equality": saved["DB_before"] == saved["DB_after"],
        "documents": len(plan["documents"]), "canonical_reviews": len(dataset["reviews"]),
        "evidence": len(dataset["evidence"]), "features": len(dataset["features"]),
        "research_DB": {"rows": saved["research_DB_rebuild"]["reviews"],
                        "SHA": saved["research_DB_rebuild"]["sha256"],
                        "scope": "author rebuilt fixed18 179-row DB; binary not independently received"},
        "raw_JSON_wire_files_received": False, "SQLite_binary_files_received": False,
        "operating_origin_verified": False, "actual_operating_restart_verified": False,
        "combined_238_operating_reviews_verified": False,
        "scope": saved["scope"], "new_HTTP_calls": 0, "new_restarts": 0,
        "source_assertions_584": "author assertions preserved; independently recounted evidence below",
        "PM_scope_receipt": GH + "pull/226#pullrequestreview-5437336094",
    })
    table("HTTP-recorded-body-audit.csv", capture_rows)
    table("restart-pairs.csv", pairs)
    table("search-scope-audit.csv", scope_rows)
    table("DB-snapshot-audit.csv", db)
    table("consumer-version-audit.csv", compat)


def audit_candidate_metadata():
    producer = load(CANDIDATE, CAND + "role-separation-and-package-metadata.json")
    intake = load(CAPTURE, ART + "candidate-opaque-archive-intake.json")
    overlay = load(BASE, PACK + "independence-holds.20261007.v1.json")
    check("PM overlay fixed18 SHA", overlay["fixed18_records_sha256"],
          sha(read(PRODUCER, PACK + "fixed18/records.json")))
    check("PM overlay sidecar SHA", overlay["balanced_v2_records_sha256"],
          sha(read(PRODUCER, PACK + "balanced-pilot-v2/records.json")))
    rows = []
    for old in producer["archives"]:
        item = next(a for a in intake["archives"] if a["role"] == old["role"])
        check("candidate published archive SHA " + old["role"], item["expected_sha256"], old["archive_sha256"])
        check("author opaque SHA " + old["role"], item["actual_sha256"], old["archive_sha256"])
        check("archive entry metadata " + old["role"], item["entry_count_from_producer_metadata_only"], old["entry_count"])
        rows.append({"role": old["role"], "filename": old["filename"],
                     "entries_producer_metadata_only": old["entry_count"],
                     "SHA": old["archive_sha256"], "PR226_author_opaque_SHA_matches": item["actual_sha256"] == old["archive_sha256"],
                     "this_audit_archive_or_contents_read": False, "recipient_delivery_receipt_received": False})
    table("candidate-package-metadata.csv", rows)
    write("evaluation-release-gates.json", {
        "candidate_producer_head": CANDIDATE, "synthetic_primary_groups": producer["primary_inputs"],
        "paired_previous_input": producer["paired_previous_input"],
        "public_research_evaluation36_is_a_separate_cohort": True,
        "PM_research_independence_overlay": {
            "version": overlay["overlay_version"],
            "known_historically_exposed_original_ids": [r["original_review_id"] for r in overlay["known_development_exposure"]],
            "known_exposed_groups_in_evaluation_candidates": overlay["known_exposed_groups_in_evaluation_candidates"],
            "known_exposed_groups_in_demonstration_candidates": overlay["known_exposed_groups_in_demonstration_candidates"],
            "remaining_lineage_review_required": True,
            "research_split_counts_are_not_approved_usable_counts": True,
            "runtime_enforcement_implemented": overlay["runtime_enforcement_implemented"],
        },
        "old_public8_heldout7_role": "PM approved development diagnostics/regression only; independent denominator excluded",
        "candidate_metadata_binding": "matched PR222 producer to PR226 author opaque digest claims",
        "private_ZIP_or_expected_answers_read_by_this_audit": False,
        "CORE_mapping_role": "source/support/residual/question mapping and counterexamples",
        "gates": [
            {"gate": "approved private route and actual input-only recipient ACK", "state": "missing", "owner": "@jeongiryang; @unknownamed recipient", "needed": "existing free private transport endpoint/client/read scope/recipient PC mapping; recipient bytes/SHA/11-entry receipt"},
            {"gate": "source mapping and semantic Gold", "state": "unapproved", "owner": "@unknownamed mapping; @jeongiryang approval", "needed": "case/source/model/version/quote to expected support, residual need and questions; approved private Gold digest and approver"},
            {"gate": "semantic independence and cohort", "state": "unapproved", "owner": "@jeongiryang", "needed": "selected six groups, paired treatment, prior exposure scope and independent author/reviewer separation"},
            {"gate": "final scorer", "state": "not designated", "owner": "@jeongiryang", "needed": "named scorer distinct from candidate/code/Gold authors; frozen rubric and private access scope"},
            {"gate": "same whole input Agent and strong baseline raw outputs", "state": "not received", "owner": "PM-approved executor", "needed": "approved existing free execution scope, versions/input SHA/full-input receipt, paired raw outputs and retries/failures/tokens/cost receipts"},
            {"gate": "actual independent scoring", "state": "not run", "owner": "PM-designated independent scorer", "needed": "per-group scores and original output/source pointers under approved rubric"},
        ], "independent_score": None, "actual_independent_evaluation_complete": False,
        "authority": [GH + "issues/15#issuecomment-6029601114", GH + "issues/15#issuecomment-6030290912"],
        "new_model_calls": 0, "new_OCR_calls": 0,
    })


def main():
    audit_manifest()
    audit_population()
    audit_capture()
    audit_candidate_metadata()
    write("source-pins.json", {"publication_base": BASE, "PR218_R5_producer": PRODUCER,
                               "PR226_capture": CAPTURE, "PR222_candidate": CANDIDATE,
                               "read_sources": list(SOURCES.values())})
    failed = [c for c in CHECKS if not c["passed"]]
    write("verification-checks.json", {"status": "PASS" if not failed else "FAIL",
                                      "checks": CHECKS, "count": len(CHECKS), "failed_count": len(failed)})
    print(json.dumps({"checks": len(CHECKS), "failed": len(failed), "output": str(OUT)}, ensure_ascii=False))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
