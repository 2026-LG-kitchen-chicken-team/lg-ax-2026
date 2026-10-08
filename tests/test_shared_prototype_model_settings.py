"""The dedicated serving launcher must preserve the resource and credential boundary."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import start_shared_prototype_model as launcher


class SharedModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.binary = root / 'bin/ollama'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'local-test-launcher-never-executed')
        self.native = root / 'lib/ollama/llama-server'
        self.native.parent.mkdir(parents=True)
        self.native.write_bytes(b'local-native-runner-never-executed')
        store = root / 'models'
        blob_root = store / 'blobs'
        blob_root.mkdir(parents=True)
        self.gguf_bytes = b'test-only-gguf-transport-bytes-not-a-model'
        self.gguf_sha = hashlib.sha256(self.gguf_bytes).hexdigest()
        self.gguf = blob_root / ('sha256-' + self.gguf_sha)
        self.gguf.write_bytes(self.gguf_bytes)
        projector_bytes = b'test-only-projector-that-must-not-be-loaded'
        projector_sha = hashlib.sha256(projector_bytes).hexdigest()
        self.projector = blob_root / ('sha256-' + projector_sha)
        self.projector.write_bytes(projector_bytes)
        manifest = store / 'manifests/registry.ollama.ai/library/qwen3.8/27b-q4_K_M'
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(json.dumps({'layers': [
            {'digest': 'sha256:' + self.gguf_sha, 'size': len(self.gguf_bytes),
             'mediaType': 'application/vnd.ollama.image.model'},
            {'digest': 'sha256:' + projector_sha, 'size': len(projector_bytes),
             'mediaType': 'application/vnd.ollama.image.projector'},
        ]}).encode())
        self.config = root / 'config.json'
        self.config.write_text(json.dumps({'ollama_binary': str(self.binary),
            'model_store': str(store), 'state_dir': str(root / 'state')}))
        self.binary_sha = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.native_sha = hashlib.sha256(self.native.read_bytes()).hexdigest()
        self.manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()

    def engine(self, name):
        config = json.loads(self.config.read_text())
        config['model_engine'] = name
        self.config.write_text(json.dumps(config))

    def launch(self, memory='42000, 0\n'):
        with patch.object(launcher, 'BINARY_SHA', self.binary_sha), \
                patch.object(launcher, 'DIGEST', self.manifest_sha), \
                patch.object(launcher, 'LLAMA_BINARY_SHA', self.native_sha), \
                patch.object(launcher, 'GGUF_SHA', self.gguf_sha), \
                patch('sys.argv', ['launcher', '--config', str(self.config)]), \
                patch.object(launcher.socket, 'socket') as socket, \
                patch.object(launcher.subprocess, 'check_output', return_value=memory) as probe, \
                patch.object(launcher.os, 'execve') as execute:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            try:
                launcher.main()
            except Exception:
                execute.assert_not_called()
                raise
            execute.assert_called_once()
            socket.return_value.__enter__.return_value.connect_ex.assert_called_once_with(
                ('127.0.0.1', 18875)
            )
            return probe.call_args.args[0], execute.call_args.args

    def test_four_model_slots_are_pinned_to_own_gpu_without_inherited_credentials(self):
        with patch.dict(launcher.os.environ, {'GH_TOKEN': 'test-secret', 'CUDA_VISIBLE_DEVICES': '0,1'}):
            probe, (_binary, _args, env) = self.launch()
        self.assertIn('--id=' + launcher.GPU, probe)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], launcher.GPU)
        self.assertEqual(env['OLLAMA_NUM_PARALLEL'], '4')
        self.assertEqual(env['OLLAMA_CONTEXT_LENGTH'], '16384')
        self.assertEqual(env['OLLAMA_KEEP_ALIVE'], '-1')
        self.assertGreaterEqual(int(env['OLLAMA_MAX_QUEUE']), 4)
        self.assertEqual(env['OLLAMA_HOST'], '127.0.0.1:18875')
        self.assertNotIn('GH_TOKEN', env)

    def test_insufficient_vram_does_not_launch_or_change_foreign_services(self):
        with self.assertRaisesRegex(RuntimeError, 'headroom'):
            self.launch('35999, 0\n')

    def test_busy_foreign_gpu_does_not_launch(self):
        with self.assertRaisesRegex(RuntimeError, 'headroom'):
            self.launch('42000, 99\n')

    def test_native_text_only_runner_has_four_separate_16k_slots_on_private_gpu3(self):
        self.engine('llama.cpp')
        inherited = {
            'GH_TOKEN': 'test-only-github-secret',
            'AWS_SECRET_ACCESS_KEY': 'test-only-cloud-secret',
            'SSH_AUTH_SOCK': '/test-only/foreign-agent',
            'LGAX_MODEL_ENDPOINT': 'https://test-only.example',
            'OLLAMA_HOST': '0.0.0.0:11434',
            'CUDA_VISIBLE_DEVICES': '0,1',
        }
        with patch.dict(launcher.os.environ, inherited):
            probe, (binary, args, env) = self.launch()
        own_gpu3 = 'GPU-ab630930-f010-1d21-6ac6-8f61dba2aac6'
        self.assertIn('--id=' + own_gpu3, probe)
        self.assertEqual(binary, str(self.native))
        self.assertEqual(args[0], str(self.native))
        self.assertEqual(args[args.index('--model') + 1], str(self.gguf))
        self.assertEqual(args[args.index('--parallel') + 1], '4')
        self.assertEqual(args[args.index('--ctx-size') + 1], '65536')
        self.assertEqual(args[args.index('--host') + 1], '127.0.0.1')
        self.assertEqual(args[args.index('--port') + 1], '18875')
        self.assertEqual(args[args.index('--alias') + 1], 'qwen3.8:27b-q4_K_M@' + self.manifest_sha)
        self.assertEqual(args[args.index('--reasoning') + 1], 'off')
        for flag in ('--no-kv-unified', '--no-context-shift', '--cont-batching', '--offline', '--no-webui'):
            self.assertIn(flag, args)
        for flag in ('--mmproj', '--mmproj-offload', '--image-min-tokens', '--image-max-tokens'):
            self.assertFalse(any(argument == flag or argument.startswith(flag + '=') for argument in args))
        self.assertNotIn(str(self.projector), args)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], own_gpu3)
        self.assertEqual(env['GGML_VK_VISIBLE_DEVICES'], '-1')
        for name in inherited:
            if name != 'CUDA_VISIBLE_DEVICES':
                self.assertNotIn(name, env)
        self.assertTrue(Path(env['HOME']).is_relative_to(Path(self.temp.name) / 'state/model-runtime'))

    def test_native_binary_hash_change_is_rejected_without_any_exec(self):
        self.engine('llama.cpp')
        self.native.write_bytes(b'changed-native-runner-never-executed')
        with self.assertRaisesRegex(RuntimeError, 'Pinned native runner or GGUF changed'):
            self.launch()

    def test_native_gguf_same_length_hash_change_is_rejected_without_any_exec(self):
        self.engine('llama.cpp')
        changed = bytes(value ^ 1 for value in self.gguf_bytes)
        self.assertEqual(len(changed), len(self.gguf_bytes))
        self.gguf.write_bytes(changed)
        with self.assertRaisesRegex(RuntimeError, 'Pinned native runner or GGUF changed'):
            self.launch()

    def test_native_engine_keeps_headroom_guard_for_low_memory_and_busy_gpu(self):
        self.engine('llama.cpp')
        for memory in ('35999, 0\n', '42000, 99\n'):
            with self.subTest(memory=memory), self.assertRaisesRegex(RuntimeError, 'headroom'):
                self.launch(memory)

    def test_unknown_engine_cannot_fall_back_to_either_runner(self):
        self.engine('unknown-engine')
        with self.assertRaisesRegex(RuntimeError, 'Unknown model engine'):
            self.launch()


if __name__ == '__main__':
    unittest.main()
