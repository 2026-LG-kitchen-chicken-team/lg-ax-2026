"""Verify exact published research file bytes, without credentials or network."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    raw_manifest = (args.pack / "manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    seen = set()
    for entry in manifest["files"]:
        name = entry["path"]
        assert Path(name).name == name and name not in seen
        seen.add(name)
        path = args.pack / name
        assert path.is_file() and not path.is_symlink()
        raw = path.read_bytes()
        assert len(raw) == entry["bytes"], name
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"], name
        assert b"\r\n" not in raw, (name, "LF source bytes required")
    assert seen == {p.name for p in args.pack.iterdir() if p.is_file() and p.name != "manifest.json"}
    assert not manifest["parent_done"]
    result = {
        "status": "PASS", "scope": "new D3 exact manifest/file bytes",
        "verified_files": len(seen),
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "network_requests": 0, "model_calls": 0,
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
