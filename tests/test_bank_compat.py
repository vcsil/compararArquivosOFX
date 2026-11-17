"""Somente dados inventados: regressões técnicas observadas em exportadores."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import warnings
from datetime import date
from decimal import Decimal
from test_baseline import fixture, A
from controller.ofx_functions import carregar_ofx
from controller.ofx_io import interpretar_ofx, serializar_ofx
from controller.ofx_compat import OFXCompatError
from controller.ofx_comparison import analisar, identificar_conta
from controller.organization import localizar_historico, OrganizacaoError, anexos
from controller.workflow import planejar, executar, _assinatura
from controller import safe_storage as ss

D = date(2026,11,16)


def longo(raw, suffix='A'):
    org = ('Instituicao Financeira Sintetica de Teste ' + suffix).encode()
    return raw.replace(b'<LANGUAGE>POR', b'<LANGUAGE>POR<FI><ORG>'+org+b'<FID>SYNTH</FI>')


def zeros(raw):
    return raw.replace(b'<DTSERVER>20230103120000', b'<DTSERVER>00000000000000').replace(b'<DTASOF>20230103120000', b'<DTASOF>00000000000000')


class Compatibilidade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.bank = self.root/'Banco'; self.bank.mkdir()
    def ler(self, raw):
        p = self.root/'input.ofx'; p.write_bytes(raw)
        model = carregar_ofx(p)[1]
        self.assertEqual(p.read_bytes(),raw)
        self.assertEqual(_assinatura(model),_assinatura(interpretar_ofx('xml',serializar_ofx(model))))
        return model
    def test_org_longo_deterministico_distinto_e_sem_alterar_financas(self):
        base=self.ler(fixture([A])); first=self.ler(longo(fixture([A])))
        again=self.ler(longo(fixture([A])));other=self.ler(longo(fixture([A]),'B'))
        self.assertEqual(identificar_conta(first),identificar_conta(again))
        self.assertEqual(len(identificar_conta(first).instituicao),32)
        self.assertNotEqual(identificar_conta(first).instituicao,identificar_conta(other).instituicao)
        a=base.statements[0].transactions[0];b=first.statements[0].transactions[0]
        self.assertEqual((a.fitid,a.dtposted,a.trnamt,a.trntype),(b.fitid,b.dtposted,b.trnamt,b.trntype))
        self.assertEqual(analisar(again, first).relatorio.estado,'SEM_NOVIDADES')
        self.assertEqual(analisar(other, first).relatorio.estado,'BLOQUEADO')
    def test_datas_zero_usam_apenas_dtend_verificavel_sem_relogio(self):
        m=self.ler(zeros(fixture([A])));stmt=m.statements[0]
        self.assertEqual(m.signonmsgsrsv1.sonrs.dtserver,stmt.banktranlist.dtend)
        self.assertEqual(stmt.ledgerbal.dtasof,stmt.banktranlist.dtend)
        self.assertEqual(stmt.ledgerbal.balamt,Decimal('100'))
        self.assertEqual(stmt.transactions[0].dtposted,self.ler(fixture([A])).statements[0].transactions[0].dtposted)
        with self.assertRaises(OFXCompatError):self.ler(zeros(fixture([A])).replace(b'<DTEND>20230103120000',b'<DTEND>00000000'))
    def test_data_invalida_nao_zero_e_transacao_invalida_bloqueiam(self):
        for raw in (fixture([A]).replace(b'<DTSERVER>20230103120000',b'<DTSERVER>invalid'),
                    fixture([A]).replace(b'<DTPOSTED>20230102120000',b'<DTPOSTED>00000000')):
            with self.assertRaises(OFXCompatError):self.ler(raw)
    def test_version_100_e_tipos_in_out_com_sinal_validado(self):
        raw=fixture([A]).replace(b'VERSION:102',b'VERSION:100').replace(b'<TRNTYPE>CREDIT',b'<TRNTYPE>IN')
        self.assertEqual(self.ler(raw).statements[0].transactions[0].trntype,'CREDIT')
        neg=raw.replace(b'<TRNTYPE>IN',b'<TRNTYPE>OUT').replace(b'<TRNAMT>20',b'<TRNAMT>-20')
        self.assertEqual(self.ler(neg).statements[0].transactions[0].trnamt,Decimal('-20'))
        with self.assertRaises(OFXCompatError):self.ler(raw.replace(b'<TRNTYPE>IN',b'<TRNTYPE>OUT'))
    def test_saldo_ausente_nao_e_inventado(self):
        with self.assertRaises(OFXCompatError):self.ler(fixture([A]).replace(b'<BALAMT>100',b'<BALAMT>null'))
    def test_conta_externa_unica_realocada_sem_inventar_identidade(self):
        raw=fixture([A]);start=raw.index(b'<BANKACCTFROM>');end=raw.index(b'</BANKACCTFROM>')+len(b'</BANKACCTFROM>')
        acct=raw[start:end];relocated=raw[:start]+raw[end:];relocated=relocated.replace(b'<OFX>',b'<OFX>'+acct)
        self.assertEqual(identificar_conta(self.ler(raw)),identificar_conta(self.ler(relocated)))
        with self.assertRaises(OFXCompatError):self.ler(relocated.replace(b'<OFX>',b'<OFX>'+acct))
        with self.assertRaises(OFXCompatError):self.ler(relocated.replace(b'<ACCTTYPE>CHECKING',b'<ACCTTYPE>CC'))
    def test_ordem_de_resposta_reparada_sem_mudar_transacoes(self):
        raw=fixture([A]);a=raw.index(b'<SIGNONMSGSRSV1>');b=raw.index(b'</SIGNONMSGSRSV1>')+len(b'</SIGNONMSGSRSV1>')
        signon=raw[a:b];altered=(raw[:a]+raw[b:]).replace(b'</OFX>',signon+b'</OFX>')
        altered=altered.replace(b'<TRNUID>1',b'').replace(b'</STMTTRNRS>',b'<TRNUID>1</STMTTRNRS>')
        self.assertEqual(_assinatura(self.ler(raw)),_assinatura(self.ler(altered)))
    def test_serializacao_nao_imprime_texto_longo_e_preserva_o_campo(self):
        texto='TEXTO-SINTETICO-NAO-IMPRIMIR-' * 3
        raw=fixture([A]).replace(b'<MEMO>', b'<NAME>'+texto.encode()+b'<MEMO>')
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            model=self.ler(raw)
            payload=serializar_ofx(model)
        self.assertEqual(captured, [])
        restored=interpretar_ofx('xml',payload)
        self.assertEqual(restored.statements[0].transactions[0].name,texto)
    def test_erro_nao_divulga_conteudo_financeiro(self):
        with self.assertRaises(OFXCompatError) as cm:self.ler(fixture([A]).replace(b'<TRNTYPE>CREDIT',b'<TRNTYPE>SEGREDO-FINANCEIRO'))
        self.assertNotIn('SEGREDO',str(cm.exception))
    def historico(self, layout, raw=None, name=None):
        day=self.bank/layout;day.mkdir(parents=True);(day/'01').mkdir()
        path=day/(name or 'OFXGeral-2026-11-12.ofx');path.write_bytes(raw or fixture([A]));return path
    def test_legado_mes_sem_ano_diretorio_e_importacao_dois_digitos(self):
        hist=self.historico('11 - Nov 2026/2026-11-12',longo(fixture([A])))
        self.assertEqual(localizar_historico(self.bank,D),hist)
        src=self.root/'novo.ofx';raw=longo(fixture([A,('20230103120000','10','NEW','Novo')]))
        src.write_bytes(raw);old=hist.read_bytes();p=planejar(self.root,self.bank,src,hoje=D);executar(p)
        self.assertEqual(hist.read_bytes(),old);self.assertEqual((p.importacao/src.name).read_bytes(),raw)
        self.assertEqual(len(carregar_ofx(p.geral)[1].statements[0].transactions),1)
    def test_mes_extenso_e_geral_antigo_bradesco(self):
        hist=self.historico('2026/11 - Novembro/2026-11-12',zeros(fixture([A])), 'Bradesco Geral - 2026-11-12.ofx')
        self.assertEqual(localizar_historico(self.bank,D),hist)
        src=self.root/'novo.ofx';src.write_bytes(zeros(fixture([A,('20230103120000','10','NEW','Novo')])))
        p=planejar(self.root,self.bank,src,hoje=D);old=hist.read_bytes();real=ss.publicar_arquivo
        def stop(*a):real(*a);raise OSError('injetada')
        with patch.object(ss,'publicar_arquivo',side_effect=stop),self.assertRaises(OSError):executar(p)
        with ss.bloquear(self.bank):ss.recuperar_concluida(self.bank)
        self.assertEqual(hist.read_bytes(),old);self.assertFalse(src.exists())
    def test_numeracao_nova_respeita_importacao_legada_dois_digitos(self):
        from controller.organization import proxima_importacao
        folder=self.bank/'dia';folder.mkdir();(folder/'01').mkdir()
        self.assertEqual(proxima_importacao(folder).name,'002')
    def test_legado_no_mesmo_dia_nao_cria_dois_gerais(self):
        hist=self.historico('11 - Nov 2026/2026-11-12')
        src=self.root/'novo.ofx';src.write_bytes(fixture([A]))
        with self.assertRaisesRegex(OrganizacaoError,'mesmo dia'):
            planejar(self.root,self.bank,src,hoje=date(2026,11,12))
        self.assertTrue(src.exists());self.assertEqual(hist.read_bytes(),fixture([A]))
    def test_geral_data_divergente_ou_multiplo_nao_e_escolhido(self):
        hist=self.historico('2026/11 - Nov 2026/2026-11-12',name='OFXGeral-2026-11-11.ofx')
        with self.assertRaises(OrganizacaoError):localizar_historico(self.bank,D)
        hist.rename(hist.parent/'OFXGeral-2026-11-12.ofx')
        (hist.parent/'Bradesco Geral - 2026-11-12.ofx').write_bytes(fixture([A]))
        with self.assertRaises(OrganizacaoError):localizar_historico(self.bank,D)
    def test_anexos_xls_xlsx_pdf_html_opacos_preservados_e_recuperados(self):
        src=self.root/'novo.ofx';src.write_bytes(fixture([A]));extras=[]
        for ext in ('.xls','.xlsx','.pdf','.html'):
            path=self.root/('anexo'+ext);path.write_bytes(b'conteudo opaco sintetico');extras.append(path)
        (self.root/'nao-executar.exe').write_bytes(b'EXE');self.assertEqual(set(anexos(self.root)),set(extras))
        p=planejar(self.root,self.bank,src,extras,hoje=D);real=Path.unlink
        def stop(path,*a,**kw):
            if path.exists() and path.samefile(extras[0]):raise OSError('interrupcao anexo')
            return real(path,*a,**kw)
        with patch.object(Path,'unlink',stop),self.assertRaises(OSError):executar(p)
        with ss.bloquear(self.bank):ss.recuperar_concluida(self.bank)
        for path in extras:
            self.assertFalse(path.exists());self.assertEqual((p.importacao/path.name).read_bytes(),b'conteudo opaco sintetico')
    def test_anexo_xls_interrupcao_durante_copia_preserva_origem(self):
        import shutil
        src=self.root/'novo.ofx';src.write_bytes(fixture([A]))
        xls=self.root/'anexo.xls';xls.write_bytes(b'sintetico')
        plan=planejar(self.root,self.bank,src,[xls],hoje=D)
        real=shutil.copyfileobj
        def stop(source,dest,*a,**kw):
            real(source,dest,*a,**kw)
            if Path(dest.name).suffix=='.xls':raise OSError('falha de copia sintetica')
        with patch.object(shutil,'copyfileobj',side_effect=stop),self.assertRaises(OSError):executar(plan)
        self.assertEqual(xls.read_bytes(),b'sintetico');self.assertTrue(src.exists())
        with ss.bloquear(self.bank):ss.recuperar_concluida(self.bank)
        executar(planejar(self.root,self.bank,src,[xls],hoje=D))
        self.assertEqual((plan.importacao/xls.name).read_bytes(),b'sintetico')
    def test_legado_fitid_com_valor_divergente_bloqueia_preservando(self):
        hist=self.historico('11 - Nov 2026/2026-11-12')
        src=self.root/'novo.ofx';raw=fixture([('20230102120000','21','2','Conflito')]);src.write_bytes(raw)
        with self.assertRaises(OrganizacaoError):planejar(self.root,self.bank,src,hoje=D)
        self.assertEqual(src.read_bytes(),raw);self.assertEqual(hist.read_bytes(),fixture([A]))
    @unittest.skipIf(os.name == 'nt', 'Windows usa mutex do kernel, sem lock no volume')
    def test_lock_zero_links_falha_segura_e_hardlink_real_rejeitado(self):
        real=os.fstat
        def zero(fd):
            result=real(fd)
            class Metadata:st_nlink=0
            return Metadata()
        with patch.object(ss.os,'fstat',side_effect=zero),self.assertRaisesRegex(OrganizacaoError,'não verificável'):
            with ss.bloquear(self.bank):pass
        with ss.bloquear(self.bank):pass
        lock=next((self.root/'.comparaofx-locks').iterdir());os.link(lock,self.root/'alias.lock')
        with self.assertRaisesRegex(OrganizacaoError,'hardlinks'):
            with ss.bloquear(self.bank):pass
    def test_onedrive_nome_nao_substitui_verificacao_de_capacidades(self):
        with patch.dict(os.environ, {'OneDrive': str(self.root)}):
            with ss.bloquear(self.bank) as token:
                self.assertTrue(ss.bloqueio_valido(token, self.bank.resolve()))
    def test_lock_concorrente_entre_processos_e_preexistente(self):
        # O filho mantém o lock até receber uma linha, sem depender de sleeps.
        code="""import sys
from pathlib import Path
from controller.safe_storage import bloquear
with bloquear(Path(sys.argv[1])):
 print('READY',flush=True)
 sys.stdin.readline()
"""
        env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        child=subprocess.Popen([sys.executable,'-c',code,str(self.bank)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            self.assertEqual(child.stdout.readline().strip(),'READY')
            with self.assertRaises(OrganizacaoError):
                with ss.bloquear(self.bank):pass
        finally:
            child.communicate('\n',timeout=15)
        self.assertEqual(child.returncode,0)
        with ss.bloquear(self.bank):pass


class ZipPrivado(unittest.TestCase):
    def test_auditoria_independente_preserva_decimal_com_virgula(self):
        path=Path(__file__).resolve().parents[1]/'scripts/audit_private_zip.py'
        spec=importlib.util.spec_from_file_location('private_audit_decimal',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'sintetico.ofx'
            source.write_bytes(fixture([A]).replace(b'<TRNAMT>20',b'<TRNAMT>20,00').replace(b'<BALAMT>100',b'<BALAMT>100,00'))
            module.conferir_financas_originais(source,carregar_ofx(source)[1],None)
    def test_zip_seguro_rejeita_traversal_symlink_e_nao_executa_anexos(self):
        path=Path(__file__).resolve().parents[1]/'scripts/audit_private_zip.py'
        spec=importlib.util.spec_from_file_location('private_audit',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('../escape', '/absolute', 'C:/escape', '.. /escape', 'folder./escape', 'CON.txt', 'LPT1', 'tab\tname'):
                with zipfile.ZipFile(root/'bad.zip','w') as z:z.writestr(name,b'bad')
                with self.assertRaises(ValueError):module.extrair_seguro(root/'bad.zip',root/'out')
            with zipfile.ZipFile(root/'bad.zip','w') as z:
                info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,b'outside')
            with self.assertRaises(ValueError):module.extrair_seguro(root/'bad.zip',root/'out')
            with zipfile.ZipFile(root/'ok.zip','w') as z:z.writestr('nao-executar.exe',b'not an executable')
            module.extrair_seguro(root/'ok.zip',root/'out');self.assertEqual((root/'out/nao-executar.exe').read_bytes(),b'not an executable')
