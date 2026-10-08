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
PARALLEL_REQUESTS = 4
LLAMA_BINARY_SHA = '234b05b2138264f8fb263c3205e85f4c290e8afe5067e280a4f6f90cdac5696b'
GGUF_SHA = 'f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d'


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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
    if free < 36000 or used > 10:
        raise RuntimeError('GPU3 lacks shared headroom; foreign services are unchanged')
    root = Path(config['state_dir']) / 'model-runtime'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('home', 'config', 'cache', 'runtime', 'tmp'):
        (root / name).mkdir(mode=0o700, exist_ok=True)
    if config.get('model_engine') == 'llama.cpp':
        native = binary.parent.parent / 'lib/ollama/llama-server'
        gguf = store / 'blobs' / ('sha256-' + GGUF_SHA)
        if file_sha256(native) != LLAMA_BINARY_SHA or file_sha256(gguf) != GGUF_SHA:
            raise RuntimeError('Pinned native runner or GGUF changed')
        env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'home'),
            'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_CACHE_HOME': str(root / 'cache'),
            'XDG_RUNTIME_DIR': str(root / 'runtime'), 'TMPDIR': str(root / 'tmp'),
            'CUDA_VISIBLE_DEVICES': GPU, 'GGML_VK_VISIBLE_DEVICES': '-1'}
        # Text-only serving: separate KV streams, 16K per slot, no image encoder.
        args = [str(native), '--model', str(gguf), '--alias', 'qwen3.8:27b-q4_K_M@' + DIGEST,
            '--host', '127.0.0.1', '--port', '18875', '--offline', '--no-webui',
            '--ctx-size', str(16384 * PARALLEL_REQUESTS), '--parallel', str(PARALLEL_REQUESTS),
            '--no-kv-unified', '--no-context-shift', '--cont-batching', '--gpu-layers', 'all',
            '--flash-attn', 'auto', '--batch-size', '1024', '--ubatch-size', '1024',
            '--no-jinja', '--chat-template', 'chatml', '--reasoning', 'off', '--slots', '--metrics']
        os.execve(str(native), args, env)
        return
    if config.get('model_engine', 'ollama') != 'ollama':
        raise RuntimeError('Unknown model engine')
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'home'),
        'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_CACHE_HOME': str(root / 'cache'),
        'XDG_RUNTIME_DIR': str(root / 'runtime'), 'TMPDIR': str(root / 'tmp'),
        'OLLAMA_HOST': '127.0.0.1:18875', 'OLLAMA_MODELS': str(store),
        'CUDA_VISIBLE_DEVICES': GPU, 'GGML_VK_VISIBLE_DEVICES': '-1', 'OLLAMA_VULKAN': '0',
        'OLLAMA_NOPRUNE': '1', 'OLLAMA_NO_CLOUD': '1', 'OLLAMA_NUM_PARALLEL': str(PARALLEL_REQUESTS),
        'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_MAX_QUEUE': '16', 'OLLAMA_KEEP_ALIVE': '-1',
        'OLLAMA_CONTEXT_LENGTH': '16384', 'OLLAMA_SCHED_SPREAD': 'false'}
    # Service manager owns only this process group; no inherited SSH/AI lifetime.
    os.execve(str(binary), [str(binary), 'serve'], env)


if __name__ == '__main__':
    main()
