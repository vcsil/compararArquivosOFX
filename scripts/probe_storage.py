"""Homologação sintética no diretório indicado; não testa exclusão entre PCs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller.storage_capabilities import verificar_capacidades


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('diretorio', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    result = {'dados_financeiros': 'SOMENTE_SINTETICOS', 'entre_dispositivos': 'NAO_HOMOLOGADO',
              'plataforma': sys.platform, 'python': sys.version.split()[0]}
    # Todos os testes criam somente subpastas descartáveis nesta área.
    with tempfile.TemporaryDirectory(prefix='compara-storage-probe-', dir=args.diretorio.resolve(strict=True)) as tmp:
        try:
            verificar_capacidades(Path(tmp))
            result['primitivas'] = 'PASS'
        except (OSError, ValueError) as exc:
            result['primitivas'] = 'FAIL'
            result['diagnostico'] = str(exc)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        env = os.environ.copy()
        env.update(TMPDIR=tmp, TMP=tmp, TEMP=tmp, PYTHONPATH=str(repo / 'src'))
        # Inclui falhas antes/depois de publicação, interrupções reais de processo,
        # recuperação v1/v2, reimportação e alteração externa, sem dados privados.
        suite = ['test_storage_capabilities', 'test_windows_native', 'test_path_identity',
                 'test_safe_storage', 'test_organization']
        run = subprocess.run([sys.executable, '-m', 'unittest', '-v', *suite],
                             cwd=repo / 'tests', env=env, timeout=300)
        result['suite_sintetica'] = 'PASS' if run.returncode == 0 else 'FAIL'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return run.returncode


if __name__ == '__main__':
    sys.exit(main())
