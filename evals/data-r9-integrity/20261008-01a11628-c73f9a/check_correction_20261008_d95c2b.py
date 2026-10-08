"""Bounded changed-field checks; previous 80/84 and review audits are not run."""
import json
from pathlib import Path

root = Path("/input")
out = Path("/output")


def load(name):
    return json.loads((root / name).read_text(encoding="utf-8"))


checks = []


def check(name, ok):
    checks.append({"name": name, "passed": bool(ok)})


old = load("old-sidecar.json")
new = load("new-sidecar.json")
check("review_and_QA_records_unchanged", old["reviews"] == new["reviews"] and old["qa"] == new["qa"])
check("manual_PDF_pins_unchanged", all((a["sha256"], a["bytes"], a["revision"]) == (b["sha256"], b["bytes"], b["revision"]) for a, b in zip(old["manuals"], new["manuals"])))
check("sidecar_version_changed", new["version"].endswith(".v2") and new["supersedes"]["commit"] == "913036481a01028959220f267b841a8338fbc895")
check("oven_exception_page_linked", new["manuals"][1]["page_references"][0]["related_pages"] == [4] and 4 in new["manuals"][1]["visual_pages"])
old_claims = {x["id"]: x for x in load("old-claims.json")["claims"]}
new_claims = {x["id"]: x for x in load("new-claims.json")["claims"]}
check("six_unaffected_claims_unchanged", all(old_claims[k] == new_claims[k] for k in old_claims if k not in {"K-INSTALL", "O-INSTALL"}))
check("only_two_claims_changed", {k for k in old_claims if old_claims[k] != new_claims[k]} == {"K-INSTALL", "O-INSTALL"})
correction = load("correction.json")
check("two_source_locations_recorded", len(correction["changes"]) == 2 and correction["changes"][0]["source"]["page"] == 26 and correction["changes"][1]["source"]["pages"] == [4, 11])
receipt = load("receiver-update.json")
check("receiver_status_bound_to_original_head", receipt["CORE_receiver"]["received_commit"] == "94f0800e30c4d653a07c32ed3b8f0dd2f793d44a" and len(receipt["CORE_receiver"]["files"]) == 13 and all(x["immutable_commit_bytes_match"] for x in receipt["CORE_receiver"]["files"]))
check("receipt_does_not_promote_new_head_or_PM", receipt["followup_corrections"]["new_head_CORE_ack"] == "not yet received" and receipt["other_stages"]["PM_date_topic_cohort_approval"] == "not received" and not receipt["other_stages"]["whole_task_done"])
chronology = load("purchase-edition.json")
identities = {x["original_review_id"]: x for x in load("identity-date-delta.json")["rows"]}
check("chronology_uses_existing_purchase_dates", all(r["displayed_purchase_date"] == identities[r["original_review_id"]]["displayed_purchase_date"] for r in chronology["rows"]))
check("two_newer_editions_four_unproven", sum(r["displayed_purchase_date"] < r["revision_label_date_interpretation"] for r in chronology["rows"]) == chronology["newer_than_purchase"] == 2 and chronology["chronologically_possible_but_unproven"] == 4)
check("no_purchase_or_edition_proofs_invented", chronology["purchase_sku_proofs"] == chronology["purchase_time_edition_proofs"] == 0 and all(r["actual_purchased_sku"] is None and not r["purchase_time_manual_confirmed"] for r in chronology["rows"]))
result = {"scope": "Changed installation notes, immutable-record boundaries, receiver-stage separation and purchase/edition chronology", "passed": sum(x["passed"] for x in checks), "failed": sum(not x["passed"] for x in checks), "checks": checks, "old_80_84_audits_rerun": False, "limitations": ["PDF bullet hierarchy and exception meaning were visually checked separately; assertions do not prove semantic correctness.", "The receiver's 13 hashes were compared to immutable Git bytes by the separate read-only receipt intake; this checker validates the resulting boundary record.", "No WEB receipt, new-head CORE acknowledgement, PM approval or operating result is inferred."]}
(out / "correction-check-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "failed": result["failed"]}))
raise SystemExit(bool(result["failed"]))
