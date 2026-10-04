"""Build a fixed external report hook; do not run teammate branch code as publisher."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["scripts/project_report.py", "scripts/project_report_common.py", "harness/phase2/project-reports.policy.json"]


def build(destination):
    output = Path(destination).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("the trusted hook must live outside the editable repository")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for relative in SOURCES:
        data = (ROOT / relative).read_bytes()
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest[relative] = hashlib.sha256(data).hexdigest()
    entry = output / "report_entry.py"
    program = """import hashlib,json,pathlib,runpy,sys
root=pathlib.Path(__file__).resolve().parent
expected=json.loads(MANIFEST)
if any(hashlib.sha256((root/name).read_bytes()).hexdigest()!=value for name,value in expected.items()):
    raise SystemExit('fixed report bundle changed; refuse authenticated reporting')
sys.path.insert(0,str(root/'scripts'))
runpy.run_path(str(root/'scripts/project_report.py'),run_name='__main__')
""".replace("MANIFEST", repr(json.dumps(manifest)))
    entry.write_text(program, encoding="utf-8")
    return {"trusted_report_script": str(entry), "trusted_report_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
            "dependency_manifest": manifest, "worker_authenticated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
