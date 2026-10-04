"""Opt-in loopback verification endpoint for the existing synthetic review transport."""

import argparse
import json
import secrets
from pathlib import Path

import uvicorn

from .documents_server import create_app
from .review_csv import ReviewCsvRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    if not args.token_file.exists():
        args.token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    repository = ReviewCsvRepository(args.directory, json.loads(args.dataset.read_text("utf-8")))
    app = create_app(repository, args.token_file.read_text("utf-8").strip(), original_media_type="text/csv")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
