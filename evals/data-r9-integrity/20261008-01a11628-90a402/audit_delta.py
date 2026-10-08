"""Read-only R9 delta audit. Run on staged immutable bytes in zero-auth Docker.

No repository imports, network, model, OCR, DB writes or producer execution.
Input staging and PDF native extraction are documented in audit.md.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def nulls(value):
    if isinstance(value, dict):
        return sum(nulls(v) for v in value.values())
    if isinstance(value, list):
        return sum(nulls(v) for v in value)
    return int(value is None)


def diff(a, b, path=""):
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            subpath = path + "/" + key
            result.extend(diff(a[key], b[key], subpath)
                          if key in a and key in b else [subpath])
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [path]
        return [p for n, (x, y) in enumerate(zip(a, b))
                for p in diff(x, y, path + "/" + str(n))]
    return [] if a == b else [path]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.input, args.out
    out.mkdir(parents=True, exist_ok=True)
    checks = Counter()
    failures = []

    def check(name, ok, detail=None):
        checks["checked"] += 1
        checks["passed" if ok else "failed"] += 1
        if not ok:
            failures.append({"check": name, "detail": detail})

    def read(path):
        return json.loads((root / path).read_bytes())

    def write(name, data):
        (out / name).write_bytes((json.dumps(data, ensure_ascii=False,
                                            indent=2) + "\n").encode("utf-8"))

    receipt = json.loads(args.receipt.read_bytes())
    for record in receipt["files"]:
        raw = (root / record["staged_path"]).read_bytes()
        check("staged_bytes:" + record["staged_path"],
              len(raw) == record["bytes"] and sha(raw) == record["sha256"])

    old = read("pr246/result.json")
    check("reused_pr246_pass", old["status"] == "PASS")
    guard = read("pr246/guard-probes.json")
    check("reused_pr246_guard_probes", guard["status"] == "PASS"
          and all(p["detected"] for p in guard["probes"]))
    check("reused_audit_code_pin", sha((root / "pr246/audit_delivery.py").read_bytes())
          == guard["audit_code_sha256"])
    for name in ["result.json", "producer-receipt.json", "execution.json",
                 "guard-probes.json", "audit_delivery.py"]:
        check("pr246_merged_bytes:" + name,
              (root / "pr246" / name).read_bytes()
              == (root / "current-d4" / name).read_bytes())
    for name in ["d1-membership.json", "d1-delivery-manifest.json"]:
        check("audited_producer_bytes:" + name,
              (root / "audited-producer" / name).read_bytes()
              == (root / "current-producer" / name).read_bytes())
    membership = read("current-producer/d1-membership.json")
    members = {x["original_review_id"]: x for x in membership}
    check("membership_238_unique", len(membership) == len(members) == 238)
    check("split_membership_reused", Counter(x["split"] for x in membership)
          == {"development": 141, "independent_evaluation": 36,
              "demonstration": 49, "quarantine": 12})

    manifest = read("r9/manifest.json")
    corrections = {x["source_id"]: x for x in manifest["metadata_corrections"]}
    check("exactly_five_corrections", len(corrections) == 5)
    ledger, bundles, reviews, all_sources, changed = [], [], [], [], []
    for group in ["fridge", "dishwasher", "microwave"]:
        before_bytes = (root / "pr254" / (group + ".json")).read_bytes()
        after_bytes = (root / "r9" / (group + ".research-bundle.json")).read_bytes()
        before, after = json.loads(before_bytes), json.loads(after_bytes)
        pin = manifest["groups"][group]
        check(group + ":pr254_input_pin", sha(before_bytes) == pin["input_sha256"])
        check(group + ":r9_output_pin", sha(after_bytes) == pin["output_sha256"])
        check(group + ":producer_unmodified", before_bytes ==
              (root / "current-producer" / (group + ".json")).read_bytes())
        bmap = {x["source_id"]: x for x in before["sources"]}
        amap = {x["source_id"]: x for x in after["sources"]}
        check(group + ":ids_unique_preserved", len(bmap) == len(before["sources"])
              and len(amap) == len(after["sources"]) and bmap.keys() == amap.keys())
        check(group + ":source_order_preserved",
              list(bmap) == list(amap))
        expected = copy.deepcopy(before)
        expected["bundle_id"] = pin["output_bundle_id"]
        for source in expected["sources"]:
            if source["source_id"] in corrections:
                fix = corrections[source["source_id"]]
                check(source["source_id"] + ":declared_old_value",
                      source["metadata"]["continuation_pages"] == fix["old_value"])
                source["metadata"]["continuation_pages"] = fix["new_value"]
        check(group + ":only_declared_delta", expected == after, diff(expected, after))
        check(group + ":source_review_counts",
              len(amap) == pin["source_count"] and
              sum(x["source_type"] == "review" for x in amap.values())
              == pin["development_review_count"])
        for sid, source in amap.items():
            previous = bmap[sid]
            fields = diff(previous, source)
            if fields:
                changed.append({"source_id": sid, "fields": fields})
            check(sid + ":body_and_nulls_preserved",
                  source["text"] == previous["text"] and nulls(source) == nulls(previous))
            ledger.append({
                "product_group": group, "source_id": sid,
                "source_type": source["source_type"],
                "before_source_json_sha256": sha(encoded(previous)),
                "after_source_json_sha256": sha(encoded(source)),
                "text_sha256": sha(source["text"].encode("utf-8")),
                "null_count": nulls(source),
                "changed_fields": "|".join(fields),
            })
            all_sources.append(source)
            if source["source_type"] == "review":
                metadata = source["metadata"]
                rid = metadata["original_review_id"]
                member = members.get(rid, {})
                check(sid + ":development_membership",
                      member.get("split") == metadata["split"] == "development"
                      and member.get("product_group") == group)
                check(sid + ":original_text_and_version",
                      member.get("text_sha256") == metadata["original_text_sha256"]
                      and metadata["text_sha256"] == sha(source["text"].encode("utf-8"))
                      and member.get("document_version") == source["document_version"])
                check(sid + ":unknowns_and_exposure",
                      source["published_at"] is None and source["purchased_model"] is None
                      and metadata["strict_exact_model_eligible_for_model_input"] is False
                      and metadata["original_input_hold_reasons"] == member["input_hold_reasons"]
                      and metadata["known_historical_development_exposure"]
                      == member["known_development_exposure"])
                reviews.append(rid)
        bundles.append({"group": group, "sources": len(amap),
                        "reviews": pin["development_review_count"],
                        "input_sha256": sha(before_bytes), "output_sha256": sha(after_bytes),
                        "input_bundle_id": before["bundle_id"], "output_bundle_id": after["bundle_id"]})
    check("184_unique_sources", len(all_sources) ==
          len({x["source_id"] for x in all_sources}) == 184)
    check("141_exact_development_ids", len(reviews) == len(set(reviews)) == 141
          and set(reviews) == {k for k, v in members.items() if v["split"] == "development"})
    check("only_five_metadata_changes", len(changed) == 5 and
          {x["source_id"] for x in changed} == set(corrections) and
          all(x["fields"] == ["/metadata/continuation_pages"] for x in changed))

    care_sources = [x for x in all_sources if x["source_id"].startswith("D2-DUE-CARE-")]
    native_care = {x["audit_evidence_id"]: x for x in read("care/manual-native-excerpts.json")}
    check("care14_count", len(care_sources) == len(native_care) == 14)
    pack = read("r9/manual-excerpts.json")
    reference = read("r9/microwave.manual-reference.research-bundle.json")
    ref_manifest = read("r9/manual-reference.manifest.json")
    check("reference5_objects_preserved", reference["sources"] == pack["sources"]
          and len(reference["sources"]) == 5)
    check("reference5_file_pins",
          sha((root / "r9/manual-excerpts.json").read_bytes()) == ref_manifest["source_pack_sha256"]
          and sha((root / "r9/microwave.manual-reference.research-bundle.json").read_bytes())
          == ref_manifest["output_sha256"])
    check("reference5_zero_reviews", all(s["source_type"] == "manual" for s in reference["sources"]))
    check("reference5_separate_from184", not
          ({s["source_id"] for s in reference["sources"]} & {s["source_id"] for s in all_sources}))
    check("reference5_four_unique_pdfs",
          len({x["metadata"]["pdf_sha256"] for x in reference["sources"]}) == 4)
    catalogue = {x["model_id"]: x for x in read("references/manual-acquisition.json")["models"]}
    intake_receipts = read("r9/manual-intake.manifest.json")["receipts"]
    citation_rows = []
    for source in care_sources + reference["sources"]:
        sid, metadata, locator = source["source_id"], source["metadata"], source["locator"]
        pdf_sha = metadata["pdf_sha256"]
        document = read("native-pages/" + pdf_sha + ".json")
        pdf = (root / "pdfs" / (pdf_sha + ".pdf")).read_bytes()
        check(sid + ":actual_pdf_bytes", sha(pdf) == pdf_sha and len(pdf) == document["pdf_bytes"])
        page = document["pages"][str(locator["page"])]
        text = page["text"]
        check(sid + ":native_page_hash", sha(text.encode("utf-8")) == page["text_sha256"])
        check(sid + ":native_range_and_excerpt_hash",
              text[locator["start_char"]:locator["end_char"]] == source["text"]
              and sha(source["text"].encode("utf-8")) == metadata["text_sha256"])
        cover = "".join(document["pages"]["1"]["text"].split())
        check(sid + ":document_version_on_cover",
              "".join(source["document_version"].split()) in cover)
        check(sid + ":unknown_scope_holds",
              source["purchased_model"] is None and source["published_at"] is None
              and source["date_kind"] == "unknown" and source["coverage"] == "excerpt"
              and source["source_role"] == "official_document"
              and source["facts"] == [] and metadata["ocr_used"] is False
              and metadata["numeric_facts_extracted_automatically"] is False)
        if sid.startswith("D2-DUE-CARE-"):
            original = native_care[metadata["audit_evidence_id"]]
            check(sid + ":prior_native_evidence_exact",
                  source["text"] == original["native_exact_excerpt"]
                  and metadata["text_sha256"] == original["native_excerpt_sha256"]
                  and page["text_sha256"] == original["native_page_text_sha256"]
                  and source["document_version"] == original["document_version"]
                  and all(locator[k] == original[k] for k in
                          ["page", "printed_page", "start_char", "end_char"]))
            check(sid + ":shared_manual_not_exact_sku",
                  source["page_model"] is None and
                  "unverified" in metadata["applicability"] and "DUE6BGL2E" not in cover)
        else:
            check(sid + ":base_model_cover",
                  source["page_model"] in cover and "unverified" in metadata["applicability"])
            check(sid + ":native_page_pin", page["text_sha256"] == metadata["page_text_sha256"])
            check(sid + ":catalogue_pin", sha((root / "references/manual-acquisition.json").read_bytes())
                  == metadata["catalogue_sha256"])
            candidates = catalogue[source["page_model"]]["candidates"]
            latest_date = max(x["listed_date"] for x in candidates)
            matching = [x for x in candidates if x["url"] == source["url"]
                        and x["pdf_sha256"] == pdf_sha]
            check(sid + ":catalogue_selection_and_pdf_bytes",
                  bool(matching) and metadata["support_listed_date"] == latest_date
                  and any(x["listed_date"] == latest_date and x["bytes"] == len(pdf)
                          and source["document_version"]
                          in x["observed_cover_versions_normalized"]
                          for x in matching))
            check(sid + ":pm_receipt_matches_local_pdf",
                  any(x["url"] == source["url"] and x["received_sha256"] == pdf_sha
                      and x["received_bytes"] == len(pdf) for x in intake_receipts))
        citation_rows.append({
            "source_id": sid, "pdf_sha256": pdf_sha, "pdf_bytes": len(pdf),
            "document_version": source["document_version"],
            "page": locator["page"], "start_char": locator["start_char"],
            "end_char": locator["end_char"], "excerpt_sha256": metadata["text_sha256"],
            "page_text_sha256": page["text_sha256"], "continuation_pages": metadata.get("continuation_pages"),
            "page_model": source["page_model"], "purchased_model": source["purchased_model"],
            "applicability": metadata["applicability"],
        })
    prior_visual = read("care/visual-review.json")
    for p in prior_visual["pages"]:
        raw = (root / "care" / p["image_path"]).read_bytes()
        check("reused_care_render:" + str(p["page"]),
              sha(raw) == p["sha256"] and len(raw) == p["bytes"])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(ledger[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(ledger)
    (out / "source-delta.csv").write_bytes(stream.getvalue().encode("utf-8"))
    write("citation-checks.json", citation_rows)
    write("result.json", {
        "record_id": "DATA-R9-INTEGRITY-20261008-01a11628-90a402",
        "status": "PASS" if not failures else "FAIL", "checks": dict(checks),
        "base_commit": receipt["base_commit"], "audit_code_sha256": sha(Path(__file__).read_bytes()),
        "reused_pr246": {"status": old["status"], "unique_reviews": 238,
                         "producer_head": "6fd98c01b3c6f1abf4741df2130a485142eeeae4",
                         "new_excel_or_db_full_audit": False},
        "bundles": bundles, "source_count": len(all_sources),
        "development_review_count": len(reviews), "changed_sources": changed,
        "care_native_citations": len(care_sources), "manual_reference_citations": len(reference["sources"]),
        "actual_pdf_files": 5, "failures": failures, "model_calls": 0, "ocr_calls": 0,
        "network_calls": 0, "production_writes": 0,
        "scope": "Immutable input and citation integrity; not runtime/semantic/PM approval",
    })
    print(json.dumps({"status": "PASS" if not failures else "FAIL",
                      "checks": dict(checks), "failures": failures}, ensure_ascii=False))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
