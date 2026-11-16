import contextlib
import io
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

spec=importlib.util.spec_from_file_location('audit_build_contents',Path(__file__).resolve().parents[1]/'scripts'/'audit_build_contents.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class BuildAudit(unittest.TestCase):
    def test_detecta_testes_e_ferramentas_do_projeto(self):
        for item in ('test_baseline','tests.test_comparison','tests/test_output_names.py','smoke_exe','benchmark_exe_processing'):
            with self.subTest(item=item): self.assertTrue(audit.forbidden(item))
        for item in ('controller.ofx_functions','ofxtools.Parser','unittest','PIL','pefile'):
            with self.subTest(item=item): self.assertFalse(audit.forbidden(item))

    def test_relatorio_nuitka_exige_modulos_reais_e_bloqueia_testes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.xml'; out=Path(tmp)/'inventory.json'
            path.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/><module name="test_baseline"/></nuitka-compilation-report>')
            with patch.object(sys,'argv',['audit','nuitka',str(path),str(out)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): audit.main()
            self.assertIn('test_baseline',out.read_text())
            path.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/><data_file name="tests/test_baseline.py"/></nuitka-compilation-report>')
            with patch.object(sys,'argv',['audit','nuitka',str(path),str(out)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): audit.main()
            self.assertIn('tests/test_baseline.py',out.read_text())
            path.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/><data_file name="renamed.bin" source="${cwd}/tests/fixtures/sample.ofx"/></nuitka-compilation-report>')
            with patch.object(sys,'argv',['audit','nuitka',str(path),str(out)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): audit.main()
            self.assertIn('tests/fixtures/sample.ofx',out.read_text())
            path.write_text('<nuitka-compilation-report completion="error"/>')
            with self.assertRaises(ValueError): audit.inventory_nuitka(path)

    def test_distribuicao_fisica_e_zip_sao_inspecionados(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); dist=root/'dist'; dist.mkdir()
            report=root/'report.xml'; out=root/'inventory.json'
            report.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/></nuitka-compilation-report>')
            with zipfile.ZipFile(dist/'resources.zip','w') as archive:
                archive.writestr('tests/test_baseline.py','')
            with patch.object(sys,'argv',['audit','nuitka',str(report),str(out),'--distribution',str(dist)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): audit.main()
            self.assertIn('tests/test_baseline.py',out.read_text())

class ColoramaAudit(unittest.TestCase):
    def test_build_exige_colorama_quando_solicitado(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); report = root/'report.xml'; out = root/'inventory.json'
            report.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/></nuitka-compilation-report>')
            with patch.object(sys, 'argv', ['audit','nuitka',str(report),str(out),'--require-colorama']), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'Colorama'): audit.main()
            report.write_text('<nuitka-compilation-report completion="yes"><module name="controller.workflow"/><module name="ofxtools.Parser"/><module name="colorama"/></nuitka-compilation-report>')
            with patch.object(sys, 'argv', ['audit','nuitka',str(report),str(out),'--require-colorama']), contextlib.redirect_stdout(io.StringIO()):
                audit.main()

class ValoriAudit(unittest.TestCase):
    def test_build_exige_despachante_e_conversor_valori(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); report=root/'report.xml'; out=root/'inventory.json'
            for modules in (['controller.workflow','ofxtools.Parser'],
                            ['controller.workflow','ofxtools.Parser','controller.valori_csv'],
                            ['controller.workflow','ofxtools.Parser','controller.valori_csv','controller.csv_formats']):
                report.write_text('<nuitka-compilation-report completion="yes">'+''.join(f'<module name="{m}"/>' for m in modules)+'</nuitka-compilation-report>')
                with patch.object(sys,'argv',['audit','nuitka',str(report),str(out),'--require-valori']), contextlib.redirect_stdout(io.StringIO()):
                    if 'controller.csv_formats' not in modules:
                        with self.assertRaisesRegex(ValueError,'Valori'): audit.main()
                    else: audit.main()
