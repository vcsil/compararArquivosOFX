"""Mede candidatos onefile com OFX sintético; inclui início do processo."""
import hashlib
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller.ofx_functions import carregar_ofx


def main():
    executable=Path(sys.argv[1]).resolve(strict=True)
    for n in (100,1000,10000):
        samples=[]; repeats=3 if n<10000 else 1
        data=fixture([('20261110120000','10',str(i),'Sintetico') for i in range(n)])
        for _ in range(repeats):
            with tempfile.TemporaryDirectory(prefix='Compara ofx ') as tmp:
                import shutil
                root=Path(tmp)/'Execução com acento'; root.mkdir()
                exe=root/executable.name
                if executable.parent.name.endswith('.dist'):
                    shutil.copytree(executable.parent, root, dirs_exist_ok=True)
                else:
                    shutil.copy2(executable,exe)
                bank=root/'Banco sintetico'; bank.mkdir()
                src=root/'entrada.ofx'; src.write_bytes(data)
                start=time.perf_counter_ns()
                proc=subprocess.run([str(exe)],cwd=Path(tmp),input=b'1\n',capture_output=True,timeout=300)
                elapsed=(time.perf_counter_ns()-start)/1e6
                if proc.returncode:
                    raise RuntimeError(f'Falha código {proc.returncode}: {proc.stderr.decode(errors="backslashreplace")}')
                copied=list(bank.rglob('entrada.ofx')); general=list(bank.rglob('OFXGeral-*.ofx'))
                if len(copied)!=1 or len(general)!=1 or hashlib.sha256(copied[0].read_bytes()).digest()!=hashlib.sha256(data).digest():
                    raise AssertionError('Original ou Geral sintético não encontrado/preservado')
                if len(carregar_ofx(general[0])[1].statements[0].transactions)!=n:
                    raise AssertionError('Quantidade incorreta no Geral sintético')
                samples.append(elapsed)
        print(f'{n} transações: n={len(samples)} mediana_ms={statistics.median(samples):.3f} min_ms={min(samples):.3f} max_ms={max(samples):.3f}',flush=True)
if __name__=='__main__': main()
