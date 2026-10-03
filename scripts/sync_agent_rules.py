"""Copy or verify identical root instructions for Codex and Claude."""

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Verify byte equality (default).")
    mode.add_argument("--write", action="store_true", help="Copy AGENTS.md to CLAUDE.md.")
    args = parser.parse_args()
    source = ROOT / "AGENTS.md"
    target = ROOT / "CLAUDE.md"
    if not source.is_file():
        print("FAIL: AGENTS.md is missing")
        return 1
    if args.write:
        target.write_bytes(source.read_bytes())
    if not target.is_file():
        print("FAIL: CLAUDE.md is missing")
        return 1
    if source.read_bytes() != target.read_bytes():
        print("FAIL: AGENTS.md and CLAUDE.md differ; review and synchronize both")
        return 1
    print("PASS: AGENTS.md and CLAUDE.md are byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
