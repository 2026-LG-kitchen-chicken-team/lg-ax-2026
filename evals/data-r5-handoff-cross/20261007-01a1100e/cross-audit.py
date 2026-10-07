"""Frozen public R5 handoff/lineage and approved saved-ranking cross-check.

No collector, production module, database, model or OCR is run. This separate
artifact preserves peer workspaces and originals. It publishes hashes/IDs only,
never copies public review text, private DOM, answers or credentials.
"""

import csv
import hashlib
import io
import json
import subprocess
import unicodedata
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "8ec1e8a51faabd6db032e52245680bef4229f93f"
PRODUCER = "0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d"
RETRIEVAL = "a26b6458118157fa0513218414f24abd6eae4b2a"
PEER217 = "9448c7995c0b5c57db54dd11a90796954fca88e6"
SOURCE = "data/research/r5-public-reviews-20261007/"
RAW = "evals/data-four-followup/20261006-01a10600/"
PREP = "evals/data003-compare/20261006-01a10834/prepared/"
checks, pins = [], {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(path, ref):
    raw = subprocess.check_output(["git", "show", ref + ":" + path], cwd=ROOT)
    pins[(ref, path)] = {"commit": ref, "path": path, "bytes": len(raw), "sha256": sha(raw)}
    return raw


def load(path, ref=PRODUCER):
    return json.loads(blob(path, ref))


def save(name, value):
    target = (OUT / name).resolve()
    if not target.is_relative_to(OUT):
        raise ValueError("audit output escapes unique folder")
    target.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def table(name, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k,v in row.items()})
    (OUT / name).write_bytes(stream.getvalue().encode())


def check(name, actual, expected):
    passed = actual == expected
    def logged(value):
        if isinstance(value, Fraction):
            return str(value)
        if isinstance(value, dict):
            return {k: logged(v) for k,v in value.items()}
        if isinstance(value, list):
            return [logged(v) for v in value]
        return value
    checks.append({"check": name, "actual": logged(actual), "expected": logged(expected), "passed": passed})
    if not passed:
        save("failed-checks.json", checks)
        raise ValueError(name)


def normalized_hash(text, form="NFKC"):
    return sha(" ".join(unicodedata.normalize(form, text).split()).encode())


# Verify immutable public files; do not treat the declared private SQLite hash
# as bytes available in Git or as database/API/restart validation.
file_checks = []
for folder in ("fixed18", "balanced-pilot-v2"):
    file_map = load(SOURCE + folder + "/files.json")
    for name, expected in file_map.items():
        path = SOURCE + folder + "/" + name
        if name.endswith(".sqlite3"):
            file_checks.append({"path": path, "expected_sha256": expected, "observed_sha256": None,
                                "status": "UNCONFIRMED", "reason": "private/generated database bytes not in supplied Git handoff"})
            continue
        observed = sha(blob(path, PRODUCER))
        check(path + " handoff bytes", observed, expected)
        file_checks.append({"path": path, "expected_sha256": expected, "observed_sha256": observed,
                            "status": "MATCH", "reason": "frozen public Git byte equality"})
table("file-handoff-review.csv", file_checks)

v1 = load(SOURCE + "fixed18/records.json")
v2 = load(SOURCE + "balanced-pilot-v2/records.json")
new = load(SOURCE + "balanced-pilot-v2/new_unique_records.json")
products = load(SOURCE + "fixed18/products.json")
m1 = load(SOURCE + "fixed18/manifest.json")
m2 = load(SOURCE + "balanced-pilot-v2/manifest.json")
check("v1 record count", len(v1), 179)
check("v2 record count", len(v2), 60)
check("v1 unique IDs", len({r["original_review_id"] for r in v1}), 179)
check("v2 unique IDs", len({r["original_review_id"] for r in v2}), 60)
old_ids = {r["original_review_id"] for r in v1}
check("v2 ID overlap", len(old_ids & {r["original_review_id"] for r in v2}), 1)
check("new59 exact original rows", new, [r for r in v2 if r["original_review_id"] not in old_ids])
combined = v1 + new
check("combined unique records", len({r["original_review_id"] for r in combined}), 238)
check("18 model pages", len(products), 18)
check("six model pages in each of three supplied categories", sorted(Counter(p["product_group"] for p in products).values()), [6,6,6])
check("v1 declared counts", dict(Counter(r["displayed_model_id"] for r in v1)), m1["model_page_row_counts"])
check("combined splits", dict(Counter(r["split"] for r in combined)), m2["collection"]["combined_split_counts"])
by_product = {p["model_id"]:p for p in products}

# Compare exported v2 records with the public sanitized DOM snapshots, not the
# unpublished raw DOM/capture files or independently confirmed buyer identity.
snapshots = {}
for r in v2:
    name = r["DOM_snapshot_location"]
    if name not in snapshots:
        snapshots[name] = load(SOURCE + "balanced-pilot-v2/" + name)
    snapshot = snapshots[name]
    matches = [x for x in snapshot["rows"] if str(x["id"]) == r["original_review_id"]]
    check(r["original_review_id"] + " public DOM row uniqueness", len(matches), 1)
    row = matches[0]
    check(r["original_review_id"] + " public DOM body", row["body"], r["text"])
    check(r["original_review_id"] + " public DOM fragment hash", sha(row["fragment"].encode()), r["public_message_DOM_fragment_sha256"])
    for field in ("rating", "purchase_date"):
        check(r["original_review_id"] + " public DOM " + field, row[field], r[field])
    check(r["original_review_id"] + " row MD", row["md"], r["review_row_MD"])
    check(r["original_review_id"] + " display page", snapshot["displayed_sku"], r["displayed_model_id"])
    check(r["original_review_id"] + " display MD", snapshot["displayed_md"], r["displayed_page_MD"])
check("snapshot rows observed", sum(len(s["rows"]) for s in snapshots.values()), 60)

public_review_rows = []
for r in combined:
    rid = r["original_review_id"]
    check(rid + " text UTF8 SHA", sha(r["text"].encode()), r["text_sha256"])
    check(rid + " actual SKU not inferred", r["actual_purchased_model_id"], None)
    check(rid + " posting date not inferred from purchase date", r["published_at"], None)
    check(rid + " model-input hold", r["eligible_for_model_input"], False)
    if r in v1:
        p = by_product[r["displayed_model_id"]]
        check(rid + " manual version provenance", r["manual_version"], p["manual_version"])
        check(rid + " reference document version provenance", r["document_version"], p["document_version"])
    public_review_rows.append({"original_review_id":rid,"displayed_model_id":r["displayed_model_id"],
        "original_source_version":"v1-fixed18" if rid in old_ids else "v2-new59",
        "text_sha256":r["text_sha256"],"source_url":r["source_url"],"source_locator":r["source_locator"],
        "manual_version":r["manual_version"],"purchase_date":r["purchase_date"],
        "confirmed_purchased_SKU":None,"confirmed_posting_date":None,"eligible_for_model_input":False,
        "declared_split":r["split"],"original_unredacted_bytes_independently_verified":False,
        "content_check":"public-export bytes/metadata; v2 public DOM comparison available",
        "private_original_verdict":"UNCONFIRMED"})
table("238-record-provenance-review.csv", public_review_rows)

split_names = ["development", "independent_evaluation", "demonstration"]
split_ids = {s:{r["original_review_id"] for r in combined if r["split"]==s} for s in split_names}
split_bodies = {s:{normalized_hash(r["text"]) for r in combined if r["split"]==s} for s in split_names}
intersections=[]
for i,a in enumerate(split_names):
    for b in split_names[i+1:]:
        ids=sorted(split_ids[a]&split_ids[b]); bodies=sorted(split_bodies[a]&split_bodies[b])
        check(a+"/"+b+" original ID overlap", len(ids), 0)
        check(a+"/"+b+" public NFKC body overlap", len(bodies), 0)
        intersections.append({"left":a,"right":b,"ID_overlap":ids,"public_normalized_body_overlap":bodies})

peer_path = "data/research/r5-public-independent-20261007/20261007T104222-01a10f51/review-audit.json"
old_observations = load(peer_path, PEER217)
known_exposure = []
for old in old_observations:
    if not old["development_exposure_known"]:
        continue
    matches=[r for r in combined if r["text_sha256"]==old["raw_body_UTF8_sha256"] or normalized_hash(r["text"],"NFC")==old["normalized_body_sha256"]]
    check(old["observation_id"]+" known old-body mapping", len(matches), 1)
    for r in matches:
        check(r["original_review_id"]+" prior development body outside evaluation", r["split"]=="independent_evaluation", False)
        known_exposure.append({"prior_observation":old["observation_id"],"prior_excerpt_ID":old["prior_excerpt_ID"],
            "matched_R5_ID":r["original_review_id"],"public_body_sha256":r["text_sha256"],"split":r["split"],
            "match_basis":"exact SHA or NFC-whitespace body SHA","known_prior_development_exposure":True})
check("known exposed groups mapped", len(known_exposure), 3)
save("past-exposure-cross-check.json", {"peer_head":PEER217,"matches":known_exposure,
    "scope":"three already documented development-exposed bodies only; not an exhaustive exposure clearance",
    "all_independent_evaluation_approved":False})

execution_dataset=load(SOURCE+"fixed18/development.dataset.json")
check("eligible execution review count", len(execution_dataset["reviews"]), 0)
check("validated execution pack evidence", len(execution_dataset["evidence"]), 21)
check("validated execution pack features", len(execution_dataset["features"]), 9)
save("R5-handoff-cross-result.json", {"producer_head":PRODUCER,"fixed_v1":179,"sidecar_v2":60,"overlap":1,"new_unique":59,
    "combined_unique":238,"model_pages":18,"splits":dict(Counter(r["split"] for r in combined)),
    "public_DOM_rows_compared":60,"public_file_hashes_verified":sum(r["status"]=="MATCH" for r in file_checks),
    "declared_database_bytes_verified":False,"actual_purchased_SKUs_confirmed":0,"posting_dates_confirmed":0,
    "admissible_model_input_reviews":0,"split_public_ID_and_body_intersections":intersections,
    "known_prior_exposure_mapped":known_exposure,"independence_or_Gold_approved":False,
    "sampling":"recommendation first10/model plus recent/low-rating first10; purposive research sample",
    "original_private_DOM_capture_verified":False,"new_collector_DB_Excel_model_OCR_calls":0})

# Approved post-measurement Gold correction. Preserve every original input/file,
# the legacy F10, rankings, model settings, repeat grouping and unlabelled cases.
authorities=json.loads((OUT/"github-authorities.json").read_bytes())
approval=next(c for c in authorities["approved_comments"] if c["id"]==6029600741)
check("approved Gold authority author", approval["author"], "jeongiryang")
approved_id="T876MEE1H1-MANUAL-F10-FOOD"
approved_sha="11212c8d4c0a986100451a8693f76ddc93b5a6de5b5b0ee2ecd502bb5cd48a5b"
check("approval contains exact ID and source hash", approved_id in approval["body"] and approved_sha in approval["body"], True)
raw_attempts=blob(RAW+"attempts.jsonl",RETRIEVAL)
attempts=[json.loads(line) for line in raw_attempts.splitlines()]
corpus=load(PREP+"model-corpus.json",RETRIEVAL)
queries=load(PREP+"model-queries.json",RETRIEVAL)
mapping=load(PREP+"question-evidence-map.json",RETRIEVAL)
execution=load(RAW+"execution.json",RETRIEVAL)
check("original corpus execution hash", sha(blob(PREP+"model-corpus.json",RETRIEVAL)), execution["model_corpus_sha256"])
check("original query execution hash", sha(blob(PREP+"model-queries.json",RETRIEVAL)), execution["model_queries_sha256"])
check("225 original attempts", len(attempts), 225)
check("225 unique original attempt IDs", len({r["attempt_id"] for r in attempts}), 225)
by_evidence={e["id"]:e for e in corpus}; by_query={q["id"]:q for q in queries}
check("approved source text UTF8 SHA",sha(by_evidence[approved_id]["text"].encode()),approved_sha)
check("legacy F10 is preserved", "T876MEE1H1-MANUAL-F10" in by_evidence, True)
gold={r["query_id"]:list(r["unchanged_old_gold_ids"]) for r in mapping["rows"] if r["ranking_metric_applicable"]}
legacy_FR01=list(gold["FR-01"]);gold["FR-01"]=[approved_id]
check("unique supported query denominator",len(gold),11)
groups=defaultdict(list); returned=0
for row in attempts:
    q=by_query[row["query_id"]]
    check(row["attempt_id"]+" requested scope", [row["requested_model"],row["requested_version"]], [q["model_id"],q["document_version"]])
    groups[(row["method"],row["query_id"])].append(row)
    for hit in row["top3"]:
        original=by_evidence[hit["id"]]
        check(row["attempt_id"]+"/"+hit["id"]+" source scope/text SHA",[hit["model_id"],hit["document_version"],hit["raw_text_sha256"]],
              [q["model_id"],q["document_version"],sha(original["text"].encode())])
        returned+=1
check("45 method/query groups",len(groups),45)
check("630 returned instances",returned,630)
metrics_rows=[]; attempt_score_rows=[]
for (method,qid),rows in groups.items():
    rows=sorted(rows,key=lambda r:r["repeat"])
    check(method+"/"+qid+" repeats",[r["repeat"] for r in rows],[1,2,3,4,5])
    ids=[[h["id"] for h in r["top3"]] for r in rows]
    check(method+"/"+qid+" stable saved rankings",all(x==ids[0] for x in ids),True)
    if qid not in gold:
        continue
    scores=[]
    for row,ranking in zip(rows,ids):
        selected=ranking if row["status"]=="success" else []
        relevant=set(gold[qid]);rank=next((i for i,eid in enumerate(selected[:3],1) if eid in relevant),None)
        values={"hit_at_1":Fraction(int(bool(selected) and selected[0] in relevant)),
                "recall_at_3":Fraction(len(set(selected[:3])&relevant),len(relevant)),
                "mrr_at_3":Fraction(1,rank) if rank else Fraction(0)}
        scores.append(values)
        attempt_score_rows.append({"original_attempt_id":row["attempt_id"],"method":method,"query_id":qid,"repeat":row["repeat"],
            "approved_gold_ids":gold[qid],"unchanged_top3":ranking,"original_status":row["status"],
            **{k:float(v) for k,v in values.items()},"new_search_model_calls":0})
    average={k:sum((s[k] for s in scores),Fraction(0))/5 for k in scores[0]}
    metrics_rows.append({"method":method,"query_id":qid,"gold_ids":gold[qid],"unchanged_top3":ids[0],
        "repeat_count":5,"first_relevant_rank":next((i for i,eid in enumerate(ids[0],1) if eid in set(gold[qid])),None),
        **{k:float(v) for k,v in average.items()},"exact_fractions":{k:str(v) for k,v in average.items()}})
table("approved11-per-query.csv",metrics_rows)
table("approved11-attempt-scores.csv",attempt_score_rows)
check("supported saved repetitions retained",len(attempt_score_rows),165)
methods=sorted({r["method"] for r in attempts})
summaries=[]
expected={"bm25_filtered":{"hit_at_1":Fraction(7,11),"recall_at_3":Fraction(19,22),"mrr_at_3":Fraction(25,33)},
          "bge_m3_filtered":{"hit_at_1":Fraction(7,11),"recall_at_3":Fraction(1),"mrr_at_3":Fraction(53,66)},
          "bge_m3_filtered_reranker":{"hit_at_1":Fraction(7,11),"recall_at_3":Fraction(10,11),"mrr_at_3":Fraction(25,33)}}
for method in methods:
    scores=[r for r in metrics_rows if r["method"]==method]
    check(method+" 11 unique questions",len(scores),11)
    values={k:sum((Fraction(r["exact_fractions"][k]) for r in scores),Fraction(0))/11 for k in expected[method]}
    check(method+" independent arithmetic expected",values,expected[method])
    summaries.append({"method":method,"denominator_unique_queries":11,
                      **{k:float(v) for k,v in values.items()},"exact_fractions":{k:str(v) for k,v in values.items()},
                      "FR01_rank":next(r["first_relevant_rank"] for r in scores if r["query_id"]=="FR-01"),
                      "post_measurement_Gold_correction":True,"independent_final_evaluation":False})
save("approved11-summary.json",{"approval":approval,"source_PR200_head":RETRIEVAL,"original_225_sha256":sha(raw_attempts),
    "Gold_version":"PM-FR01-corrected-20261007-offline-v1","legacy_FR01_Gold_preserved":legacy_FR01,
    "FR01_only_new_Gold":gold["FR-01"],"other_10_Gold_changed":False,"unique_question_denominator":11,
    "failure_rule":"each failed saved repeat contributes zero; none dropped; five repeats reduced within each unique question",
    "failed_original_attempts":sum(r["status"]!="success" for r in attempts),"methods":summaries,
    "new_model_search_OCR_calls":0,"source_quality_scope":"public authored development questions; post-measurement Gold correction; not heldout performance"})
unlabelled=[]
for row in mapping["rows"]:
    if row["ranking_metric_applicable"]:
        continue
    saved=[r for r in attempts if r["query_id"]==row["query_id"]]
    unlabelled.append({"query_id":row["query_id"],"expected_disposition":row["expected_response"],"saved_retrieval_attempts":len(saved),
        "empty_rankings":sum(not r["top3"] for r in saved),"observed_actual_AI_answer":None,"semantic_verdict":"UNCONFIRMED",
        "reason":"saved rankings/policy status do not supply an AI answer/hold/clarification result"})
check("unlabelled cases excluded from ranking quality",len(unlabelled),4)
table("no-gold-semantic-pending.csv",unlabelled)
save("automatic-table-status.json",{"source_main":BASE,"producer_graph_received":False,"approved_adapter_received":False,
    "inspected_paths":["packages/core","packages/contracts","services","data"],"actual_structure_fields_found":[],
    "existing_manual_questions":144,"manual_questions_are_auto_performance_samples":False,"automatic_accuracy":None,"automatic_error_count":None,
    "verdict":"UNVERIFIABLE_MISSING_AUTOMATIC_OUTPUT","new_model_OCR_calls":0,
    "required_next_owner":"PM fixes producer/adapter ownership and existing/future fixed artifact; DATA checks original cells; CORE checks canonical binding"})

save("source-pins.json",{"producer_head":PRODUCER,"retrieval_head":RETRIEVAL,"peer217_head":PEER217,"files":list(pins.values())})
save("verification.json",{"checks":checks,"all_passed":all(c["passed"] for c in checks),"scope":"public handoff/capture consistency and approved frozen-ranking arithmetic",
    "independence_Gold_operating_approved":False,"private_DOM_or_DB_bytes_verified":False,"models_search_OCR_collector_calls":0})
print(json.dumps({"R5_unique":238,"public_DOM_rows":60,"known_exposed_groups":3,"approved_queries":11,"saved_attempts_reused":225,"supported_repeats":165,
    "automatic_table_status":"unverifiable","new_model_OCR_calls":0,"methods":summaries},ensure_ascii=False))
