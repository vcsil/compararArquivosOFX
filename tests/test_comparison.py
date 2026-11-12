import contextlib
import io
import runpy
import unittest
from unittest.mock import patch
from decimal import Decimal
from pathlib import Path
from test_baseline import fixture, parse
from controller.ofx_comparison import analisar


def tx(day, amount, ident, memo='memo'):
    return (f'202301{day:02d}120000',str(amount),str(ident),memo)
def model(items, account='123'):
    return parse(fixture(items, account=account))
def ids(o): return [t.fitid for t in o.statements[0].transactions]

class Comparacao(unittest.TestCase):
    def test_overlap_ordem_quantidades_e_valores(self):
        old=model([tx(2,10,'a'),tx(1,2,'z')])
        new=model([tx(3,-5,'c'),tx(2,10,'a'),tx(1,4,'x'),tx(2,10,'b')])
        a,b=ids(old),ids(new); result=analisar(new,old); r=result.relatorio
        self.assertEqual(r.estado,'APROVADO'); self.assertEqual(ids(result.modelo_filtrado(new)),['c','b'])
        self.assertEqual((r.original.quantidade,r.anteriores.quantidade,r.duplicatas.quantidade,r.novas_intersecao.quantidade,r.posteriores.quantidade,r.novas.quantidade),(4,1,1,1,1,2))
        self.assertEqual((r.original.creditos,r.original.debitos,r.original.liquido),(Decimal('24'),Decimal('-5'),Decimal('19')))
        self.assertEqual((r.novas.creditos,r.novas.debitos,r.novas.liquido),(Decimal('10'),Decimal('-5'),Decimal('5')))
        self.assertEqual(ids(old),a); self.assertEqual(ids(new),b)
        self.assertEqual(result.relatorio,analisar(new,old).relatorio)
    def test_memo_alterado_e_id_diferente(self):
        old=model([tx(2,10,'a','velho')]); new=model([tx(2,10,'a','novo'),tx(2,10,'b','novo')])
        r=analisar(new,old); self.assertEqual(ids(r.modelo_filtrado(new)),['b']); self.assertEqual(len(r.relatorio.divergencias_memo),1)
    def test_conflitos_valor_tipo_data(self):
        old=model([tx(2,10,'a')])
        for items in ([tx(2,11,'a')],[tx(2,10,'b'),tx(3,10,'a')]):
            with self.subTest(items=items): self.assertEqual(analisar(model(items),old).relatorio.estado,'BLOQUEADO')
        other=model([tx(2,10,'a')]); other.statements[0].transactions[0].trntype='DEBIT'
        self.assertEqual(analisar(other,old).relatorio.estado,'BLOQUEADO')
    def test_mesmo_instante_com_fusos_distintos(self):
        old=model([('20230102120000[-3:EST]','10','a','x')])
        new=model([('20230102150000[0:GMT]','10','a','x')])
        self.assertEqual(analisar(new,old).relatorio.estado,'SEM_NOVIDADES')
    def test_id_duplicado_em_ambos_arquivos(self):
        duplicate=model([tx(2,1,'a'),tx(2,1,'a')]); good=model([tx(2,1,'a')])
        for a,b in ((duplicate,good),(good,duplicate)):
            self.assertEqual(analisar(a,b).relatorio.estado,'BLOQUEADO')
    def test_conta_banco_moeda_diferentes(self):
        old=model([tx(2,1,'a')]); other=model([tx(2,1,'a')],account='999')
        self.assertEqual(analisar(other,old).relatorio.estado,'BLOQUEADO')
        other=model([tx(2,1,'a')]); other.statements[0].bankacctfrom.bankid='9'
        self.assertEqual(analisar(other,old).relatorio.estado,'BLOQUEADO')
        other=model([tx(2,1,'a')]); other.statements[0].curdef='USD'
        self.assertEqual(analisar(other,old).relatorio.estado,'BLOQUEADO')
        other=model([tx(2,1,'a')],account='0123')
        self.assertEqual(analisar(other,old).relatorio.estado,'BLOQUEADO')
    def test_multiplos_demonstrativos(self):
        from types import SimpleNamespace
        old=model([tx(2,1,'a')]); wrapper=SimpleNamespace(statements=[old.statements[0],old.statements[0]])
        self.assertEqual(analisar(wrapper,old).relatorio.estado,'BLOQUEADO')
    def test_ausencia_data_e_falta_historico_dia(self):
        old=model([tx(2,1,'a'),tx(2,2,'b')])
        for items in ([tx(3,1,'c')],[tx(2,1,'a')],[tx(1,1,'x')]):
            self.assertEqual(analisar(model(items),old).relatorio.estado,'BLOQUEADO')
    def test_primeira_importacao_e_vazio(self):
        new=model([tx(2,1,'a')]); result=analisar(new)
        self.assertEqual(result.relatorio.estado,'PRIMEIRA_IMPORTACAO'); self.assertEqual(ids(result.modelo_filtrado(new)),['a'])
        empty=model([]); self.assertEqual(analisar(empty,new).relatorio.estado,'SEM_NOVIDADES')
        self.assertEqual(analisar(new,empty).relatorio.estado,'APROVADO')
    def test_reprocessamento(self):
        old=model([tx(2,1,'a'),tx(2,-2,'b')]); new=model([tx(2,1,'a'),tx(2,-2,'b')])
        self.assertEqual(analisar(new,old).relatorio.estado,'SEM_NOVIDADES')
        self.assertEqual(analisar(new,old).relatorio.novas.quantidade,0)
    def test_modelo_filtrado_independente(self):
        old=model([tx(2,1,'a')]); new=model([tx(2,1,'a'),tx(2,3,'b')])
        result=analisar(new,old); filtered=result.modelo_filtrado(new)
        filtered.statements[0].transactions[0].memo='mudado'
        self.assertEqual(new.statements[0].transactions[1].memo,'memo')
        self.assertEqual(old.statements[0].transactions[0].memo,'memo')
    def test_conflito_numero_cheque(self):
        old=model([tx(2,1,'a')]); new=model([tx(2,1,'a')])
        new.statements[0].transactions[0].checknum='outro'
        result=analisar(new,old)
        self.assertEqual(result.relatorio.estado,'BLOQUEADO')
        self.assertTrue(result.relatorio.conflitos)
    def test_precisao_insuficiente_bloqueia(self):
        from decimal import localcontext
        new=model([tx(2,'123456789.12','a'),tx(2,'0.01','b')])
        with localcontext() as ctx:
            ctx.prec=6
            result=analisar(new)
        self.assertEqual(result.relatorio.estado,'BLOQUEADO')
        self.assertIn('Decimal',result.relatorio.motivo)
    def test_grande(self):
        old=model([tx(2,1,str(i)) for i in range(400)])
        new=model([tx(2,1,str(i)) for i in range(600)])
        self.assertEqual(analisar(new,old).relatorio.novas.quantidade,200)
    def test_bloqueado_antes_gravacao(self):
        import tempfile
        from datetime import date
        from controller.workflow import planejar
        from controller.organization import pasta_dia, OrganizacaoError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bank=root/'Banco'; bank.mkdir(); day=pasta_dia(bank,date(2023,1,2)); day.mkdir(parents=True)
            (day/'OFXGeral-2023-01-02.ofx').write_bytes(fixture([tx(2,1,'a')]))
            current=root/'input.ofx'; current.write_bytes(fixture([tx(2,2,'a')]))
            with self.assertRaises(OrganizacaoError): planejar(root,bank,current,hoje=date(2023,1,2))
            self.assertTrue(current.exists()); self.assertFalse((day/'001').exists())
    def test_fluxo_aprovado_envia_somente_movimentos_novos(self):
        import tempfile
        from datetime import date
        from controller.workflow import planejar, executar
        from controller.organization import pasta_dia
        from controller.ofx_functions import carregar_ofx
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bank=root/'Banco'; bank.mkdir(); day=pasta_dia(bank,date(2023,1,2)); day.mkdir(parents=True)
            (day/'OFXGeral-2023-01-02.ofx').write_bytes(fixture([tx(2,1,'a')]))
            current=root/'input.ofx'; current.write_bytes(fixture([tx(2,1,'a'),tx(3,-2,'b')]))
            dest=executar(planejar(root,bank,current,hoje=date(2023,1,2)))
            self.assertEqual(ids(carregar_ofx(dest/'OFX Limpo.ofx')[1]),['b'])
            self.assertEqual(ids(carregar_ofx(day/'OFXGeral-2023-01-02.ofx')[1]),['a','b'])

if __name__=='__main__': unittest.main()
