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

    def test_full_smoke_uses_real_lines_and_runs_csv_flow(self):
        """Execute every smoke invocation against the real app in child processes.

        The bridge supplies the executable root only; financial code and stdin
        parsing are real. Packaged binaries are tested separately by the CI.
        """
        import contextlib
        import io
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'smoke_exe.py'
        src = path.parents[1] / 'src'
        spec = importlib.util.spec_from_file_location('full_smoke', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        real_run = subprocess.run
        invocations = []
        bridge = ('import sys; from pathlib import Path; '
                  f'sys.path.insert(0, {str(src)!r}); '
                  'from comparaArqOFX import main; '
                  'sys.exit(main(raiz=Path(sys.argv[1]).parent))')
        def run_app(args, **kwargs):
            invocations.append(kwargs['input'])
            self.assertNotIn(b'\\n', kwargs['input'])
            return real_run([sys.executable, '-c', bridge, args[0]], **kwargs)
        output = io.StringIO()
        with patch.object(sys, 'argv', [str(path), sys.executable]), \
             patch.object(module.subprocess, 'run', side_effect=run_app), \
             contextlib.redirect_stdout(output):
            module.main()
        self.assertEqual(len(invocations), 9)
        self.assertIn('Smoke CSV Rede aprovado', output.getvalue())
