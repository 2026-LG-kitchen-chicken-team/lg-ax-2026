"""Rebuild a public research landing from pinned JSON, without network or models."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from lgax_core.public_review_collection import save_landing_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pilot1", "fixed18"), default="fixed18")
    parser.add_argument("--output", type=Path, required=True, help="New local research DB; existing files are preserved.")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "data/research/r5-public-reviews-20261007" / args.profile
    hashes = json.loads((source / "files.json").read_bytes())
    values = {}
    for name in ("records.json", "products.json", "manifest.json"):
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[name]:
            parser.error("Pinned public research JSON changed.")
        values[name] = json.loads(raw)
    if args.output.exists():
        parser.error("Research DB output already exists; choose a new output path.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_landing_db(args.output, records=values["records.json"], products=values["products.json"],
                    manifest=values["manifest.json"])
    with sqlite3.connect(args.output.resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM reviews ORDER BY original_review_id")]
        products = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM products ORDER BY model_id")]
        manifest = json.loads(db.execute("SELECT value_json FROM manifest WHERE key='collection'").fetchone()[0])
    assert rows == sorted(values["records.json"], key=lambda row: row["original_review_id"])
    assert products == sorted(values["products.json"], key=lambda row: row["model_id"])
    assert manifest == values["manifest.json"]
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"profile": args.profile, "reviews": len(rows), "products": len(products),
                      "sha256": digest, "expected_artifact_sha256": hashes["public-reviews.sqlite3"],
                      "byte_exact": digest == hashes["public-reviews.sqlite3"], "json_rows_equal": True,
                      "model_calls": 0, "network_requests": 0}))


if __name__ == "__main__":
    main()
