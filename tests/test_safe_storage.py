import io
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from test_baseline import limpo_em, fixture
from controller import safe_storage as ss
from controller.workflow import planejar, executar
from controller.organization import OrganizacaoError, pasta_dia
from controller.ofx_functions import carregar_ofx

D=date(2026,11,12)
def tx(day,id,amount='10'): return (f'202611{day:02d}120000',amount,id,'Teste')
class Seguranca(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.bank=self.root/'Banco'; self.bank.mkdir()
        self.src=self.root/'atual.ofx'; self.raw=fixture([tx(10,'A'),tx(11,'B')]); self.src.write_bytes(self.raw)
        self.pdf=self.root/'anexo.pdf'; self.pdf.write_bytes(b'PDF sintetico')
        day=pasta_dia(self.bank,D); day.mkdir(parents=True)
        self.geral=day/f'OFXGeral-{D.isoformat()}.ofx'; self.old=fixture([tx(10,'A')]); self.geral.write_bytes(self.old)
    def plan(self): return planejar(self.root,self.bank,self.src,[self.pdf],hoje=D)
    def check_pending(self):
        with self.assertRaises(OrganizacaoError): ss.exigir_sem_pendencias(self.bank)
        with ss.bloquear(self.bank):
            try: ss.recuperar_concluida(self.bank)
            except OrganizacaoError: pass
        self.assertTrue(self.src.exists())
    def test_falha_temporario_antes_publicacao(self):
        plan=self.plan(); original=ss.escrever
        def fail(path,data):
            if Path(path).name=='geral.tmp': raise OSError('disco cheio')
            return original(path,data)
        with patch.object(ss,'escrever',side_effect=fail):
            with self.assertRaises(OSError): executar(plan)
        self.assertEqual(self.geral.read_bytes(),self.old); self.assertEqual(self.src.read_bytes(),self.raw)
        self.assertFalse(plan.importacao.exists()); self.check_pending()
        self.assertEqual(ss.pendencias(self.bank),[])
    def test_preparacao_alteracao_origem_bloqueia_limpeza(self):
        plan=self.plan(); real=ss.escrever
        def fail(path,data):
            if Path(path).name=='geral.tmp': raise OSError('interrompido')
            return real(path,data)
        with patch.object(ss,'escrever',side_effect=fail):
            with self.assertRaises(OSError): executar(plan)
        self.pdf.write_bytes(b'alterado')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.pdf.read_bytes(),b'alterado'); self.assertTrue(ss.pendencias(self.bank))
    def test_preparacao_arquivo_desconhecido_bloqueia_limpeza(self):
        plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        op=ss.pendencias(self.bank)[0]; (op/'desconhecido').write_bytes(b'preservar')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual((op/'desconhecido').read_bytes(),b'preservar')
    def test_preparacao_historico_alterado_bloqueia_limpeza(self):
        plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        self.geral.write_bytes(b'historico externo')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.geral.read_bytes(),b'historico externo'); self.assertTrue(ss.pendencias(self.bank))
    def test_preparacao_destino_ocupado_bloqueia_limpeza(self):
        plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        plan.importacao.mkdir(); (plan.importacao/'outro').write_text('preservar')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual((plan.importacao/'outro').read_text(),'preservar'); self.assertTrue(ss.pendencias(self.bank))
    def test_preparacao_temporario_trocado_bloqueia_limpeza(self):
        plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        op=ss.pendencias(self.bank)[0]; temp=op/'pasta'/'anexo.pdf'; temp.write_bytes(b'outro')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(temp.read_bytes(),b'outro'); self.assertTrue(ss.pendencias(self.bank))
    def test_preparacao_geral_criado_externamente_bloqueia_limpeza(self):
        self.geral.unlink(); plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        self.geral.write_bytes(b'externo')
        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.geral.read_bytes(),b'externo'); self.assertTrue(ss.pendencias(self.bank))
    def test_falha_escrita_temporaria_parcial(self):
        plan=self.plan(); original=ss.escrever
        def fail(path,data):
            if Path(path).name=='geral.tmp':
                Path(path).write_bytes(data[:10]); raise OSError('disco cheio')
            return original(path,data)
        with patch.object(ss,'escrever',side_effect=fail):
            with self.assertRaises(OSError): executar(plan)
        self.assertEqual(self.geral.read_bytes(),self.old); self.assertFalse(plan.importacao.exists()); self.check_pending()
        self.assertTrue(ss.pendencias(self.bank), 'temporário parcial sem hash verificável deve permanecer')
    def test_falha_antes_publicar_geral(self):
        plan=self.plan()
        with patch.object(ss,'publicar_arquivo',side_effect=OSError('bloqueado')):
            with self.assertRaises(OSError): executar(plan)
        self.assertTrue(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old)
        self.assertEqual(self.src.read_bytes(),self.raw); self.check_pending()
    def test_falha_antes_publicar_pasta(self):
        plan=self.plan()
        with patch.object(ss,'publicar_pasta',side_effect=OSError('sem espaço')):
            with self.assertRaises(OSError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old)
        self.assertEqual(self.src.read_bytes(),self.raw); self.check_pending()
    def test_alteracao_externa_depois_pasta_bloqueia(self):
        plan=self.plan(); publish=ss.publicar_pasta
        def modify(*args):
            publish(*args); self.geral.write_bytes(b'modificado externamente')
        with patch.object(ss,'publicar_pasta',side_effect=modify):
            with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual(self.geral.read_bytes(),b'modificado externamente')
        self.assertEqual(self.src.read_bytes(),self.raw); self.check_pending()
    def test_origem_alterada_apos_publicar_nao_e_removida(self):
        plan=self.plan(); publish=ss.publicar_arquivo
        def modify(*args):
            publish(*args); self.src.write_bytes(b'alterado externamente')
        with patch.object(ss,'publicar_arquivo',side_effect=modify):
            with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual(self.src.read_bytes(),b'alterado externamente')
        self.assertEqual((plan.importacao/self.src.name).read_bytes(),self.raw)
        self.check_pending()
    def test_geral_novo_concorrente_nao_e_sobrescrito(self):
        self.geral.unlink(); plan=self.plan(); publish=ss.publicar_pasta
        def create(*args):
            publish(*args); self.geral.write_bytes(b'arquivo de outro processo')
        with patch.object(ss,'publicar_pasta',side_effect=create):
            with self.assertRaises(FileExistsError): executar(plan)
        self.assertEqual(self.geral.read_bytes(),b'arquivo de outro processo')
        self.assertEqual(self.src.read_bytes(),self.raw); self.check_pending()
    def test_falha_depois_publicar_geral(self):
        plan=self.plan(); pub=ss.publicar_arquivo
        def fail(*args): pub(*args); raise OSError('interrompido')
        with patch.object(ss,'publicar_arquivo',side_effect=fail):
            with self.assertRaises(OSError): executar(plan)
        self.assertEqual([t.fitid for t in carregar_ofx(self.geral)[1].statements[0].transactions],['A','B'])
        self.assertEqual(self.src.read_bytes(),self.raw)
        with ss.bloquear(self.bank): ss.recuperar_concluida(self.bank)
        self.assertFalse(self.src.exists()); self.assertEqual(ss.pendencias(self.bank),[])
    def test_historico_alterado_depois_plano(self):
        plan=self.plan(); self.geral.write_bytes(b'externo')
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual(self.geral.read_bytes(),b'externo')
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertFalse(plan.importacao.exists())
    def test_destino_concorrente_nao_sobrescrito(self):
        plan=self.plan(); plan.importacao.mkdir(); (plan.importacao/'user.txt').write_text('original')
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertEqual((plan.importacao/'user.txt').read_text(),'original'); self.assertEqual(self.src.read_bytes(),self.raw)
    def test_falha_copia_pdf(self):
        plan=self.plan(); import controller.workflow as w
        real=w.shutil.copyfileobj; count=[0]
        def fail(src,dst):
            count[0]+=1
            if count[0]==2: raise PermissionError('acesso negado')
            return real(src,dst)
        with patch.object(w.shutil,'copyfileobj',side_effect=fail):
            with self.assertRaises(PermissionError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_falha_copia_ofx(self):
        plan=self.plan()
        with patch('controller.workflow.shutil.copyfileobj',side_effect=OSError('cópia interrompida')):
            with self.assertRaises(OSError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.src.read_bytes(),self.raw)
        self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_hash_da_copia_divergente_bloqueia(self):
        from controller import workflow
        plan=self.plan(); real=workflow._hash
        def wrong(path):
            if Path(path).name=='anexo.pdf' and '.comparaofx' in str(path): return bytes(32)
            return real(path)
        with patch.object(workflow,'_hash',side_effect=wrong):
            with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old)
        self.assertEqual(self.pdf.read_bytes(),b'PDF sintetico'); self.check_pending()
    def test_falha_gravar_limpo_nao_publica(self):
        plan=self.plan(); real=ss.escrever
        def fail(path,data):
            if Path(path).name==plan.limpo_nome: raise PermissionError('arquivo bloqueado')
            return real(path,data)
        with patch.object(ss,'escrever',side_effect=fail):
            with self.assertRaises(PermissionError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old)
        self.assertEqual(self.src.read_bytes(),self.raw); self.check_pending()
    def test_limpo_invalido_nao_publica(self):
        plan=self.plan(); plan.limpo=b'OFX invalido'
        with self.assertRaises(Exception): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_geral_invalido_nao_publica(self):
        plan=self.plan(); plan.geral_bytes=b'OFX invalido'
        with self.assertRaises(Exception): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_geral_valido_com_valor_divergente_nao_publica(self):
        from controller.ofx_io import serializar_ofx
        plan=self.plan(); falso=carregar_ofx(self.geral)[1]
        falso.statements[0].transactions[0].trnamt=99
        plan.geral_bytes=serializar_ofx(falso)
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_geral_valido_com_saldo_divergente_nao_publica(self):
        from controller.ofx_io import interpretar_ofx, serializar_ofx
        plan=self.plan(); falso=interpretar_ofx('xml',plan.geral_bytes)
        falso.statements[0].ledgerbal.balamt=99
        plan.geral_bytes=serializar_ofx(falso)
        with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertEqual(self.geral.read_bytes(),self.old); self.check_pending()
    def test_recuperacao_apos_remocao_parcial(self):
        plan=self.plan(); unlink=Path.unlink
        def crash(path,*args,**kwargs):
            is_source=path.exists() and path.samefile(self.src)
            result=unlink(path,*args,**kwargs)
            if is_source: raise OSError('interrupção após remover origem')
            return result
        with patch.object(Path,'unlink',crash):
            with self.assertRaises(OSError): executar(plan)
        self.assertFalse(self.src.exists()); self.assertTrue(self.pdf.exists())
        self.assertEqual((plan.importacao/self.src.name).read_bytes(),self.raw)
        with ss.bloquear(self.bank):
            ss.recuperar_concluida(self.bank); ss.recuperar_concluida(self.bank)
        self.assertFalse(self.pdf.exists()); self.assertEqual((plan.importacao/self.pdf.name).read_bytes(),b'PDF sintetico')
        self.assertEqual([t.fitid for t in carregar_ofx(self.geral)[1].statements[0].transactions],['A','B'])
    def test_recuperacao_bloqueia_origem_alterada(self):
        plan=self.plan(); old=ss.publicar_arquivo
        def crash(*args): old(*args); raise OSError('interrompido')
        with patch.object(ss,'publicar_arquivo',side_effect=crash):
            with self.assertRaises(OSError): executar(plan)
        self.pdf.write_bytes(b'externo')
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.pdf.read_bytes(),b'externo'); self.assertEqual(self.src.read_bytes(),self.raw)
    def test_recuperacao_bloqueia_historico_alterado(self):
        plan=self.plan(); old=ss.publicar_arquivo
        def crash(*args): old(*args); raise OSError('interrompido')
        with patch.object(ss,'publicar_arquivo',side_effect=crash):
            with self.assertRaises(OSError): executar(plan)
        self.geral.write_bytes(b'historico externo')
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.geral.read_bytes(),b'historico externo')
        self.assertEqual(self.src.read_bytes(),self.raw)
    def test_recuperacao_bloqueia_referencia_de_outro_dia_alterada(self):
        self.geral.unlink()
        previous_day=date(2026,11,11); previous=pasta_dia(self.bank,previous_day)
        previous.mkdir(parents=True); reference=previous/f'OFXGeral-{previous_day.isoformat()}.ofx'
        reference.write_bytes(self.old); plan=self.plan(); old=ss.publicar_arquivo
        def crash(*args): old(*args); raise OSError('interrompido')
        with patch.object(ss,'publicar_arquivo',side_effect=crash):
            with self.assertRaises(OSError): executar(plan)
        reference.write_bytes(b'alterado')
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertEqual(reference.read_bytes(),b'alterado')
    def test_primeira_importacao_recupera_apos_publicacao(self):
        self.geral.unlink(); plan=self.plan(); old=ss.publicar_arquivo
        def crash(*args): old(*args); raise OSError('interrompido')
        with patch.object(ss,'publicar_arquivo',side_effect=crash):
            with self.assertRaises(OSError): executar(plan)
        with ss.bloquear(self.bank): ss.recuperar_concluida(self.bank)
        self.assertFalse(self.src.exists()); self.assertEqual((plan.importacao/self.src.name).read_bytes(),self.raw)
        self.assertEqual([t.fitid for t in carregar_ofx(self.geral)[1].statements[0].transactions],['A','B'])
    def test_primeira_importacao_valida_semanticamente_ambos_arquivos(self):
        from controller import ofx_functions
        self.geral.unlink(); plan=self.plan(); real=ofx_functions.carregar_ofx; nomes=[]
        def read(path,*args,**kwargs):
            nomes.append(Path(path).name)
            return real(path,*args,**kwargs)
        with patch.object(ofx_functions,'carregar_ofx',side_effect=read): executar(plan)
        self.assertEqual(nomes,[plan.limpo_nome,'geral.tmp'])
        self.assertEqual([t.fitid for t in carregar_ofx(self.geral)[1].statements[0].transactions],['A','B'])
    def test_geral_temporario_corrompido_e_detectado_mesmo_identico(self):
        self.geral.unlink(); plan=self.plan(); real=ss.escrever
        def corrupt(path,data):
            real(path,data)
            if Path(path).name=='geral.tmp': Path(path).write_bytes(b'corrompido')
        with patch.object(ss,'escrever',side_effect=corrupt):
            with self.assertRaises(OrganizacaoError): executar(plan)
        self.assertFalse(plan.importacao.exists()); self.assertFalse(self.geral.exists())
        self.assertEqual(self.src.read_bytes(),self.raw); self.assertTrue(ss.pendencias(self.bank))
    def test_sem_novidades_nao_regrava_geral(self):
        self.src.write_bytes(self.old); plan=self.plan(); before=self.geral.read_bytes()
        self.assertEqual(plan.resultado.relatorio.estado,'SEM_NOVIDADES')
        with patch.object(ss,'publicar_arquivo',side_effect=AssertionError('não deve regravar')):
            dest=executar(plan)
        self.assertEqual(self.geral.read_bytes(),before)
        self.assertEqual(carregar_ofx(limpo_em(dest))[1].statements[0].transactions,[])
    def test_manifesto_corrompido_e_orfao_bloqueiam(self):
        op=self.bank/'.comparaofx'/'orfao'; op.mkdir(parents=True); (op/'manifesto.json').write_text('{')
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual((op/'manifesto.json').read_text(),'{'); self.assertEqual(self.geral.read_bytes(),self.old)
    def test_temporario_orfao_sem_manifesto_bloqueia(self):
        op=self.bank/'.comparaofx'/'orfao'; op.mkdir(parents=True); (op/'geral.tmp').write_bytes(b'parcial')
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(self.bank)
        self.assertEqual((op/'geral.tmp').read_bytes(),b'parcial'); self.assertEqual(self.geral.read_bytes(),self.old)
    def test_pendencia_identificada_sem_ofx_na_raiz(self):
        from comparaArqOFX import main
        op=self.bank/'.comparaofx'/'orfao'; op.mkdir(parents=True)
        self.src.unlink(); messages=[]
        self.assertEqual(main(self.root,lambda _:self.fail('não solicitar entrada'),messages.append),1)
        self.assertTrue(any('pendente' in msg for msg in messages)); self.assertTrue(op.exists())
    def test_sem_novidades_interrompido_e_recuperado(self):
        self.src.write_bytes(self.old); plan=self.plan(); before=self.geral.read_bytes()
        with patch.object(ss,'finalizar',side_effect=OSError('interrompido')):
            with self.assertRaises(OSError): executar(plan)
        with ss.bloquear(self.bank):
            ss.recuperar_concluida(self.bank); ss.recuperar_concluida(self.bank)
        self.assertEqual(self.geral.read_bytes(),before)
        self.assertEqual((plan.importacao/self.src.name).read_bytes(),self.old)
        self.assertEqual(carregar_ofx(limpo_em(plan.importacao))[1].statements[0].transactions,[])
    def test_bloqueio_independente_e_liberacao(self):
        other=self.root/'Outro'; other.mkdir()
        with ss.bloquear(self.bank):
            with self.assertRaises(OrganizacaoError):
                with ss.bloquear(self.bank): pass
            with ss.bloquear(other): pass
        with ss.bloquear(self.bank): pass
    def test_token_nao_adquirido_nao_autoriza_execucao(self):
        plan=self.plan(); falso=ss.Bloqueio(self.bank)
        with self.assertRaises(OrganizacaoError): executar(plan,bloqueio=falso)
        self.assertEqual(self.geral.read_bytes(),self.old); self.assertEqual(self.src.read_bytes(),self.raw)
    def test_interrupcoes_reais_e_recuperacao(self):
        script=r'''import os,sys
from pathlib import Path
from datetime import date
from controller.workflow import planejar, executar
from controller import safe_storage as ss
root=Path(sys.argv[1]); bank=root/'Banco'; target=sys.argv[2]
p=planejar(root,bank,root/'atual.ofx',[root/'anexo.pdf'],hoje=date(2026,11,12))
if target=='preparado':
 ss.publicar_pasta=lambda *args: os._exit(70)
elif target=='pasta':
 old=ss.publicar_pasta
 def stop(*args): old(*args); os._exit(71)
 ss.publicar_pasta=stop
elif target=='geral':
 old=ss.publicar_arquivo
 def stop(*args): old(*args); os._exit(72)
 ss.publicar_arquivo=stop
elif target=='fim':
 ss.finalizar=lambda *args: os._exit(73)
elif target=='parcial':
 old=Path.unlink
 def stop(path,*args,**kwargs):
  is_source=path.exists() and path.samefile(root/'atual.ofx')
  result=old(path,*args,**kwargs)
  if is_source: os._exit(74)
  return result
 Path.unlink=stop
executar(p)
'''
        # Cada subteste recebe um ambiente próprio; não reutiliza arquivos financeiros.
        for target in ('preparado','pasta','geral','fim','parcial'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); bank=root/'Banco'; bank.mkdir(); (root/'atual.ofx').write_bytes(self.raw); (root/'anexo.pdf').write_bytes(b'PDF sintetico')
                day=pasta_dia(bank,D); day.mkdir(parents=True); general=day/f'OFXGeral-{D.isoformat()}.ofx'; general.write_bytes(self.old)
                proc=subprocess.run([sys.executable,'-c',script,str(root),target],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')},capture_output=True)
                self.assertEqual(proc.returncode,{'preparado':70,'pasta':71,'geral':72,'fim':73,'parcial':74}[target],proc.stderr.decode(errors='backslashreplace'))
                if target=='preparado':
                    self.assertFalse((day/'001').exists())
                else:
                    self.assertEqual((day/'001'/'atual.ofx').read_bytes(),self.raw)
                    self.assertEqual((day/'001'/'anexo.pdf').read_bytes(),b'PDF sintetico')
                with ss.bloquear(bank):
                    if target in ('fim','geral','parcial'):
                        ss.recuperar_concluida(bank); ss.recuperar_concluida(bank)
                        self.assertEqual(ss.pendencias(bank),[])
                        self.assertFalse((root/'atual.ofx').exists())
                    elif target=='preparado':
                        ss.recuperar_concluida(bank)
                        self.assertEqual(ss.pendencias(bank),[])
                        self.assertEqual((root/'atual.ofx').read_bytes(),self.raw)
                    else:
                        with self.assertRaises(OrganizacaoError): ss.recuperar_concluida(bank)
                        self.assertEqual((root/'atual.ofx').read_bytes(),self.raw)
                self.assertEqual([t.fitid for t in carregar_ofx(general)[1].statements[0].transactions],['A'] if target in ('preparado','pasta') else ['A','B'])
    def test_bloqueio_liberado_por_kill(self):
        code="import sys; from controller.safe_storage import bloquear; from pathlib import Path; c=bloquear(Path(sys.argv[1])); c.__enter__(); print('locked',flush=True); sys.stdin.read()"
        p=subprocess.Popen([sys.executable,'-c',code,str(self.bank)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
        try:
            self.assertEqual(p.stdout.readline().strip(),'locked')
            with self.assertRaises(OrganizacaoError):
                with ss.bloquear(self.bank): pass
            p.kill(); p.wait(timeout=10)
            with ss.bloquear(self.bank): pass
        finally:
            if p.poll() is None: p.kill(); p.wait()
            p.stdin.close(); p.stdout.close(); p.stderr.close()
if __name__=='__main__': unittest.main()
