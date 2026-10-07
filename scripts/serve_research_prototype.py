"""Start the actual-source prototype manually; no schedulers or implicit model startup."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import uvicorn
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.model_client import StructuredModelClient
from lgax_core.public_planning import PublicPlanner

ROOT = Path(__file__).resolve().parents[1]


def research_bundle_paths(root: Path = ROOT) -> list[Path]:
    """Keep seven existing run inputs and add one document-only manual reference."""
    edition = root / 'data/research/r9-public-runtime-20261008'
    paths = [edition / f'{group}.research-bundle.json' for group in ('dishwasher', 'fridge', 'microwave')]
    paths += sorted((root / 'data/research/r8-public-official-expansion-20261007/bundles').glob('*.json'))
    paths.append(root / 'data/research/r8-public-competitor-adapter-20261007/fridge.development.research-bundle.json')
    paths.append(edition / 'microwave.manual-reference.research-bundle.json')
    if len(paths) != 8 or any(not path.is_file() for path in paths):
        raise ValueError('Prepare the three R9 actual-source bundles and the separate manual reference.')
    return paths


class BoundedPrototypePlanner:
    def run(self, bundle, goal, constraints, previous=None):
        with StructuredModelClient.from_env() as client:
            return PublicPlanner.from_model_client(client, max_model_calls=4, max_problems=1,
                max_prompt_characters=6500, max_source_characters=1000).run(bundle, goal, constraints, previous)

    def repair(self, bundle, previous, feedback):
        with StructuredModelClient.from_env() as client:
            return PublicPlanner.from_model_client(client, max_model_calls=4, max_problems=1).repair(bundle, previous, feedback)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-file', type=Path, required=True,
                        help='Private JSON with token and optional principal_id; never commit this file.')
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18969)
    parser.add_argument('--enable-model', action='store_true')
    args = parser.parse_args()
    credential = json.loads(args.credential_file.read_text('utf-8'))
    token = credential.get('token')
    if (not isinstance(token, str) or not 32 <= len(token) <= 256
            or any(char.isspace() for char in token)):
        parser.error('The private token must contain 32–256 characters without whitespace.')
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a non-privileged loopback port.')
    registry = TokenRegistry([{'principal_id': credential.get('principal_id', 'manual-research-prototype'),
                              'role': 'editor', 'token_sha256': sha256(token.encode()).hexdigest()}])
    try:
        paths = research_bundle_paths()
    except ValueError as error:
        parser.error(str(error))
    workspace = ResearchWorkspace(args.state_dir / 'r8-preview.research.sqlite3', paths,
                                  BoundedPrototypePlanner() if args.enable_model else None)
    app = create_workspace_app(args.state_dir / 'r8-preview.workspace.sqlite3', registry,
                               research_workspace=workspace)
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
