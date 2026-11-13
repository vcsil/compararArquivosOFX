"""Validate test-harness stdin against a real binary-mode subprocess."""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class CandidateInputTests(unittest.TestCase):
    def test_candidate_scripts_send_binary_stdin(self):
        real_run = subprocess.run
        class InputChecked(Exception):
            pass
        for name in ('smoke_exe', 'benchmark_exe_processing'):
            with self.subTest(script=name):
                path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                def check_input(args, **kwargs):
                    result = real_run(
                        [sys.executable, '-c',
                         'import sys; sys.exit(0 if sys.stdin.buffer.read() == b"1\\n" else 1)'],
                        input=kwargs['input'], capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    raise InputChecked()

                with patch.object(sys, 'argv', [str(path), sys.executable]), \
                     patch.object(module.subprocess, 'run', side_effect=check_input):
                    with self.assertRaises(InputChecked):
                        module.main()
