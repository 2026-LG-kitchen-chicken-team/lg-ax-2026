"""Run only the explicitly authorized, dedicated GPU3 model service; no session expiry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

GPU = 'GPU-ab630930-f010-1d21-6ac6-8f61dba2aac6'
DIGEST = '25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e'
BINARY_SHA = '103220f734bf8b4f4dad26637720fd41400c5ad95d7b02eb7b9d8e16ad1c8f27'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text('utf-8'))
    binary, store = Path(config['ollama_binary']), Path(config['model_store'])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA:
        raise RuntimeError('Pinned model binary changed')
    manifest = store / 'manifests/registry.ollama.ai/library/qwen3.8/27b-q4_K_M'
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise RuntimeError('Pinned model manifest changed')
    for layer in json.loads(raw)['layers']:
        path = store / 'blobs' / layer['digest'].replace(':', '-')
        if not path.is_file() or path.stat().st_size != layer['size']:
            raise RuntimeError('Pinned cached model layer missing')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 18875)) == 0:
            raise RuntimeError('Dedicated model port already in use')
    output = subprocess.check_output(['nvidia-smi', '--id=' + GPU,
        '--query-gpu=memory.free,utilization.gpu', '--format=csv,noheader,nounits'], text=True, timeout=10)
    free, used = (int(item.strip()) for item in output.strip().split(','))
    if free < 26000 or used > 10:
        raise RuntimeError('GPU3 lacks shared headroom; foreign services are unchanged')
    root = Path(config['state_dir']) / 'model-runtime'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('home', 'config', 'cache', 'runtime', 'tmp'):
        (root / name).mkdir(mode=0o700, exist_ok=True)
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'home'),
        'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_CACHE_HOME': str(root / 'cache'),
        'XDG_RUNTIME_DIR': str(root / 'runtime'), 'TMPDIR': str(root / 'tmp'),
        'OLLAMA_HOST': '127.0.0.1:18875', 'OLLAMA_MODELS': str(store),
        'CUDA_VISIBLE_DEVICES': GPU, 'GGML_VK_VISIBLE_DEVICES': '-1', 'OLLAMA_VULKAN': '0',
        'OLLAMA_NOPRUNE': '1', 'OLLAMA_NO_CLOUD': '1', 'OLLAMA_NUM_PARALLEL': '1',
        'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_MAX_QUEUE': '4', 'OLLAMA_KEEP_ALIVE': '-1',
        'OLLAMA_CONTEXT_LENGTH': '16384', 'OLLAMA_SCHED_SPREAD': 'false'}
    # Service manager owns only this process group; no inherited SSH/AI lifetime.
    os.execve(str(binary), [str(binary), 'serve'], env)


if __name__ == '__main__':
    main()
