"""Executa candidato em diretório temporário com OFX sintético; sem dados reais."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'tests'))
from test_baseline import fixture
from controller.ofx_functions import carregar_ofx


def main():
    exe = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='compara ofx ') as tmp:
        base = Path(tmp)
        root = base / 'Aplicação com acentos'; root.mkdir()
        if exe.parent.name.endswith('.dist'):
            shutil.copytree(exe.parent, root, dirs_exist_ok=True)
        else:
            shutil.copy2(exe, root / exe.name)
        candidate = root / exe.name
        bank = root / '00 Banco Sintetico'; bank.mkdir()
        raw = fixture([('20261110120000', '20', 'SYNTH-1', 'Sintetico')])
        source = root / 'Entrada.ofx'; source.write_bytes(raw)
        proc = subprocess.run([str(candidate)], cwd=base, input='1\n',
                              capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f'Candidato falhou com código {proc.returncode}: {proc.stderr.decode(errors="backslashreplace")}')
        archived = list(bank.rglob('Entrada.ofx'))
        clean = list(bank.rglob('OFX Limpo.ofx'))
        general = list(bank.rglob('OFXGeral-*.ofx'))
        if len(archived) != 1 or len(clean) != 1 or len(general) != 1 or source.exists():
            raise AssertionError('Fluxo sintético não criou arquivos esperados na pasta do executável')
        if archived[0].read_bytes() != raw:
            raise AssertionError('Original sintético não foi preservado')
        for path in (clean[0], general[0]):
            items = carregar_ofx(path)[1].statements[0].transactions
            if len(items) != 1 or items[0].fitid != 'SYNTH-1':
                raise AssertionError('Movimentação sintética não foi preservada')
        if list(base.glob('Banco*')) or list(base.glob('OFXGeral*')):
            raise AssertionError('Histórico foi gravado no diretório de trabalho incorreto')
        print('Smoke sintético aprovado:', exe.name)


if __name__ == '__main__':
    main()
