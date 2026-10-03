"""Create private local credentials once; never print credential values."""

import argparse
import json
import secrets
from hashlib import sha256
from pathlib import Path


def initialize(directory: Path) -> None:
    directory = directory.resolve()
    root = Path(__file__).resolve().parents[1]
    if not directory.is_relative_to(root / "private"):
        raise ValueError("Local credentials must stay inside this repository private directory")
    directory.mkdir(parents=True, exist_ok=True)
    credentials_path = directory / "server-credentials.json"
    if credentials_path.exists() or any(
        (directory / f"{role}-client.json").exists() for role in ("editor", "viewer", "admin")
    ):
        raise ValueError("Existing workspace credentials are preserved; choose another private directory")
    records = []
    for role, principal_id in [("editor", "planner-demo"), ("viewer", "planner-demo"), ("admin", "pm-demo")]:
        token = secrets.token_urlsafe(48)
        records.append(
            {"principal_id": principal_id, "role": role, "token_sha256": sha256(token.encode()).hexdigest()}
        )
        path = directory / f"{role}-client.json"
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump({"token": token}, handle)
            handle.write("\n")
        path.chmod(0o600)
    with credentials_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump({"credentials": records}, handle, indent=2)
        handle.write("\n")
    credentials_path.chmod(0o600)
    print(
        "Private local workspace credentials created. Values are not printed. Existing public services are unchanged."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("private/workspace"))
    initialize(parser.parse_args().directory)
