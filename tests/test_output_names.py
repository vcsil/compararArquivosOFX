"""Contratos de nomes, hashes e recuperação v1/v2; somente dados sintéticos."""
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from test_baseline import fixture
from controller import safe_storage as ss
from controller.workflow import planejar, executar
from controller.organization import OrganizacaoError
from controller.ofx_functions import carregar_ofx
from controller.ofx_names import LEGADO_LIMPO, validar_nome_limpo, nome_limpo_manifesto

T = datetime(2026, 11, 13, 7, 40, tzinfo=timezone(timedelta(hours=-3)))
D = date(2026, 11, 12)
NOME = 'OFX Limpo-131120260740.ofx'


class NomesERecuperacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.bank = self.root/'Banco'; self.bank.mkdir()
        self.raw = fixture([('20261110120000', '20', 'A', 'Sintetico')])
        self.src = self.root/'Extrato.ofx'; self.src.write_bytes(self.raw)
        self.pdf = self.root/'Comprovante.pdf'; self.pdf.write_bytes(b'PDF sintetico')

    def plan(self, **kwargs):
        return planejar(self.root, self.bank, self.src, [self.pdf], hoje=D,
                        relogio=kwargs.pop('relogio', lambda: T), **kwargs)

    def interrupted(self, stage='geral'):
        plan = self.plan()
        if stage == 'preparado':
            with patch.object(ss, 'publicar_pasta', side_effect=OSError('interrompido')):
                with self.assertRaises(OSError): executar(plan)
        elif stage == 'parcial':
            real = Path.unlink
            def unlink(path, *args, **kwargs):
                removed_source = path == self.src
                result = real(path, *args, **kwargs)
                if removed_source: raise OSError('interrupção após remover original')
                return result
            with patch.object(Path, 'unlink', unlink):
                with self.assertRaises(OSError): executar(plan)
        else:
            real = ss.publicar_arquivo
            def publish(*args):
                real(*args)
                raise OSError('interrompido depois do Geral')
            with patch.object(ss, 'publicar_arquivo', side_effect=publish):
                with self.assertRaises(OSError): executar(plan)
        op = ss.pendencias(self.bank)[0]
        m = json.loads((op/'manifesto.json').read_text(encoding='utf-8'))
        return plan, op, m

    def test_nome_exato_horario_local_e_hierarquia_independente(self):
        plan = self.plan()
        self.assertEqual(plan.limpo_nome, NOME)
        self.assertEqual(plan.dia.name, '2026-11-12')
        self.assertEqual(plan.geral.name, 'OFXGeral-2026-11-12.ofx')
        out = executar(plan)
        self.assertEqual((out/NOME).read_bytes(), plan.limpo)
        self.assertEqual((out/self.src.name).read_bytes(), self.raw)
        self.assertEqual((out/self.pdf.name).read_bytes(), b'PDF sintetico')
        self.assertIn(b'VERSION="203"', plan.limpo)
        self.assertIn(b'encoding="UTF-8"', plan.limpo)
        item = carregar_ofx(out/NOME)[1].statements[0].transactions[0]
        self.assertEqual((item.fitid, str(item.trnamt)), ('A', '20'))

    def test_relogio_capturado_uma_vez_mesmo_virando_minuto(self):
        clock = Mock(side_effect=[T, T+timedelta(minutes=1)])
        plan = self.plan(relogio=clock)
        with patch('controller.workflow.datetime') as later:
            later.now.side_effect = AssertionError('Relógio não deve ser relido')
            out = executar(plan)
        clock.assert_called_once_with()
        self.assertTrue((out/NOME).is_file())
        self.assertFalse((out/'OFX Limpo-131120260741.ofx').exists())

    def test_mesmo_minuto_isolado_por_pastas_e_limpo_vazio_valido(self):
        first = self.plan(); out1 = executar(first); before = first.geral.read_bytes()
        self.src.write_bytes(self.raw); self.pdf.write_bytes(b'PDF sintetico')
        second = self.plan(); out2 = executar(second)
        self.assertEqual((out1.name, out2.name), ('001', '002'))
        self.assertTrue((out1/NOME).exists()); self.assertTrue((out2/NOME).exists())
        self.assertEqual(second.resultado.relatorio.estado, 'SEM_NOVIDADES')
        self.assertEqual(carregar_ofx(out2/NOME)[1].statements[0].transactions, [])
        self.assertEqual(second.geral.read_bytes(), before)

    def test_segunda_importacao_com_novidades(self):
        executar(self.plan())
        self.src.write_bytes(fixture([('20261110120000','20','A','Sintetico'),
                                      ('20261111120000','30','B','Novo')]))
        self.pdf.write_bytes(b'PDF sintetico')
        plan = self.plan(relogio=lambda: T+timedelta(minutes=1)); out = executar(plan)
        self.assertEqual(out.name, '002')
        self.assertEqual(plan.limpo_nome, 'OFX Limpo-131120260741.ofx')
        self.assertEqual([t.fitid for t in carregar_ofx(out/plan.limpo_nome)[1].statements[0].transactions], ['B'])
        self.assertEqual([t.fitid for t in carregar_ofx(plan.geral)[1].statements[0].transactions], ['A','B'])

    def test_dia_diferente_preserva_historico_e_nome_planejado(self):
        first = self.plan(); out = executar(first); old = first.geral.read_bytes()
        self.src.write_bytes(self.raw); self.pdf.write_bytes(b'PDF sintetico')
        plan = planejar(self.root, self.bank, self.src, [self.pdf], hoje=date(2026,11,13), relogio=lambda:T)
        dest = executar(plan)
        self.assertEqual(dest.name,'001'); self.assertEqual(plan.dia.name,'2026-11-13')
        self.assertTrue((dest/NOME).exists()); self.assertTrue((out/NOME).exists())
        self.assertEqual(first.geral.read_bytes(), old)
        self.assertEqual(carregar_ofx(dest/NOME)[1].statements[0].transactions, [])

    def test_colisao_original_sem_modificar_arquivos(self):
        for name in (NOME, NOME.swapcase()):
            with self.subTest(name=name):
                source = self.root/name; source.write_bytes(self.raw)
                with self.assertRaisesRegex(OrganizacaoError, 'Colisão'):
                    planejar(self.root,self.bank,source,hoje=D,relogio=lambda:T)
                self.assertEqual(source.read_bytes(),self.raw); source.unlink()
        self.assertEqual(list(self.bank.iterdir()),[])

    def test_colisao_anexo_sem_modificar_arquivos(self):
        attachment = self.root/NOME.swapcase(); attachment.write_bytes(b'anexo sintetico')
        with self.assertRaisesRegex(OrganizacaoError, 'Colisão'):
            planejar(self.root,self.bank,self.src,[attachment],hoje=D,relogio=lambda:T)
        self.assertEqual(attachment.read_bytes(),b'anexo sintetico')
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertEqual(list(self.bank.iterdir()),[])

    def test_plano_adulterado_nao_escapa_da_pasta(self):
        plan = self.plan(); plan.limpo_nome = '../fora.ofx'
        with self.assertRaises(ValueError): executar(plan)
        self.assertEqual(list(self.bank.iterdir()),[]); self.assertEqual(self.src.read_bytes(),self.raw)

    def test_manifesto_v2_nome_e_hash_obrigatorios(self):
        plan, op, m = self.interrupted()
        self.assertEqual((m['versao'],m['limpo_nome']), (2,NOME))
        self.assertEqual(m['limpo_hash'],hashlib.sha256(plan.limpo).hexdigest())
        self.assertEqual(nome_limpo_manifesto(m),NOME)
        ss.recuperar_concluida(self.bank)
        self.assertFalse(self.src.exists()); self.assertTrue((plan.importacao/NOME).exists())

    def test_recuperacao_pre_publicacao_v2(self):
        plan, op, m = self.interrupted('preparado')
        self.assertEqual(m['limpo_nome'],NOME)
        self.assertTrue((op/'pasta'/NOME).exists())
        ss.recuperar_concluida(self.bank)
        self.assertEqual(ss.pendencias(self.bank),[])
        self.assertFalse(plan.importacao.exists()); self.assertFalse(plan.geral.exists())
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertEqual(self.pdf.read_bytes(),b'PDF sintetico')

    def test_recuperacao_apos_remocao_parcial_v2(self):
        plan, op, m = self.interrupted('parcial')
        self.assertFalse(self.src.exists()); self.assertTrue(self.pdf.exists())
        ss.recuperar_concluida(self.bank); ss.recuperar_concluida(self.bank)
        self.assertEqual(ss.pendencias(self.bank),[]); self.assertFalse(self.pdf.exists())
        self.assertEqual((plan.importacao/self.src.name).read_bytes(),self.raw)
        self.assertTrue((plan.importacao/NOME).exists())

    def test_manifestos_invalidos_bloqueiam_antes_de_remover(self):
        plan, op, m = self.interrupted()
        invalid = ['../'+NOME, 'pasta/'+NOME, 'pasta\\'+NOME, 'C:\\'+NOME,
                   NOME+'\n', NOME+'\x00', NOME+' ', NOME.upper(),
                   'OFX Limpo-３１１１２０２６０７４０.ofx', 'OFX Limpo-311120260740.ofx',
                   'OFX Limpo-131120262440.ofx', LEGADO_LIMPO, '', None, 123]
        before = plan.geral.read_bytes()
        for name in invalid:
            with self.subTest(name=name):
                broken = {**m,'limpo_nome':name}; ss.atualizar_manifesto(op,broken)
                with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
                self.assertEqual(self.src.read_bytes(),self.raw)
                self.assertEqual(plan.geral.read_bytes(),before)
        for changes in ({'versao':3},{'versao':True},{'versao':2.0},{'limpo_hash':None}, {'limpo_hash':'bad'}):
            with self.subTest(changes=changes):
                ss.atualizar_manifesto(op,{**m,**changes})
                with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
                self.assertTrue(self.src.exists())
        for key in ('limpo_nome','limpo_hash'):
            broken = dict(m); del broken[key]; ss.atualizar_manifesto(op,broken)
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        ss.atualizar_manifesto(op,m); ss.recuperar_concluida(self.bank)
        self.assertTrue((plan.importacao/NOME).exists())

    def test_nome_malicioso_na_preparacao_preserva_todos_os_temporarios(self):
        plan,op,m = self.interrupted('preparado')
        m['limpo_nome']='../fora.ofx'; ss.atualizar_manifesto(op,m)
        before={p.name:p.read_bytes() for p in (op/'pasta').iterdir()}
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual({p.name:p.read_bytes() for p in (op/'pasta').iterdir()},before)
        self.assertEqual(self.src.read_bytes(),self.raw)

    def test_hash_limpo_divergente_bloqueia_recuperacao(self):
        plan,op,m = self.interrupted(); target=plan.importacao/NOME
        target.write_bytes(b'corrompido')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertTrue(self.pdf.exists())
        self.assertEqual(target.read_bytes(),b'corrompido'); self.assertTrue(op.exists())

    def test_recuperacao_legada_publicada_sem_renomear(self):
        plan,op,m = self.interrupted()
        # Construção controlada de um registro v1 tal como gerado pela Etapa 5.
        (plan.importacao/NOME).rename(plan.importacao/LEGADO_LIMPO)
        old_bytes=(plan.importacao/LEGADO_LIMPO).read_bytes()
        m['versao']=1; m.pop('limpo_nome'); ss.atualizar_manifesto(op,m)
        ss.recuperar_concluida(self.bank); ss.recuperar_concluida(self.bank)
        self.assertEqual((plan.importacao/LEGADO_LIMPO).read_bytes(),old_bytes)
        self.assertFalse((plan.importacao/NOME).exists()); self.assertFalse(self.src.exists())
        self.assertEqual(ss.pendencias(self.bank),[])

    def test_recuperacao_legada_pre_publicacao(self):
        plan,op,m=self.interrupted('preparado')
        (op/'pasta'/NOME).rename(op/'pasta'/LEGADO_LIMPO)
        m['versao']=1; m.pop('limpo_nome'); ss.atualizar_manifesto(op,m)
        ss.recuperar_concluida(self.bank)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(ss.pendencias(self.bank),[])
        self.assertEqual(self.src.read_bytes(),self.raw)

    def test_hash_legado_obrigatorio(self):
        plan,op,m=self.interrupted()
        (plan.importacao/NOME).rename(plan.importacao/LEGADO_LIMPO)
        m['versao']=1; m.pop('limpo_nome'); m.pop('limpo_hash'); ss.atualizar_manifesto(op,m)
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertTrue((plan.importacao/LEGADO_LIMPO).exists())


if __name__ == '__main__': unittest.main()
