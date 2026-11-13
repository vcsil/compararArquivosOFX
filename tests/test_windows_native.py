"""Contratos de sistema de arquivos; teste de compartilhamento exige Windows real."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller import safe_storage as ss

class ContratosArquivos(unittest.TestCase):
    def test_publicacao_de_pasta_nao_substitui_destino(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); source=root/'source'; target=root/'target'; source.mkdir(); target.mkdir()
            (source/'new').write_text('novo'); (target/'keep').write_text('original')
            with self.assertRaises(OSError): ss.publicar_pasta(source,target)
            self.assertEqual((target/'keep').read_text(),'original')
            self.assertEqual((source/'new').read_text(),'novo')
    def test_geral_exclusivo_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); source=root/'temp'; target=root/'oficial'
            source.write_bytes(b'novo'); target.write_bytes(b'original')
            with self.assertRaises(OSError): ss.publicar_arquivo(source,target,False)
            self.assertEqual(target.read_bytes(),b'original'); self.assertEqual(source.read_bytes(),b'novo')
    def test_criacao_exclusiva_e_substituicao(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); target=root/'oficial'; source=root/'temp'
            source.write_bytes(b'primeiro'); ss.publicar_arquivo(source,target,False)
            self.assertEqual(target.read_bytes(),b'primeiro')
            source.write_bytes(b'segundo'); ss.publicar_arquivo(source,target,True)
            self.assertEqual(target.read_bytes(),b'segundo')
    @unittest.skipUnless(os.name=='nt','bloqueio de compartilhamento do Windows requer Windows nativo')
    def test_windows_arquivo_sem_compartilhamento_nao_e_substituido(self):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]; kernel.CloseHandle.restype=wintypes.BOOL
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); source=root/'temp'; target=root/'oficial'; source.write_bytes(b'novo'); target.write_bytes(b'original')
            handle=kernel.CreateFileW(str(target),0x80000000,0,None,3,0x80,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            try:
                with self.assertRaises(OSError): ss.publicar_arquivo(source,target,True)
            finally: kernel.CloseHandle(handle)
            self.assertEqual(target.read_bytes(),b'original'); self.assertEqual(source.read_bytes(),b'novo')
