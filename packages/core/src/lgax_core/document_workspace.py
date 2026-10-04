"""Explicit document adapter into the existing workspace server injection point.

The internal manifest below is version metadata, NOT a canonical DemoManifest.
Public documents are never converted into the synthetic demo dataset.
"""

import argparse
import json
from pathlib import Path

import uvicorn
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app

from .document_store import DocumentStore
from .workspace_planning import EnvPlanningRunner


class WorkspaceDocumentStore(DocumentStore):
    def __init__(self, dataset):
        super().__init__(dataset)
        if not isinstance(dataset.get("dataset_version"), str) or not dataset["dataset_version"].strip():
            raise ValueError("Document dataset version required")

    def bootstrap(self):
        response = super().bootstrap()
        response["data"]["manifest"] = {
            "artifact_kind": "document_version_metadata",
            "version": self._dataset["dataset_version"],
        }
        return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--enable-planning", action="store_true")
    args = parser.parse_args()
    store = WorkspaceDocumentStore(json.loads(args.dataset.read_text("utf-8")))
    app = create_workspace_app(args.db, TokenRegistry.from_file(args.credentials), evidence_store=store,
                               planning_runner=EnvPlanningRunner() if args.enable_planning else None)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
