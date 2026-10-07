"""Compare a received, fixed R5 packet with saved DB/API/restart captures.

Only files are read. No network, producer, repository module, model or OCR is
executed. This audit wrapper is separate from the canonical product schema.
MATCH describes capture content consistency, never PM approval/runtime origin.
"""

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

FORMAT = "data13-r5-consumer-v1"
FIELDS = ["id", "model_id", "text", "source_kind", "document_version", "source_id", "row", "evidence_id"]
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
INSPECTED_CONTRACT_COMMIT = "8b41fd4785bc149593f04d913ef974f29fb341fe"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def same(a, b):
    # Python's bool==int must not make forged numeric/identity fields pass.
    return json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)


def pointer(value, path):
    if path == "":
        return value
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("JSON pointer must be empty or start with /")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


class Audit:
    def __init__(self, manifest_path):
        self.manifest_path = Path(manifest_path).resolve()
        self.root = self.manifest_path.parent
        self.packet = json.loads(self.manifest_path.read_bytes())
        self.rows = []
        self.files = {}
        self.datasets = []
        self.evidence = {}
        self.review_ids = set()
        self.scopes = set()

    def row(self, subject, check, status, reason="", expected=None, observed=None):
        self.rows.append({"subject": subject, "check": check, "status": status, "reason": reason,
                          "expected": expected, "observed": observed})

    def compare(self, subject, check, actual, expected):
        self.row(subject, check, "MATCH" if same(actual, expected) else "MISMATCH", "", expected, actual)

    def required(self, subject, check, value):
        if value is None or value == "" or value == []:
            self.row(subject, check, "UNCONFIRMED", "required input/capture not supplied")
            return False
        return True

    def file(self, name):
        if not isinstance(name, str) or name not in self.files:
            raise ValueError("file is not in the verified input manifest")
        return self.files[name]

    def node(self, ref):
        if not isinstance(ref, dict):
            raise ValueError("capture/reference not supplied")
        value = pointer(json.loads(self.file(ref["file"])), ref.get("pointer", ""))
        if ref.get("decode_json_string") is True:
            if not isinstance(value, str):
                raise ValueError("DB JSON string selector points to non-string")
            value = json.loads(value)
        return value

    def attempt(self, subject, check, function):
        try:
            return function()
        except (OSError, ValueError, KeyError, IndexError, TypeError, UnicodeError, csv.Error) as error:
            self.row(subject, check, "UNCONFIRMED", type(error).__name__ + ": " + str(error))
            return None

    def verify_files(self):
        for item in self.packet.get("files", []):
            name = item.get("path")
            try:
                path = (self.root / name).resolve()
                if not path.is_relative_to(self.root) or path == self.manifest_path:
                    raise ValueError("file reference escapes packet root or self-references")
                if not SHA.fullmatch(item.get("sha256", "")):
                    raise ValueError("missing/invalid original file SHA")
                if name in self.files:
                    raise ValueError("duplicate file path")
                if path.stat().st_size > 64 * 1024 * 1024:
                    raise ValueError("file exceeds bounded 64 MiB audit limit")
                raw = path.read_bytes()
                self.compare(name, "file bytes SHA256", digest(raw), item["sha256"])
                if digest(raw) == item["sha256"]:
                    self.files[name] = raw
            except (OSError, ValueError, TypeError) as error:
                self.row(str(name), "file manifest", "MISMATCH", str(error))

    def index_dataset(self, did, dataset):
        if not isinstance(dataset, dict):
            raise ValueError("expected dataset must be an object")
        self.compare(did, "expected dataset version", dataset.get("dataset_version"), self.packet["dataset_version"])
        for collection in ("products", "reviews", "features", "evidence"):
            if not isinstance(dataset.get(collection), list):
                raise ValueError("expected dataset lacks collection " + collection)
        self.datasets.append(dataset)
        for review in dataset["reviews"]:
            rid = review["id"]
            if rid in self.review_ids:
                self.row(rid, "globally unique storage review ID", "MISMATCH", "duplicate review ID across original documents")
            self.review_ids.add(rid)
        for evidence in dataset["evidence"]:
            eid = evidence["id"]
            if eid in self.evidence:
                self.row(eid, "globally unique evidence ID", "MISMATCH", "duplicate expected ID")
            self.evidence[eid] = evidence
            self.scopes.add((evidence["model_id"], evidence["document_version"]))

    def csv_source(self, did, raw, dataset, origins):
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        self.compare(did, "source CSV columns", next(reader), FIELDS)
        actual_reviews, actual_evidence, actual_origins = [], [], []
        while True:
            start = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if len(values) != len(FIELDS):
                raise ValueError("CSV row length differs from original eight-column contract")
            source = dict(zip(FIELDS, values))
            self.compare(source["id"], "physical source row", source["row"], str(start))
            review = {k: v for k, v in source.items() if k != "row"}
            review["locator"] = {"row": start}
            evidence = {k: review[k] for k in ("model_id", "document_version", "source_kind", "source_id", "locator", "text")}
            evidence.update(id=review["evidence_id"], source_type="review", feature_ids=[])
            origin = {"evidence_id": evidence["id"], "source_id": evidence["source_id"],
                      "document_version": evidence["document_version"], "source_kind": evidence["source_kind"],
                      "sha256": digest(raw), "row": start, "end_row": reader.line_num,
                      "text_sha256": digest(evidence["text"].encode("utf-8")),
                      "original_role": "uploaded_review_csv", "parser": "stdlib.csv"}
            actual_reviews.append(review)
            actual_evidence.append(evidence)
            actual_origins.append(origin)
        if not actual_reviews:
            raise ValueError("empty original CSV is not a received pilot")
        self.compare(did, "source CSV -> expected reviews", dataset["reviews"], actual_reviews)
        self.compare(did, "source CSV -> expected evidence", dataset["evidence"], actual_evidence)
        self.compare(did, "source CSV -> expected origins", origins, actual_origins)

    def pdf_source(self, did, raw, dataset, origins):
        # Independent native text-layer read, not OCR/layout extraction.
        self.compare(did, "registered manual PDF has no invented reviews", dataset["reviews"], [])
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError("pypdf unavailable; PDF original range remains unconfirmed") from error
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 200:
            raise ValueError("PDF is encrypted or exceeds bounded page count")
        evidence = {e["id"]: e for e in dataset["evidence"]}
        if len(origins) != len(evidence):
            raise ValueError("PDF origins do not cover expected evidence")
        pages = {}
        for origin in origins:
            eid, page = origin["evidence_id"], origin["page"]
            if type(page) is not int or not 1 <= page <= len(reader.pages):
                raise ValueError("PDF physical page invalid")
            if page not in pages:
                pages[page] = reader.pages[page - 1].extract_text() or ""
            start, end = origin["start_char"], origin["end_char"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(pages[page]):
                raise ValueError("PDF source character range invalid")
            self.compare(eid, "PDF original SHA", origin.get("sha256"), digest(raw))
            self.compare(eid, "PDF native source range", evidence[eid]["text"], pages[page][start:end])
            self.compare(eid, "PDF native UTF8 text SHA", origin.get("text_sha256"), digest(evidence[eid]["text"].encode()))

    def document(self, spec):
        did = spec["document_id"]
        source = self.file(spec["source_file"])
        dataset = self.node(spec["expected_dataset_ref"])
        origins = self.node(spec["expected_origins_ref"])
        self.index_dataset(did, dataset)
        kind = spec["kind"]
        if kind == "review_csv":
            self.csv_source(did, source, dataset, origins)
        elif kind == "pdf":
            self.pdf_source(did, source, dataset, origins)
        else:
            raise ValueError("only review_csv/pdf document preservation is in scope")
        before_after = []
        for phase in ("before", "after"):
            for operation, path in (("metadata", "/api/documents/" + did), ("original", "/api/documents/" + did + "/original")):
                request = spec.get(operation + "_" + phase + "_request")
                if self.required(did, phase + " " + operation + " GET request metadata", request):
                    self.compare(did, phase + " " + operation + " request method", request.get("method"), "GET")
                    self.compare(did, phase + " " + operation + " request path", request.get("path"), path)
                status = spec.get(operation + "_" + phase + "_http_status")
                if self.required(did, phase + " " + operation + " HTTP status", status):
                    self.compare(did, phase + " " + operation + " HTTP status", status, 200)
            db = self.attempt(did, phase + " DB record input", lambda p=phase: self.node(spec["stored_" + p + "_ref"]))
            response = self.attempt(did, phase + " metadata GET input", lambda p=phase: self.node(spec["metadata_" + p + "_ref"]))
            raw = self.attempt(did, phase + " original GET input", lambda p=phase: self.file(spec["original_" + p + "_file"]))
            record = None
            if response is not None:
                self.compare(did, phase + " metadata envelope ok", response.get("ok"), True)
                record = response.get("data")
            for label, value in (("DB", db), ("API", record)):
                if not isinstance(value, dict):
                    self.row(did, phase + " " + label + " stored record", "UNCONFIRMED", "record not provided as JSON object")
                    continue
                for field, expected in (("document_id", did), ("sha256", digest(source)), ("dataset", dataset), ("origins", origins)):
                    self.compare(did, phase + " " + label + " " + field, value.get(field), expected)
                if kind == "review_csv":
                    self.compare(did, phase + " " + label + " review count", value.get("review_count"), len(dataset["reviews"]))
            if raw is not None:
                self.compare(did, phase + " original bytes SHA", digest(raw), digest(source))
            if db is not None and record is not None:
                # Registration idempotent flags are not a read-preservation field.
                db_core = {k: v for k, v in db.items() if k != "idempotent"}
                api_core = {k: v for k, v in record.items() if k != "idempotent"}
                self.compare(did, phase + " DB vs API metadata", api_core, db_core)
                before_after.append(db_core)
        if len(before_after) == 2:
            self.compare(did, "restart DB semantic record equality", before_after[1], before_after[0])

    def capture(self, capture):
        cid = capture["id"]
        if capture.get("phase") not in {"before", "after"}:
            raise ValueError("capture phase is not before/after")
        if capture.get("server_profile") not in {"documents", "public_api"}:
            raise ValueError("server profile not supplied")
        request = capture["request"]
        self.compare(cid, "read-only request method", request.get("method"), "GET")
        response = self.node(capture["response_ref"])
        kind = capture["kind"]
        if kind == "evidence":
            eid = capture["expected_evidence_id"]
            self.compare(cid, "canonical ID GET route", request.get("path"), "/api/evidence/" + eid)
            self.compare(cid, "evidence HTTP status", capture["http_status"], 200)
            self.compare(cid, "evidence envelope ok", response.get("ok"), True)
            self.compare(cid, "evidence contract version", response["data"].get("contract_version"), "0.1.0")
            if eid not in self.evidence:
                raise ValueError("expected evidence ID is outside received source datasets")
            self.compare(cid, "evidence entire canonical content", response["data"].get("evidence"), self.evidence[eid])
            return
        if kind != "search":
            raise ValueError("aggregate/planning/model captures are outside this #13 audit")
        self.compare(cid, "scoped search route", request.get("path"), "/api/evidence/search")
        params = request["params"]
        for name in ("q", "model_id", "document_version"):
            if not isinstance(params.get(name), str) or not params[name]:
                raise ValueError("scoped search needs explicit q/model/version")
        case_id = capture["case_id"]
        if case_id not in {"selected-model", "other-valid-model", "invalid-model", "invalid-version"}:
            raise ValueError("unknown scope scenario")
        expected_errors = {"invalid-model": "INVALID_MODEL_ID", "invalid-version": "INVALID_DOCUMENT_VERSION"}
        self.compare(cid, "scenario expectation", capture.get("expect"), "error" if case_id in expected_errors else "success")
        if case_id in expected_errors:
            self.compare(cid, "scenario required error", capture.get("expected_error_code"), expected_errors[case_id])
            known_models = {m for m, _ in self.scopes}
            if case_id == "invalid-model":
                self.compare(cid, "invalid model is outside received full scope", params["model_id"] in known_models, False)
            else:
                self.compare(cid, "invalid version uses a known model", params["model_id"] in known_models, True)
                self.compare(cid, "invalid version is outside known model/version scope", (params["model_id"], params["document_version"]) in self.scopes, False)
        else:
            self.compare(cid, "positive query has a received original scope", (params["model_id"], params["document_version"]) in self.scopes, True)
            if case_id == "other-valid-model":
                selected_models = {c.get("request", {}).get("params", {}).get("model_id") for c in self.packet["captures"] if c.get("case_id") == "selected-model"}
                self.compare(cid, "other model is different from selected model", params["model_id"] in selected_models, False)
        if capture["expect"] == "error":
            code = capture["expected_error_code"]
            if code not in {"INVALID_MODEL_ID", "INVALID_DOCUMENT_VERSION"}:
                raise ValueError("error is not an inspected HTTP scope contract")
            profile = capture["server_profile"]
            if profile not in {"documents", "public_api"}:
                raise ValueError("unknown server profile; status cannot be scored")
            expected_status = 400 if profile == "documents" and code == "INVALID_DOCUMENT_VERSION" else 404
            self.compare(cid, "scope HTTP status for server profile", capture["http_status"], expected_status)
            self.compare(cid, "scope error envelope", response.get("ok"), False)
            self.compare(cid, "scope error code", response["error"].get("code"), code)
            return
        if capture["expect"] != "success":
            raise ValueError("capture expectation must be success or error")
        self.compare(cid, "search HTTP status", capture["http_status"], 200)
        self.compare(cid, "search envelope", response.get("ok"), True)
        data = response["data"]
        for field in ("model_id", "document_version"):
            self.compare(cid, "echoed " + field, data.get(field), params[field])
        self.compare(cid, "echoed query", data.get("query"), params["q"])
        self.compare(cid, "current API method name", data.get("search_method"), "literal_token_count")
        self.compare(cid, "search contract version", data.get("contract_version"), "0.1.0")
        items = data["items"]
        if not isinstance(items, list) or type(data.get("total")) is not int or data["total"] < len(items):
            raise ValueError("search total/items have incorrect types or bounds")
        if not items:
            self.row(cid, "positive scope control", "UNCONFIRMED", "empty positive result does not show original retrieval/identity")
        ids = [e["id"] for e in items]
        self.compare(cid, "unique search result IDs", len(set(ids)), len(ids))
        for item in items:
            self.compare(cid, item["id"] + " selected model", item.get("model_id"), params["model_id"])
            self.compare(cid, item["id"] + " selected document version", item.get("document_version"), params["document_version"])
            if item["id"] not in self.evidence:
                raise ValueError("returned ID lacks an original in the supplied full scope")
            self.compare(cid, item["id"] + " original canonical evidence", item, self.evidence[item["id"]])

    def run(self):
        p = self.packet
        self.compare("packet", "audit wrapper format", p.get("audit_input_format"), FORMAT)
        pins_ready = True
        for field in ("producer_commit", "consumer_commit"):
            value = p.get(field)
            if not self.required("packet", field, value):
                pins_ready = False
            elif not isinstance(value, str) or not COMMIT.fullmatch(value):
                self.row("packet", field, "MISMATCH", "not an exact Git commit")
                pins_ready = False
        if not self.required("packet", "R5 dataset version", p.get("dataset_version")):
            pins_ready = False
        elif not isinstance(p["dataset_version"], str):
            self.row("packet", "R5 dataset version", "MISMATCH", "not a version string")
            pins_ready = False
        self.verify_files()
        documents = p.get("documents", [])
        captures = p.get("captures", [])
        self.required("packet", "actual registered document list", documents)
        self.required("packet", "actual saved evidence/scope captures", captures)
        if pins_ready:
            doc_ids = [d.get("document_id") for d in documents]
            self.compare("packet", "unique document IDs", len(set(doc_ids)), len(doc_ids))
            for doc in documents:
                self.attempt(str(doc.get("document_id")), "document/source inputs", lambda d=doc: self.document(d))
            capture_ids = [c.get("id") for c in captures]
            self.compare("packet", "unique capture IDs", len(set(capture_ids)), len(capture_ids))
            for capture in captures:
                self.attempt(str(capture.get("id")), "saved capture inputs", lambda c=capture: self.capture(c))
            for eid in self.evidence:
                for phase in ("before", "after"):
                    matches = [c for c in captures if c.get("kind") == "evidence" and c.get("expected_evidence_id") == eid and c.get("phase") == phase]
                    if len(matches) != 1:
                        self.row(eid, phase + " exactly one ID GET", "UNCONFIRMED", "missing or ambiguous evidence capture pair")
            for case_id in ("selected-model", "other-valid-model", "invalid-model", "invalid-version"):
                for phase in ("before", "after"):
                    matches = [c for c in captures if c.get("kind") == "search" and c.get("case_id") == case_id and c.get("phase") == phase]
                    if len(matches) != 1:
                        self.row(case_id, phase + " scope GET pair", "UNCONFIRMED", "required scenario capture not supplied")
            for cap in captures:
                if cap.get("kind") == "search" and cap.get("phase") == "before":
                    peers = [c for c in captures if c.get("kind") == "search" and c.get("case_id") == cap.get("case_id") and c.get("phase") == "after"]
                    if len(peers) == 1:
                        other = peers[0]
                        self.compare(cap["case_id"], "restart exact request scope", other.get("request"), cap.get("request"))
                        self.compare(cap["case_id"], "restart status", other.get("http_status"), cap.get("http_status"))
                        self.attempt(cap["case_id"], "restart search content", lambda a=cap,b=other: self.compare(a["case_id"], "restart search payload", self.node(b["response_ref"]), self.node(a["response_ref"])))
        receipt = p.get("restart_receipt_file")
        if self.required("packet", "PM restart/DB-scope receipt", receipt):
            self.attempt("packet", "restart receipt bytes", lambda: self.file(receipt))
        status = "MISMATCH" if any(r["status"] == "MISMATCH" for r in self.rows) else "UNCONFIRMED" if any(r["status"] == "UNCONFIRMED" for r in self.rows) else "MATCH"
        return {"status": status, "comparison_kind": "provided_file_DB_API_content_consistency_only",
                "input_role": p.get("input_role", "received_packet"), "producer_commit": p.get("producer_commit"),
                "consumer_commit": p.get("consumer_commit"), "dataset_version": p.get("dataset_version"),
                "inspected_contract_commit": INSPECTED_CONTRACT_COMMIT,
                "consumer_contract_compatibility_verified": False,
                "declared_documents": len(documents), "declared_captures": len(captures),
                "expected_evidence_count": len(self.evidence), "verified_input_files": len(self.files),
                "operating_origin_verified": False, "pm_approval_verified": False,
                "new_network_requests": 0, "new_model_calls": 0, "new_OCR_calls": 0,
                "runtime_restart_calls": 0, "rows": self.rows}


def write_result(result, output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory is not empty; original reports will not be overwritten")
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["subject", "check", "status", "reason", "expected", "observed"], lineterminator="\n")
    writer.writeheader()
    for row in result["rows"]:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k,v in row.items()})
    (output / "comparison.csv").write_bytes(stream.getvalue().encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = Audit(args.packet).run()
    write_result(result, args.output)
    print(json.dumps({k:v for k,v in result.items() if k != "rows"}, ensure_ascii=False))
    return {"MATCH": 0, "MISMATCH": 1, "UNCONFIRMED": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
