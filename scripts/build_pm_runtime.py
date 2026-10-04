"""Deploy a hash-checked PM/Worker runtime outside editable repository files."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["scripts/automation_pm.py", "scripts/automation_isolation.py"] + [
    "services/automation/" + name for name in (
        "__init__.py", "pm.py", "pm_broker.py", "github_bridge.py", "state.py", "worker.py",
        "process.py", "claude.py", "artifacts.py", "isolation.py")]


def build(destination):
    output = Path(destination).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("fixed PM runtime must live outside the editable repository")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for name in FILES:
        data = (ROOT / name).read_bytes()
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    entry = output / "pm_entry.py"
    entry.write_text('''import hashlib,json,pathlib,runpy,sys
root=pathlib.Path(__file__).resolve().parent
expected=json.loads(MANIFEST)
if any(hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest for name,digest in expected.items()):
    raise SystemExit('fixed PM runtime changed; refuse execution')
sys.path.insert(0,str(root))
runpy.run_path(str(root/'scripts/automation_pm.py'),run_name='__main__')
'''.replace("MANIFEST", repr(json.dumps(manifest))), encoding="utf-8")
    return {"entry_path": str(entry), "entry_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
            "dependency_manifest": manifest, "automation_enabled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output)))
