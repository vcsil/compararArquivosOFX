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
        proc = subprocess.run([str(candidate)], cwd=base, input=b'1\n',
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
        # Reimport an overlapping statement: only the new FITID may be added.
        next_raw = fixture([('20261110120000', '20', 'SYNTH-1', 'Sintetico'),
                            ('20261110120000', '30', 'SYNTH-2', 'Novo')])
        source.write_bytes(next_raw)
        proc = subprocess.run([str(candidate)], cwd=base, input=b'1\n',
                              capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f'Reimportação falhou: {proc.stderr.decode(errors="backslashreplace")}')
        archives = list(bank.rglob('Entrada.ofx'))
        if source.exists() or len(archives) != 2 or sorted(p.read_bytes() for p in archives) != sorted([raw, next_raw]):
            raise AssertionError('Reimportação não preservou os dois originais')
        clean_ids = [tuple(t.fitid for t in carregar_ofx(p)[1].statements[0].transactions)
                     for p in bank.rglob('OFX Limpo.ofx')]
        if sorted(clean_ids) != [('SYNTH-1',), ('SYNTH-2',)]:
            raise AssertionError('Deduplicação do candidato não preservou somente novidades')
        if [t.fitid for t in carregar_ofx(general[0])[1].statements[0].transactions] != ['SYNTH-1', 'SYNTH-2']:
            raise AssertionError('Geral duplicado ou incompleto após reimportação')
        # A changed amount under an existing FITID must block and preserve data.
        before = general[0].read_bytes()
        conflict = fixture([('20261110120000', '999', 'SYNTH-1', 'Sintetico')])
        source.write_bytes(conflict)
        proc = subprocess.run([str(candidate)], cwd=base, input=b'1\n',
                              capture_output=True, timeout=120)
        if proc.returncode == 0 or not source.exists() or source.read_bytes() != conflict:
            raise AssertionError('Conflito de FITID não bloqueou preservando o original')
        if general[0].read_bytes() != before or len(list(bank.rglob('Entrada.ofx'))) != 2:
            raise AssertionError('Conflito alterou o histórico ou arquivou a entrada')
        print('Smoke sintético aprovado:', exe.name)


if __name__ == '__main__':
    main()
