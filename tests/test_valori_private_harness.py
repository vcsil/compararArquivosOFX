"""Exercita o harness privado somente com ZIPs sintéticos descartáveis."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from test_valori_csv import dados, linha
from test_baseline import fixture

scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location(
    "audit_valori_zip", scripts / "audit_valori_zip.py"
)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class ValoriHarness(unittest.TestCase):
    def test_conversao_valida_e_publicacao_tem_resultados_distintos(self):
        for cc in (False, True):
            with self.subTest(cc=cc), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "sintetico.zip"
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("Valori/entrada.csv", dados(linha()))
                    z.writestr("Valori/anexo.xlsx", b"SINTETICO")
                    if cc:
                        raw = fixture(
                            [("20261112120000", "10", "OLD", "Sintetico")]
                        ).replace(b"CHECKING", b"CC")
                        z.writestr(
                            "Valori/2026/11 - Nov 2026/2026-11-13/OFXGeral-2026-11-13.ofx",
                            raw,
                        )
                result = harness.auditar(path)
                self.assertEqual(result["conversao"], "APROVADA")
                self.assertEqual(result["registros_conferidos_individualmente"], 1)
                self.assertTrue(result["referencias_preservadas"])
                self.assertEqual(
                    result["publicacao"],
                    "HISTORICO_INCOMPATIVEL" if cc else "IMPORTACAO_APROVADA",
                )
                # A saída pública não deve conter IDs, dinheiro, loja ou caminhos.
                public = str(result)
                for private in ("Loja Sintética", "SYNTH-001", "970.25", str(path)):
                    self.assertNotIn(private, public)

    def test_zip_inseguro_rejeitado_antes_de_extrair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inseguro.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../escape.csv", dados(linha()))
            with self.assertRaises(ValueError):
                harness.auditar(path)
