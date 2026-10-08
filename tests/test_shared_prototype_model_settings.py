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
        binary = root / 'ollama'
        binary.write_bytes(b'local-test-launcher')
        store = root / 'models'
        manifest = store / 'manifests/registry.ollama.ai/library/qwen3.8/27b-q4_K_M'
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(json.dumps({'layers': []}).encode())
        self.config = root / 'config.json'
        self.config.write_text(json.dumps({'ollama_binary': str(binary),
            'model_store': str(store), 'state_dir': str(root / 'state')}))
        self.binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
        self.manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()

    def launch(self, memory='42000, 0\n'):
        with patch.object(launcher, 'BINARY_SHA', self.binary_sha), \
                patch.object(launcher, 'DIGEST', self.manifest_sha), \
                patch('sys.argv', ['launcher', '--config', str(self.config)]), \
                patch.object(launcher.socket, 'socket') as socket, \
                patch.object(launcher.subprocess, 'check_output', return_value=memory) as probe, \
                patch.object(launcher.os, 'execve') as execute:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            launcher.main()
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


if __name__ == '__main__':
    unittest.main()
