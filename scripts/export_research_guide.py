"""Export actual manual excerpts or a separately labelled proposed-product draft; no model calls."""
import argparse
import json
from pathlib import Path

from lgax_core.guides import (
    build_concept_guide,
    build_official_guide,
    render_guide_html,
    render_guide_markdown,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--page-model")
    mode.add_argument("--concept-id")
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.concept_id) != bool(args.brief):
        parser.error("concept export requires --brief; official excerpts do not use a brief")
    inputs = {args.bundle.resolve()} | ({args.brief.resolve()} if args.brief else set())
    outputs = {kind: Path(str(args.output_prefix) + suffix) for kind, suffix in
               (("json", ".json"), ("markdown", ".md"), ("html", ".html"))}
    if any(path.resolve() in inputs for path in outputs.values()):
        parser.error("output must differ from input files")
    if not args.overwrite and any(path.exists() for path in outputs.values()):
        parser.error("output exists; select a new prefix or explicitly use --overwrite")
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    if args.page_model:
        guide = build_official_guide(bundle, args.page_model)
    else:
        brief = json.loads(args.brief.read_text(encoding="utf-8"))
        guide = build_concept_guide(bundle, brief, args.concept_id)
    contents = {"json": json.dumps(guide, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                "markdown": render_guide_markdown(guide), "html": render_guide_html(guide)}
    for kind, path in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents[kind], encoding="utf-8")
    print(json.dumps({"guide_kind": guide["guide_kind"], "sources": len(guide["sources"]),
                      "model_calls": 0, "outputs": {key: str(path) for key, path in outputs.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
