"""Regressões sintéticas para volumes virtuais; não simula homologação do Drive."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller import storage_capabilities as caps, safe_storage as ss
from controller.organization import OrganizacaoError, link_inseguro


class Capacidades(unittest.TestCase):
    def test_primitivas_reais(self):
        with tempfile.TemporaryDirectory() as tmp:
            caps.verificar_capacidades(Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_falha_especifica_nao_libera_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ss, 'publicar_arquivo', side_effect=OSError('sem rename')):
                with self.assertRaisesRegex(OrganizacaoError, 'renomeação exclusiva'):
                    caps.verificar_capacidades(Path(tmp))

    def test_zero_links_nao_equivale_a_hardlink(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_nlink=0)), \
             patch.object(caps.sys, 'platform', 'win32'), \
             patch.object(caps, 'volume_windows', return_value=0):
            self.assertTrue(caps.links_seguros(Path('virtual')))

    def test_metadados_ausentes_com_hardlinks_bloqueiam(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_nlink=0)), \
             patch.object(caps.sys, 'platform', 'win32'), \
             patch.object(caps, 'volume_windows', return_value=0x00400000):
            with self.assertRaisesRegex(OrganizacaoError, 'contagem de links'):
                caps.links_seguros(Path('virtual'))

    def test_hardlink_real_continua_recusado(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_nlink=2)):
            self.assertFalse(caps.links_seguros(Path('arquivo')))

    def test_tags_cloud_e_redirecionamentos(self):
        for tag, unsafe in ((0x9000001A, False), (0x9000F01A, False),
                            (0xA0000003, True), (0xA000000C, True), (0x80000099, True)):
            with self.subTest(tag=hex(tag)), \
                 patch.object(Path, 'lstat', return_value=SimpleNamespace(st_file_attributes=0x400, st_reparse_tag=tag)), \
                 patch.object(Path, 'is_symlink', return_value=False):
                self.assertEqual(link_inseguro(Path('placeholder')), unsafe)

    def test_duas_instancias_e_morte_do_dono(self):
        with tempfile.TemporaryDirectory() as tmp:
            banco = Path(tmp) / 'Banco'; banco.mkdir()
            env = os.environ.copy()
            env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
            code = '''import sys
from pathlib import Path
from controller.safe_storage import bloquear
with bloquear(Path(sys.argv[1])):
 print('READY', flush=True)
 sys.stdin.read()
'''
            child = subprocess.Popen([sys.executable, '-c', code, str(banco)], env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # communicate timeout no processo auxiliar impede diagnóstico travado.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(child.stdout.readline)
                    try:
                        self.assertEqual(future.result(timeout=30).strip(), 'READY')
                    except BaseException:
                        child.kill()
                        raise
                with self.assertRaisesRegex(OrganizacaoError, 'já está em processamento'):
                    with ss.bloquear(banco):
                        self.fail('segunda instância adquiriu bloqueio')
                child.kill(); child.communicate(timeout=15)
                with ss.bloquear(banco) as token:
                    self.assertTrue(ss.bloqueio_valido(token, banco))
                    with self.assertRaises(OrganizacaoError):
                        with ss.bloquear(banco):
                            pass
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=15)

    def test_zero_links_no_fluxo_e_recuperacao(self):
        from test_baseline import fixture
        from controller.workflow import planejar, executar
        from controller.ofx_functions import carregar_ofx
        real_stat = Path.stat
        def zero(path, *args, **kwargs):
            values = list(real_stat(path, *args, **kwargs)); values[3] = 0
            return os.stat_result(values)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bank = root / 'Banco'; bank.mkdir()
            source = root / 'entrada.ofx'
            raw = fixture([('20261110120000', '10', 'A', 'Sintetico')])
            source.write_bytes(raw)
            with patch.object(Path, 'stat', zero), \
                 patch.object(caps, 'sys', SimpleNamespace(platform='win32')), \
                 patch.object(caps, 'volume_windows', return_value=0):
                for attempt in range(2):
                    source.write_bytes(raw)
                    plan = planejar(root, bank, source)
                    if attempt == 0:
                        finish = ss.finalizar
                        with patch.object(ss, 'finalizar', side_effect=OSError('interrupcao')):
                            with self.assertRaises(OSError):
                                executar(plan)
                        self.assertTrue(ss.pendencias(bank))
                        ss.recuperar_concluida(bank)
                        self.assertFalse(ss.pendencias(bank))
                    else:
                        executar(plan)
                    self.assertEqual(len(carregar_ofx(plan.geral)[1].statements[0].transactions), 1)
                    self.assertFalse(source.exists())

    @unittest.skipUnless(os.name == 'nt', 'rename exclusivo requer Windows real')
    def test_windows_publica_sem_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(os, 'link', side_effect=AssertionError('hardlink usado')):
            caps.verificar_capacidades(Path(tmp))
