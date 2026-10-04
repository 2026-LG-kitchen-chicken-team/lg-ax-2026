"""Copy the PM-reviewed worker outside editable branches and verify its modules."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("worker.py", "process.py", "claude.py", "isolation.py", "artifacts.py")


def build(destination):
    output = Path(destination).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("the fixed worker runtime must live outside the editable repository")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for name in SOURCES:
        data = (ROOT / "services/automation" / name).read_bytes()
        (output / name).write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    entry = output / "worker_entry.py"
    entry.write_text('''import hashlib,json,pathlib,runpy,sys
root=pathlib.Path(__file__).resolve().parent
expected=json.loads(MANIFEST)
if any(hashlib.sha256((root/name).read_bytes()).hexdigest()!=value for name,value in expected.items()):
    raise SystemExit('fixed worker runtime changed; refuse execution')
sys.path.insert(0,str(root))
runpy.run_path(str(root/'worker.py'),run_name='__main__')
'''.replace("MANIFEST", repr(json.dumps(manifest))), encoding="utf-8")
    return {"worker_path": str(entry), "worker_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
            "dependency_manifest": manifest, "worker_authenticated": False, "automation_enabled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
