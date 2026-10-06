"""Static migration counterexamples in a disposable, metadata-only fixture."""
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import re
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / 'private/runtime').resolve()
FIXTURE = (RUNTIME / ('document-navigation-counterprobe-' + uuid.uuid4().hex)).resolve()
assert FIXTURE.is_relative_to(RUNTIME) and FIXTURE.name.startswith('document-navigation-counterprobe-')
FIXTURE.mkdir(parents=True)
MANIFEST_PATH = 'docs/history/project/20261006/manifest.json'
manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding='utf-8'))
files = {MANIFEST_PATH, manifest['link_index'], *manifest['current_entries']}
for source in manifest['sources']:
    files.add(source['archive_path'])
    files.update(link['resolved_path'] for link in source['local_markdown_links'] if link['existed_at_source'])
for entry_path in manifest['current_entries']:
    entry = ROOT / entry_path
    for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)', entry.read_text(encoding='utf-8')):
        target = match.group(1).strip().strip('<>')
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        path_part = target.partition('#')[0]
        full = (entry.parent / unquote(path_part)).resolve() if path_part else entry
        assert full.is_relative_to(ROOT)
        files.add(full.relative_to(ROOT).as_posix())

def verify():
    return subprocess.run(['python', '-X', 'utf8', str(ROOT / 'scripts/check_document_navigation.py'), '--root', str(FIXTURE)], capture_output=True, text=True, encoding='utf-8')

results = []
try:
    for relative in files:
        source = (ROOT / relative).resolve()
        assert source.is_relative_to(ROOT)
        target = FIXTURE / relative
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        elif source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
    assert verify().returncode == 0, verify().stdout
    results.append({'case': 'unchanged_metadata_fixture', 'accepted': True})

    archive = FIXTURE / manifest['sources'][0]['archive_path']
    original = archive.read_bytes()
    archive.write_bytes(original + b'\n')
    result = verify()
    assert result.returncode == 1 and 'Original bytes/hash changed' in result.stdout
    results.append({'case': 'archive_byte_added', 'rejected': True})
    archive.write_bytes(original)

    entry = FIXTURE / manifest['sources'][0]['original_path']
    original = entry.read_bytes()
    heading = manifest['sources'][0]['headings'][0]
    entry.write_bytes(original.replace(heading.encode(), (heading+' altered').encode(), 1))
    result = verify()
    assert result.returncode == 1 and 'Original headings/duplicate-anchor order lost' in result.stdout
    results.append({'case': 'old_heading_changed', 'rejected': True})
    entry.write_bytes(original)

    index = FIXTURE / manifest['link_index']
    original = index.read_bytes()
    reverse = manifest['sources'][0]['sections'][0]['current_entry_link']
    index.write_bytes(original.replace(reverse.encode(), b'missing-reverse-link'))
    result = verify()
    assert result.returncode == 1 and 'Missing reverse link' in result.stdout
    results.append({'case': 'reverse_anchor_link_removed', 'rejected': True})
    index.write_bytes(original)
    assert verify().returncode == 0
    results.append({'case': 'restored_fixture', 'accepted': True})
    print(json.dumps({'cases': results, 'copied_metadata_files': len(files), 'product_execution': False, 'model_calls': 0, 'network_calls': 0}, ensure_ascii=False, indent=2))
finally:
    # Explicitly validate the resolved deletion target before recursive cleanup.
    assert FIXTURE.is_relative_to(RUNTIME) and FIXTURE != RUNTIME and FIXTURE.name.startswith('document-navigation-counterprobe-')
    shutil.rmtree(FIXTURE)
