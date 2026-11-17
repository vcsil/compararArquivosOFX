"""Fluxo CSV da Rede: contrato do notebook + integridade do ComparaOFX."""
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from controller.rede_csv import carregar_csv_rede, preparar_transacoes
from controller.ofx_functions import carregar_ofx
from controller.organization import OrganizacaoError, extratos, csvs_rede, anexos
from controller.user_navigation import selecionar
from controller.workflow import planejar, executar
from controller.ofx_names import eh_nome_limpo
from controller import safe_storage


COLUNAS = ('Status da venda;Data da venda;Hora da venda;Valor líquido;NSU/CV;'
           'Código da maquininha;Meio de pagamento;Bandeira;Modalidade;'
           'Tipo;Número de parcelas;Pré-autorizado')


def linha(nsu, data='12/11/2026', hora='10:30:01', valor='R$ 1.234,56',
          status='Aprovada', memo='Visa', pre='Não'):
    return ';'.join((status, data, hora, valor, nsu, 'M012', 'Maquininha',
                     memo, 'Crédito', 'À vista', '1', pre))


def csv(*linhas):
    return (COLUNAS + '\n' + '\n'.join(linhas) + '\n').encode('utf-8')


def transacoes(ofx):
    return ofx.statements[0].transactions


class RedeCSV(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rede = self.root / 'Rede'
        self.rede.mkdir()
        self.outra = self.root / 'Banco A'
        self.outra.mkdir()
        self.dia = date(2026, 11, 13)

    def criar(self, nome='Rede.csv', *linhas):
        p = self.root / nome
        p.write_bytes(csv(*linhas))
        return p

    def test_contrato_notebook_com_todos_campos(self):
        src = self.criar('rede.csv',
                          linha('NSU-10', memo='Mastercard', pre='Sim'),
                          linha('IGNORAR', status='Negada'),
                          linha('NSU-11', data='13/11/2026', hora='12:01',
                                valor='4,50', memo='Visa'))
        _, modelo = carregar_csv_rede(src)
        trs = transacoes(modelo)
        self.assertEqual(len(trs), 2)
        self.assertEqual([t.fitid for t in trs], ['NSU-10 - 10:30:01', 'NSU-11 - 12:01'])
        self.assertEqual([t.trnamt for t in trs], [Decimal('1234.56'), Decimal('4.50')])
        self.assertEqual(trs[0].name, 'M012 - Maquininha')
        self.assertEqual(trs[0].memo, 'Mastercard - Crédito - À vista Pre-Auto - 1x')
        self.assertEqual(trs[0].dtposted.date(), date(2026, 11, 12))
        self.assertIsNotNone(trs[0].dtposted.utcoffset())
        self.assertEqual(src.read_bytes(), csv(linha('NSU-10', memo='Mastercard', pre='Sim'),
                                              linha('IGNORAR', status='Negada'),
                                              linha('NSU-11', data='13/11/2026',
                                                    hora='12:01', valor='4,50', memo='Visa')))

    def test_codificacao_cp1252_e_formato_virgula(self):
        original = csv(linha('C-1', memo='Crédito')).decode('utf-8').encode('cp1252')
        src = self.root / 'outro.CSV'
        src.write_bytes(original)
        _, modelo = carregar_csv_rede(src)
        self.assertEqual(transacoes(modelo)[0].fitid, 'C-1 - 10:30:01')

    def test_recusa_faltantes_duplicados_e_valor_ambiguo(self):
        for texto in (COLUNAS.replace('Valor líquido;', '') + '\n' + linha('A'),
                      COLUNAS + '\n' + linha('A') + '\n' + linha('A'),
                      COLUNAS + '\n' + linha('A', valor='1.234'),
                      COLUNAS + '\n' + linha('A', status='Negada')):
            with self.subTest(texto=texto[:70]):
                src = self.root / 'invalido.csv'
                dados = texto.encode('utf-8')
                src.write_bytes(dados)
                with self.assertRaises(ValueError):
                    carregar_csv_rede(src)
                self.assertEqual(src.read_bytes(), dados)

    def test_modo_csv_so_para_rede_e_outros_csv_nao_sao_anexos(self):
        src = self.criar('vendas.csv', linha('A'))
        outro = self.criar('outras.csv', linha('B'))
        self.assertEqual(extratos(self.root), [])
        self.assertEqual([p.name for p in csvs_rede(self.root)], ['outras.csv', 'vendas.csv'])
        respostas = iter(['2', '1', 'n'])
        banco, selecionado, _ = selecionar(self.root, lambda _: next(respostas), lambda _: None)
        self.assertEqual((banco, selecionado), (self.rede, src))
        self.assertEqual(outro.read_bytes(), csv(linha('B')))
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.outra, src, hoje=self.dia)

    def test_importa_csv_preserva_original_e_gera_ofx(self):
        src = self.criar('vendas.csv', linha('A'))
        bruto = src.read_bytes()
        plano = planejar(self.root, self.rede, src, hoje=self.dia)
        self.assertEqual(plano.resultado.relatorio.estado, 'PRIMEIRA_IMPORTACAO')
        destino = executar(plano)
        self.assertFalse(src.exists())
        self.assertEqual((destino / 'vendas.csv').read_bytes(), bruto)
        limpos = [p for p in destino.iterdir() if eh_nome_limpo(p.name)]
        self.assertEqual(len(limpos), 1)
        self.assertEqual([t.fitid for t in transacoes(carregar_ofx(limpos[0])[1])], ['A - 10:30:01'])
        self.assertEqual([t.fitid for t in transacoes(carregar_ofx(plano.geral)[1])], ['A - 10:30:01'])

    def test_segunda_importacao_e_bloqueio_conflito(self):
        src = self.criar('um.csv', linha('A'))
        executar(planejar(self.root, self.rede, src, hoje=self.dia))
        src = self.criar('dois.csv', linha('A'), linha('B', hora='11:01:00', valor='10,00'))
        plan = planejar(self.root, self.rede, src, hoje=self.dia)
        self.assertEqual(plan.resultado.relatorio.novas.quantidade, 1)
        executar(plan)
        self.assertEqual([t.fitid for t in transacoes(carregar_ofx(plan.geral)[1])],
                         ['A - 10:30:01', 'B - 11:01:00'])
        src = self.criar('conflito.csv', linha('A', valor='999,00'),
                         linha('B', hora='11:01:00', valor='10,00'))
        original = src.read_bytes()
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.rede, src, hoje=self.dia)
        self.assertEqual(src.read_bytes(), original)

    def test_recuperacao_de_manifesto_csv(self):
        src = self.criar('vendas.csv', linha('A'))
        plano = planejar(self.root, self.rede, src, hoje=self.dia)
        publicar = safe_storage.publicar_arquivo
        def interromper(*args):
            publicar(*args)
            raise OSError('interrupção após publicação do Geral')
        with patch.object(safe_storage, 'publicar_arquivo', side_effect=interromper):
            with self.assertRaises(OSError):
                executar(plano)
        self.assertTrue(safe_storage.pendencias(self.rede))
        with safe_storage.bloquear(self.rede):
            safe_storage.recuperar_concluida(self.rede)
        self.assertFalse(safe_storage.pendencias(self.rede))
        self.assertFalse(src.exists())
        self.assertEqual((plano.importacao / 'vendas.csv').read_bytes(), csv(linha('A')))


if __name__ == '__main__':
    unittest.main()
