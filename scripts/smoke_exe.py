"""Executa candidato em diretório temporário com OFX sintético; sem dados reais."""
import shutil
import os
import json
from datetime import date, datetime
from unittest.mock import patch
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'tests'))
from test_baseline import fixture
from controller.ofx_functions import carregar_ofx
from controller.ofx_names import eh_nome_limpo, LEGADO_LIMPO
from controller import safe_storage
from controller.workflow import planejar, executar


def main():
    exe = Path(sys.argv[1]).resolve(strict=True)
    candidate_env = os.environ.copy()
    if os.name == 'nt':
        # Do not let a separately installed Python satisfy the executable.
        candidate_env.pop('PYTHONPATH', None)
        candidate_env.pop('PYTHONHOME', None)
        candidate_env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
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
        generation_started = datetime.now().replace(second=0, microsecond=0)
        proc = subprocess.run([str(candidate)], cwd=base, input=b'1\n',
                              capture_output=True, timeout=120, env=candidate_env)
        if b'\x1b[' in proc.stdout or b'\x1b[' in proc.stderr:
            raise AssertionError('Saída redirecionada contém códigos ANSI')
        if b'COMPARAOFX 2.0' not in proc.stdout or b'Selecione a institui' not in proc.stdout:
            raise AssertionError('Cabeçalho ou menu ausente na saída redirecionada')
        if proc.returncode != 0:
            raise RuntimeError(f'Candidato falhou com código {proc.returncode}: {proc.stderr.decode(errors="backslashreplace")}')
        archived = list(bank.rglob('Entrada.ofx'))
        clean = [p for p in bank.rglob('*.ofx') if eh_nome_limpo(p.name, legado=False)]
        general = list(bank.rglob('OFXGeral-*.ofx'))
        if len(archived) != 1 or len(clean) != 1 or len(general) != 1 or source.exists():
            raise AssertionError('Fluxo sintético não criou arquivos esperados na pasta do executável')
        if archived[0].read_bytes() != raw:
            raise AssertionError('Original sintético não foi preservado')
        generated = datetime.strptime(clean[0].name[10:-4], '%d%m%Y%H%M')
        if not generation_started <= generated <= datetime.now():
            raise AssertionError('Nome do Limpo não usa o horário local de geração')
        for path in (clean[0], general[0]):
            if b'\x1b[' in path.read_bytes():
                raise AssertionError('Sequência ANSI encontrada em arquivo OFX')
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
                              capture_output=True, timeout=120, env=candidate_env)
        if proc.returncode != 0:
            raise RuntimeError(f'Reimportação falhou: {proc.stderr.decode(errors="backslashreplace")}')
        archives = list(bank.rglob('Entrada.ofx'))
        if source.exists() or len(archives) != 2 or sorted(p.read_bytes() for p in archives) != sorted([raw, next_raw]):
            raise AssertionError('Reimportação não preservou os dois originais')
        clean_ids = [tuple(t.fitid for t in carregar_ofx(p)[1].statements[0].transactions)
                     for p in bank.rglob('*.ofx') if eh_nome_limpo(p.name, legado=False)]
        if sorted(clean_ids) != [('SYNTH-1',), ('SYNTH-2',)]:
            raise AssertionError('Deduplicação do candidato não preservou somente novidades')
        if [t.fitid for t in carregar_ofx(general[0])[1].statements[0].transactions] != ['SYNTH-1', 'SYNTH-2']:
            raise AssertionError('Geral duplicado ou incompleto após reimportação')
        # A changed amount under an existing FITID must block and preserve data.
        before = general[0].read_bytes()
        conflict = fixture([('20261110120000', '999', 'SYNTH-1', 'Sintetico')])
        source.write_bytes(conflict)
        proc = subprocess.run([str(candidate)], cwd=base, input=b'1\n',
                              capture_output=True, timeout=120, env=candidate_env)
        if proc.returncode == 0 or not source.exists() or source.read_bytes() != conflict:
            raise AssertionError('Conflito de FITID não bloqueou preservando o original')
        if general[0].read_bytes() != before or len(list(bank.rglob('Entrada.ofx'))) != 2:
            raise AssertionError('Conflito alterou o histórico ou arquivou a entrada')
        # Prepare synthetic interrupted operations in the test harness; the
        # candidate itself must recover both the old and new storage protocol.
        for version in (1, 2):
            rows = [('20261110120000', '20', 'SYNTH-1', 'Sintetico'),
                    ('20261110120000', '30', 'SYNTH-2', 'Novo')]
            rows += [('20261110120000', '10', f'REC-{v}', 'Recuperacao')
                     for v in range(1, version+1)]
            recovery_raw = fixture(rows); source.write_bytes(recovery_raw)
            plan = planejar(root, bank, source, hoje=date.today())
            real_publish = safe_storage.publicar_arquivo
            def interrupted(*args):
                real_publish(*args)
                raise OSError('Interrupção sintética depois do Geral')
            try:
                with patch.object(safe_storage, 'publicar_arquivo', side_effect=interrupted):
                    executar(plan)
            except OSError as exc:
                if str(exc) != 'Interrupção sintética depois do Geral':
                    raise
            else:
                raise AssertionError('Interrupção sintética não ocorreu')
            op = safe_storage.pendencias(bank)[0]
            manifest = json.loads((op/'manifesto.json').read_text(encoding='utf-8'))
            expected_name = plan.limpo_nome
            if version == 1:
                # Controlled fixture construction, never migration of user data.
                (plan.importacao/plan.limpo_nome).rename(plan.importacao/LEGADO_LIMPO)
                manifest['versao'] = 1; manifest.pop('limpo_nome')
                safe_storage.atualizar_manifesto(op, manifest)
                expected_name = LEGADO_LIMPO
            elif manifest['versao'] != 2 or manifest['limpo_nome'] != expected_name:
                raise AssertionError('Novo manifesto não registra o nome planejado')
            saved_clean = (plan.importacao/expected_name).read_bytes()
            saved_general = plan.geral.read_bytes()
            proc = subprocess.run([str(candidate)], cwd=base, input=b'',
                                  capture_output=True, timeout=120, env=candidate_env)
            if proc.returncode or source.exists() or safe_storage.pendencias(bank):
                raise AssertionError(f'Candidato não recuperou manifesto v{version}')
            if ((plan.importacao/expected_name).read_bytes() != saved_clean
                    or plan.geral.read_bytes() != saved_general
                    or (plan.importacao/source.name).read_bytes() != recovery_raw):
                raise AssertionError('Recuperação alterou nomes, dados ou originais')
            print(f'Recuperação sintética v{version} aprovada:', exe.name)
        # CSV da Rede: nenhum Python externo, CSV original preservado e OFX validado.
        from controller.ofx_names import eh_nome_limpo
        rede = root / 'Rede'
        rede.mkdir()
        csv_data = (
            'Status da venda;Data da venda;Hora da venda;Valor líquido;NSU/CV;'
            'Código da maquininha;Meio de pagamento;Bandeira;Modalidade;'
            'Tipo;Número de parcelas;Pré-autorizado\\n'
            'Aprovada;10/11/2026;12:30:05;10,50;REDE-SMOKE;'
            'M001;Maquininha;Visa;Crédito;À vista;1;Não\\n'
            'Negada;10/11/2026;12:31:05;10,50;REDE-IGNORE;'
            'M001;Maquininha;Visa;Crédito;À vista;1;Não\\n'
        ).replace('\\n', '\\n').encode('utf-8')
        csv_source = root / 'vendas_rede.csv'
        csv_source.write_bytes(csv_data)
        # O arquivo de entrada é único; selecionar a instituição Rede.
        proc = subprocess.run([str(candidate)], cwd=base, input=b'2\\n',
                              capture_output=True, timeout=120, env=candidate_env)
        if proc.returncode:
            raise AssertionError('Candidato falhou ao importar CSV da Rede: ' +
                                 proc.stdout.decode(errors='backslashreplace'))
        copias = list(rede.rglob('vendas_rede.csv'))
        novos = [p for p in rede.rglob('*.ofx') if eh_nome_limpo(p.name, legado=False)]
        gerais = list(rede.rglob('OFXGeral-*.ofx'))
        if csv_source.exists() or len(copias) != 1 or len(novos) != 1 or len(gerais) != 1:
            raise AssertionError('Fluxo Rede CSV não organizou os arquivos esperados')
        if copias[0].read_bytes() != csv_data:
            raise AssertionError('CSV original da Rede foi modificado')
        for path in (novos[0], gerais[0]):
            if [t.fitid for t in carregar_ofx(path)[1].statements[0].transactions] != ['REDE-SMOKE - 12:30:05']:
                raise AssertionError('CSV Rede convertido não preservou a venda aprovada')
        print('Smoke CSV Rede aprovado:', exe.name)
        print('Smoke sintético aprovado:', exe.name)


if __name__ == '__main__':
    main()
