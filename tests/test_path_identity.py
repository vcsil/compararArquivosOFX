"""Identidade de caminhos sem dados financeiros reais."""
import os
import sys
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from test_baseline import fixture
from controller.organization import OrganizacaoError, raiz_aplicacao
from controller.workflow import planejar, executar
from controller.safe_storage import bloquear, recuperar_concluida


class Caminhos(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Caminhos com acentos ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bank=self.root/'Banco São João'; self.bank.mkdir()
        self.source=self.root/'Extrato com acento.ofx'
        self.source.write_bytes(fixture([('20261110120000','10','A','Sintetico')]))
        self.day=date(2026,11,12)
    def test_caminhos_relativos_e_diretorio_de_trabalho(self):
        cwd=Path.cwd()
        try:
            os.chdir(self.root.parent)
            root=Path(self.root.name); bank=root/self.bank.name; source=root/self.source.name
            plan=planejar(root,bank,source,hoje=self.day)
            self.assertTrue(plan.banco.samefile(self.bank)); self.assertTrue(plan.original.samefile(self.source))
        finally: os.chdir(cwd)
    def test_link_de_arquivo_rejeitado(self):
        alias=self.root/'alias.ofx'
        try: alias.symlink_to(self.source)
        except OSError: self.skipTest('Sistema não permite criar link simbólico para este usuário')
        with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,alias,hoje=self.day)
    def test_link_de_banco_rejeitado(self):
        alias=self.root/'Banco Link'
        try: alias.symlink_to(self.bank,target_is_directory=True)
        except OSError: self.skipTest('Sistema não permite criar link simbólico para este usuário')
        with self.assertRaises(OrganizacaoError): planejar(self.root,alias,self.source,hoje=self.day)
        with self.assertRaises(OrganizacaoError):
            with bloquear(alias): pass
    def test_pai_link_para_raiz_rejeitado(self):
        alias=self.root.parent/(self.root.name+'-link')
        try: alias.symlink_to(self.root,target_is_directory=True)
        except OSError: self.skipTest('Sistema não permite criar link simbólico para este usuário')
        self.addCleanup(lambda: alias.unlink(missing_ok=True))
        with self.assertRaises(OrganizacaoError):
            planejar(self.root,alias/self.bank.name,self.source,hoje=self.day)
    def test_banco_e_arquivo_externos_rejeitados(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside=Path(tmp); bank=outside/'Banco'; bank.mkdir(); file=outside/'x.ofx'; file.write_bytes(b'x')
            with self.assertRaises(OrganizacaoError): planejar(self.root,bank,self.source,hoje=self.day)
            with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,file,hoje=self.day)
    def test_hardlink_indevido_rejeitado(self):
        alias=self.root/'outro.ofx'
        try: os.link(self.source,alias)
        except OSError: self.skipTest('Sistema de arquivos não permite hardlink')
        with self.assertRaises(OrganizacaoError): planejar(self.root,self.bank,self.source,hoje=self.day)
    def test_raiz_executavel_independe_cwd(self):
        exe=self.root/'Programa com acento.exe'; exe.write_bytes(b'sintetico')
        cwd=Path.cwd()
        try:
            os.chdir(self.root.parent)
            with patch('sys.frozen',True,create=True), patch('sys.executable',str(exe)):
                self.assertTrue(raiz_aplicacao().samefile(self.root))
        finally: os.chdir(cwd)
    def test_raiz_nuitka_independe_extracao_e_cwd(self):
        from types import SimpleNamespace
        from controller import organization
        extracted = self.root / 'extracao'; extracted.mkdir()
        cwd = Path.cwd()
        try:
            os.chdir(self.root.parent)
            for mode in ('standalone', 'onefile'):
                with self.subTest(mode=mode):
                    binary_root = self.root / (mode + '.dist' if mode == 'standalone' else mode)
                    binary_root.mkdir()
                    exe = binary_root / 'Programa com acento.exe'; exe.write_bytes(b'sintetico')
                    metadata = SimpleNamespace(containing_dir=str(binary_root.parent if mode == 'standalone' else binary_root))
                    with patch.dict(organization.__dict__, {'__compiled__': metadata}), \
                         patch.object(sys, 'argv', [str(exe)]), \
                         patch.object(sys, 'executable', str(extracted / 'interno.exe')), \
                         patch.object(organization, '__file__', str(extracted / 'controller' / 'organization.py')):
                        self.assertTrue(raiz_aplicacao().samefile(binary_root))
                        self.assertTrue(raiz_aplicacao(extracted).samefile(extracted))
        finally:
            os.chdir(cwd)

    @unittest.skipUnless(os.name=='nt','nomes curtos 8.3 e capitalização exigem Windows nativo')
    def test_windows_nome_curto_e_longo_mesma_identidade(self):
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        func=kernel.GetShortPathNameW
        func.argtypes=(ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32); func.restype=ctypes.c_uint32
        def short(path):
            buf=ctypes.create_unicode_buffer(32768); result=func(str(path),buf,len(buf))
            if not result or result>=len(buf): raise ctypes.WinError(ctypes.get_last_error())
            return Path(buf.value)
        bank=short(self.bank); source=short(self.source); root=short(self.root)
        if str(root).casefold()==str(self.root.resolve()).casefold() and str(bank).casefold()==str(self.bank.resolve()).casefold():
            self.skipTest('Geração de nomes curtos 8.3 indisponível neste volume')
        plan=planejar(self.root,bank,source,hoje=self.day)
        self.assertTrue(plan.banco.samefile(self.bank)); self.assertTrue(plan.original.samefile(self.source))
        with bloquear(bank) as token:
            with self.assertRaises(OrganizacaoError):
                with bloquear(self.bank): pass
            recuperar_concluida(self.bank,bloqueio=token)
            output=executar(plan,bloqueio=token)
        self.assertTrue((output/self.source.name).is_file())
    @unittest.skipUnless(os.name=='nt','sistema de arquivos sensível a maiúsculas exige Windows')
    def test_windows_capitalizacao_equivalente(self):
        bank=Path(str(self.bank).swapcase()); source=Path(str(self.source).swapcase())
        plan=planejar(self.root,bank,source,hoje=self.day)
        self.assertTrue(plan.banco.samefile(self.bank)); self.assertTrue(plan.original.samefile(self.source))
    @unittest.skipUnless(os.name=='nt','junctions requerem Windows nativo')
    def test_windows_junction_rejeitada(self):
        junction=self.root/'Banco Junction'
        proc=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(self.bank)],capture_output=True)
        if proc.returncode:
            self.skipTest('Sistema de arquivos ou política não permite criar junction')
        self.addCleanup(lambda: junction.rmdir())
        with self.assertRaises(OrganizacaoError): planejar(self.root,junction,self.source,hoje=self.day)
        with self.assertRaises(OrganizacaoError):
            with bloquear(junction): pass
