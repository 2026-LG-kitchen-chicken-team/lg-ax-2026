"""Rebuild a public research landing from pinned JSON, without network or models."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from lgax_contracts.research import validate_research_bundle
from lgax_core.public_review_collection import save_landing_db


def load_profile(profile, root=None):
    root = root or Path(__file__).resolve().parents[1]
    source = root / "data/research/r8-public-research-20261007" if profile == "r8" else root / "data/research/r5-public-reviews-20261007" / profile
    hashes = json.loads((source / "files.json").read_bytes())
    values = {}
    names = ["records.json", "products.json", "manifest.json"]
    if profile == "r8":
        names += ["official-sources.json"] + sorted(name for name in hashes if name.startswith("bundles/"))
    for name in names:
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[name]:
            raise ValueError("Pinned public research JSON changed.")
        values[name] = json.loads(raw)
        if name.startswith("bundles/"):
            validate_research_bundle(values[name])
    return values, hashes


def build_db(profile, output, root=None):
    values, hashes = load_profile(profile, root)
    if output.exists():
        raise ValueError("Research DB output already exists; choose a new output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    save_landing_db(output, records=values["records.json"], products=values["products.json"],
                    manifest=values["manifest.json"])
    if profile == "r8":
        with closing(sqlite3.connect(output)) as db, db:
            db.executescript("""
                CREATE TABLE research_sources (source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL,
                    product_group TEXT NOT NULL, metadata_json TEXT NOT NULL);
                CREATE TABLE research_bundles (bundle_id TEXT PRIMARY KEY, product_group TEXT NOT NULL,
                    metadata_json TEXT NOT NULL);
            """)
            db.executemany("INSERT INTO research_sources VALUES (?, ?, ?, ?)",
                           [(s["source_id"], s["source_type"], s["product_group"], json.dumps(s, ensure_ascii=False, sort_keys=True))
                            for s in values["official-sources.json"]])
            db.executemany("INSERT INTO research_bundles VALUES (?, ?, ?)",
                           [(b["bundle_id"], b["product_group"], json.dumps(b, ensure_ascii=False, sort_keys=True))
                            for name, b in values.items() if name.startswith("bundles/")])
    with closing(sqlite3.connect(output.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM reviews ORDER BY original_review_id")]
        products = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM products ORDER BY model_id")]
        manifest = json.loads(db.execute("SELECT value_json FROM manifest WHERE key='collection'").fetchone()[0])
        if profile == "r8":
            sources = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM research_sources ORDER BY source_id")]
            bundles = [json.loads(row[0]) for row in db.execute("SELECT metadata_json FROM research_bundles ORDER BY bundle_id")]
            assert sources == sorted(values["official-sources.json"], key=lambda row: row["source_id"])
            assert bundles == sorted((b for name, b in values.items() if name.startswith("bundles/")), key=lambda b: b["bundle_id"])
    assert rows == sorted(values["records.json"], key=lambda row: row["original_review_id"])
    assert products == sorted(values["products.json"], key=lambda row: row["model_id"])
    assert manifest == values["manifest.json"]
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    expected = hashes.get("public-reviews.sqlite3")
    return {"profile": profile, "reviews": len(rows), "products": len(products),
            "sha256": digest, "expected_artifact_sha256": expected,
            "byte_exact": digest == expected if expected else None, "json_rows_equal": True,
            "official_sources": len(values.get("official-sources.json", [])),
            "research_bundles": sum(name.startswith("bundles/") for name in values),
            "model_calls": 0, "network_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pilot1", "fixed18", "r8"), default="fixed18")
    parser.add_argument("--output", type=Path, required=True, help="New local research DB; existing files are preserved.")
    args = parser.parse_args()
    try:
        result = build_db(args.profile, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
