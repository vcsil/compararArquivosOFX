"""Regressão integrada com operações financeiras inteiramente sintéticas."""
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from controller.ofx_functions import carregar_ofx
from controller.workflow import executar, planejar
from test_valori_csv import dados, linha


class IntegracaoHistoricoStatusValori(unittest.TestCase):
    def test_pendente_pago_mesmo_dia_preserva_referencia_e_saldo(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta).resolve()
            banco = raiz / 'Valori'
            banco.mkdir()
            entrada = raiz / 'sintetico.csv'
            hoje = date(2026, 11, 18)

            entrada.write_bytes(dados(
                linha('PEND-INTEGRACAO', Status='Pendente'),
                linha('CONF-INTEGRACAO', Status='Pago'),
            ))
            primeira = planejar(raiz, banco, entrada, hoje=hoje)
            executar(primeira)
            modelo = carregar_ofx(primeira.geral)[1]
            self.assertEqual(len(modelo.statements[0].transactions), 2)
            self.assertEqual(modelo.statements[0].ledgerbal.balamt, Decimal('970.25'))

            entrada.write_bytes(dados(
                linha('PEND-INTEGRACAO', Status='Pago'),
                linha('CONF-INTEGRACAO', Status='Pago'),
            ))
            segunda = planejar(raiz, banco, entrada, hoje=hoje)
            self.assertEqual(segunda.historico, primeira.geral)
            self.assertEqual(segunda.geral, primeira.geral)
            self.assertEqual(segunda.resultado.relatorio.estado, 'APROVADO')
            executar(segunda)
            modelo = carregar_ofx(segunda.geral)[1]
            self.assertEqual(len(modelo.statements[0].transactions), 2)
            self.assertEqual(len({t.fitid for t in modelo.statements[0].transactions}), 2)
            self.assertEqual(modelo.statements[0].ledgerbal.balamt, Decimal('1940.50'))

            entrada.write_bytes(dados(
                linha('PEND-INTEGRACAO', Status='Pago'),
                linha('CONF-INTEGRACAO', Status='Pago'),
            ))
            terceira = planejar(raiz, banco, entrada, hoje=hoje)
            self.assertEqual(terceira.resultado.relatorio.estado, 'SEM_NOVIDADES')
            executar(terceira)
            modelo = carregar_ofx(terceira.geral)[1]
            self.assertEqual(len(modelo.statements[0].transactions), 2)
            self.assertEqual(modelo.statements[0].ledgerbal.balamt, Decimal('1940.50'))
