"""Compare every original tracked file to its fixed Git blob without editing it."""
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
GIT = ["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false"]
raw_tree = subprocess.run(GIT + ["ls-tree", "-r", "-z", SOURCE], cwd=ROOT, capture_output=True, check=True).stdout
count, total_bytes = 0, 0
diffs = []
for record in raw_tree.split(b"\0"):
    if not record:
        continue
    metadata, name = record.split(b"\t", 1)
    mode, kind, blob = metadata.split()
    if kind != b"blob":
        continue
    relative = name.decode("utf-8")
    raw = (ROOT / relative).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    count += 1
    total_bytes += len(raw)
    if actual != blob.decode("ascii"):
        diffs.append({"path": relative, "expected_git_blob": blob.decode("ascii"), "actual_raw_git_blob": actual})
result = {"record_id": "DATA-DISH-MANUAL-01a1100e", "source_commit": SOURCE,
          "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
          "original_tracked_file_count": count, "original_bytes_read": total_bytes,
          "all_original_raw_bytes_match_fixed_git_blobs": not diffs, "mismatch_count": len(diffs), "mismatches": diffs,
          "comparison": "raw bytes hashed as Git blob identity; not checkout-filter-normalized",
          "model_calls": 0, "ocr_runs": 0}
(OUT / "original-preservation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
manifest = []
for path in sorted(OUT.rglob("*")):
    if path.is_file() and path.name != "file-manifest.json":
        raw = path.read_bytes()
        manifest.append({"path": path.relative_to(OUT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
(OUT / "file-manifest.json").write_text(json.dumps({"record_id": result["record_id"], "files": manifest,
                                                   "manifest_self_excluded": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"original_files": count, "raw_byte_mismatches": len(diffs), "original_bytes_read": total_bytes,
                  "audit_manifest_files": len(manifest)}, ensure_ascii=False))
if diffs:
    raise SystemExit(1)
