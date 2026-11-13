import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from test_baseline import fixture
from controller.organization import (instituicoes, extratos, anexos, pasta_dia, proxima_importacao, localizar_historico, raiz_aplicacao, OrganizacaoError)
from controller.user_navigation import selecionar, Cancelado
from controller.workflow import planejar, executar
from controller.ofx_functions import carregar_ofx

D=date(2026,11,12)
def tx(day,ident,amount='10'):
    return (f'202611{day:02d}120000',amount,ident,'Teste')

def ids(path):
    return [x.fitid for x in carregar_ofx(path)[1].statements[0].transactions]

class Organizacao(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.bank=self.root/'Banco do Brasil'; self.bank.mkdir()
    def old(self,day,items):
        p=pasta_dia(self.bank,day); p.mkdir(parents=True,exist_ok=True)
        f=p/f'OFXGeral-{day.isoformat()}.ofx'; f.write_bytes(fixture(items)); return f
    def test_discovery_and_menus(self):
        for name in ['docs','src','tests','.git','venv','Itau CNPJ','Árvore']:
            (self.root/name).mkdir()
        a=self.root/'A.OFX'; a.write_bytes(b'a'); b=self.root/'b.ofx'; b.write_bytes(b'b')
        (self.root/'~tmp.ofx').write_bytes(b'x'); (self.root/'anexo.pdf').write_bytes(b'p')
        (self.root/'programa.exe').write_bytes(b'e')
        self.assertEqual([x.name for x in instituicoes(self.root)],['Banco do Brasil','Itau CNPJ','Árvore'])
        self.assertEqual([x.name for x in extratos(self.root)],['A.OFX','b.ofx'])
        self.assertEqual([x.name for x in anexos(self.root)],['anexo.pdf'])
        responses=iter(['erro','2','1','1'])
        bank,chosen,docs=selecionar(self.root,lambda _:next(responses),lambda _:None)
        self.assertEqual((bank,chosen,docs),(self.bank,b,[self.root/'anexo.pdf']))
        responses=iter(['0'])
        with self.assertRaises(Cancelado): selecionar(self.root,lambda _:next(responses),lambda _:None)
    def test_sem_ofx_nada_criado(self):
        self.assertIsNone(selecionar(self.root,lambda _:self.fail('não deve solicitar entrada'),lambda _:None))
        self.assertEqual(list(self.bank.iterdir()),[])
    def test_primeira_importacao_e_preservacao(self):
        source=self.root/'Extrato.ofx'; raw=fixture([tx(10,'A'),tx(11,'B')]); source.write_bytes(raw)
        pdf=self.root/'anexo.pdf'; pdf.write_bytes(b'documento sintetico')
        plan=planejar(self.root,self.bank,source,[pdf],hoje=D)
        self.assertEqual(plan.resultado.relatorio.estado,'PRIMEIRA_IMPORTACAO')
        self.assertEqual(list(self.bank.iterdir()),[])
        dest=executar(plan)
        self.assertEqual(dest,pasta_dia(self.bank,D)/'001')
        self.assertEqual((dest/'Extrato.ofx').read_bytes(),raw)
        self.assertEqual((dest/'anexo.pdf').read_bytes(),b'documento sintetico')
        self.assertFalse(source.exists()); self.assertEqual(ids(dest/'OFX Limpo.ofx'),['A','B'])
        self.assertEqual(ids(plan.geral),['A','B'])
    def test_segunda_importacao_e_sem_novidades(self):
        src=self.root/'one.ofx'; src.write_bytes(fixture([tx(10,'A')]))
        executar(planejar(self.root,self.bank,src,hoje=D))
        src=self.root/'two.ofx'; src.write_bytes(fixture([tx(10,'A'),tx(11,'B')]))
        plan=planejar(self.root,self.bank,src,hoje=D); dest=executar(plan)
        self.assertEqual(dest.name,'002'); self.assertEqual(ids(dest/'OFX Limpo.ofx'),['B'])
        self.assertEqual(ids(plan.geral),['A','B'])
        src=self.root/'three.ofx'; src.write_bytes(fixture([tx(10,'A'),tx(11,'B')]))
        plan=planejar(self.root,self.bank,src,hoje=D); self.assertEqual(plan.resultado.relatorio.estado,'SEM_NOVIDADES')
        before=plan.geral.read_bytes(); dest=executar(plan)
        self.assertEqual(dest.name,'003'); self.assertEqual(ids(dest/'OFX Limpo.ofx'),[])
        self.assertEqual(plan.geral.read_bytes(),before)
    def test_historico_cronologico(self):
        old=self.old(date(2024,12,31),[tx(10,'A')]); recent=self.old(date(2025,1,1),[tx(10,'A')])
        newest=self.old(date(2026,10,31),[tx(10,'A')])
        self.assertEqual(localizar_historico(self.bank,D),newest)
        today=self.old(D,[tx(10,'A')]); self.assertEqual(localizar_historico(self.bank,D),today)
        self.assertNotEqual(old,recent)
    def test_lacuna_pastas_e_historico_perdido(self):
        day=pasta_dia(self.bank,D); day.mkdir(parents=True)
        (day/'001').mkdir(); (day/'003').mkdir()
        self.assertEqual(proxima_importacao(day).name,'004')
        with self.assertRaises(OrganizacaoError): localizar_historico(self.bank,D)
    def test_futuro_corrompido_e_conta(self):
        future=self.old(date(2026,11,13),[tx(10,'A')])
        with self.assertRaises(OrganizacaoError): localizar_historico(self.bank,D)
        future.unlink(); future.parent.rmdir()
        today=self.old(D,[tx(10,'A')]); today.write_bytes(b'malformado')
        src=self.root/'current.ofx'; src.write_bytes(fixture([tx(10,'A')]))
        with self.assertRaises(Exception): planejar(self.root,self.bank,src,hoje=D)
        today.write_bytes(fixture([tx(10,'A')],account='999'))
        with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,src,hoje=D)
        self.assertTrue(src.exists()); self.assertFalse((today.parent/'001').exists())
    def test_conflict_and_missing_intersection(self):
        self.old(D,[tx(10,'A')]); src=self.root/'current.ofx'
        for item in ([tx(10,'A','11')],[tx(11,'B')]):
            src.write_bytes(fixture(item))
            with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,src,hoje=D)
            self.assertTrue(src.exists()); self.assertFalse((pasta_dia(self.bank,D)/'001').exists())
    def test_historico_recente_conta_diferente_nao_faz_fallback(self):
        self.old(date(2026,11,10),[tx(10,'A')])
        recent=self.old(date(2026,11,11),[tx(10,'A')])
        recent.write_bytes(fixture([tx(10,'A')],account='999'))
        src=self.root/'current.ofx'; src.write_bytes(fixture([tx(10,'A')]))
        with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,src,hoje=D)
        self.assertTrue(src.exists()); self.assertFalse(pasta_dia(self.bank,D).exists())
    def test_ambiguous_choice(self):
        src=self.root/'x.ofx'; src.write_bytes(fixture([('20261110120000','10','A','Café')],'utf-8'))
        from controller.ofx_io import OFXEncodingAmbiguaError
        with self.assertRaises(OFXEncodingAmbiguaError): planejar(self.root,self.bank,src,hoje=D)
        plan=planejar(self.root,self.bank,src,hoje=D,leitor=lambda p:carregar_ofx(p,codificacao='utf-8'))
        self.assertEqual(plan.resultado.relatorio.estado,'PRIMEIRA_IMPORTACAO')
    def test_menu_ambiguidade_cancelar_e_escolher(self):
        from comparaArqOFX import main
        src=self.root/'x.ofx'; raw=fixture([('20261110120000','10','A','Café')],'utf-8'); src.write_bytes(raw)
        choices=iter(['1','0'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertEqual(src.read_bytes(),raw); self.assertEqual(list(self.bank.iterdir()),[])
        choices=iter(['1','1'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertFalse(src.exists())
        copies=list(self.bank.rglob('x.ofx')); self.assertEqual(len(copies),1)
        self.assertEqual(copies[0].read_bytes(),raw)
    def test_menu_ambiguidade_historico(self):
        from comparaArqOFX import main
        day=date.today(); folder=pasta_dia(self.bank,day); folder.mkdir(parents=True)
        general=folder/f'OFXGeral-{day.isoformat()}.ofx'
        raw=fixture([('20261110120000','10','A','Café')],'utf-8'); general.write_bytes(raw)
        src=self.root/'x.ofx'; src.write_bytes(fixture([tx(10,'A'),tx(11,'B')]))
        before=src.read_bytes(); choices=iter(['1','0'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertEqual(general.read_bytes(),raw); self.assertEqual(src.read_bytes(),before)
        choices=iter(['1','1'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertEqual(ids(general),['A','B']); self.assertFalse(src.exists())
    def test_sem_novidades_em_dia_posterior_preserva_referencia(self):
        anterior=self.old(date(2026,11,11),[tx(10,'A')]); src=self.root/'x.ofx'
        src.write_bytes(fixture([tx(10,'A')]))
        plan=planejar(self.root,self.bank,src,hoje=D)
        self.assertEqual(plan.resultado.relatorio.estado,'SEM_NOVIDADES')
        output=executar(plan)
        self.assertEqual(ids(output/'OFX Limpo.ofx'),[])
        self.assertEqual(ids(plan.geral),['A']); self.assertEqual(ids(anterior),['A'])
    def test_arquivo_modificado_apos_plano_bloqueia(self):
        src=self.root/'x.ofx'; src.write_bytes(fixture([tx(10,'A')]))
        plan=planejar(self.root,self.bank,src,hoje=D); src.write_bytes(b'alterado')
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual(src.read_bytes(),b'alterado'); self.assertFalse(plan.dia.exists())
    def test_menu_ambiguidade_cancelar_e_escolher_repeticao(self):
        from comparaArqOFX import main
        src=self.root/'x.ofx'; raw=fixture([('20261110120000','10','A','Café')],'utf-8'); src.write_bytes(raw)
        choices=iter(['1','0'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertEqual(src.read_bytes(),raw); self.assertEqual(list(self.bank.iterdir()),[])
        choices=iter(['1','1'])
        self.assertEqual(main(self.root,lambda _:next(choices),lambda _:None),0)
        self.assertFalse(src.exists())
        copies=list(self.bank.rglob('x.ofx')); self.assertEqual(len(copies),1)
        self.assertEqual(copies[0].read_bytes(),raw)
    def test_sem_novidades_em_dia_posterior_preserva_referencia_repeticao(self):
        anterior=self.old(date(2026,11,11),[tx(10,'A')]); src=self.root/'x.ofx'
        src.write_bytes(fixture([tx(10,'A')]))
        plan=planejar(self.root,self.bank,src,hoje=D)
        self.assertEqual(plan.resultado.relatorio.estado,'SEM_NOVIDADES')
        output=executar(plan)
        self.assertEqual(ids(output/'OFX Limpo.ofx'),[])
        self.assertEqual(ids(plan.geral),['A']); self.assertEqual(ids(anterior),['A'])
    def test_arquivo_modificado_apos_plano_bloqueia_repeticao(self):
        src=self.root/'x.ofx'; src.write_bytes(fixture([tx(10,'A')]))
        plan=planejar(self.root,self.bank,src,hoje=D); src.write_bytes(b'alterado')
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual(src.read_bytes(),b'alterado'); self.assertFalse(plan.dia.exists())
    def test_only_selected_file_moved(self):
        source=self.root/'one.ofx'; source.write_bytes(fixture([tx(10,'A')]))
        other=self.root/'two.OFX'; other.write_bytes(b'outro'); attachment=self.root/'outro.pdf'; attachment.write_bytes(b'pdf')
        executar(planejar(self.root,self.bank,source,hoje=D))
        self.assertEqual(other.read_bytes(),b'outro'); self.assertEqual(attachment.read_bytes(),b'pdf')
    def test_raiz_frozen_nao_cwd(self):
        with patch('sys.frozen',True,create=True), patch('sys.executable',str(self.root/'app.exe')):
            (self.root/'app.exe').write_bytes(b'x')
            self.assertEqual(raiz_aplicacao(),self.root)
    def test_symlink_recusado(self):
        with tempfile.TemporaryDirectory() as outside:
            try: (self.bank/'2026').symlink_to(outside,target_is_directory=True)
            except OSError: self.skipTest('links indisponíveis')
            with self.assertRaises(OrganizacaoError): localizar_historico(self.bank,D)
