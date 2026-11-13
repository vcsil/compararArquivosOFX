"""O pacote manual usa somente cenários novos e é recuperável pelo terminal."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from test_baseline import fixture, limpo_em
from comparaArqOFX import main
from controller import safe_storage
from controller.ofx_functions import carregar_ofx


class PacoteManual(unittest.TestCase):
    def test_seis_cenarios_e_recusa_destino_existente(self):
        path=Path(__file__).resolve().parents[1]/'scripts'/'prepare_recovery_smoke.py'
        spec=importlib.util.spec_from_file_location('prepare_recovery_smoke',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'cenarios'; cases=module.preparar(output)
            self.assertEqual(len(cases),6)
            before=(cases[0]/'LEIA-ME.txt').read_bytes()
            with self.assertRaises(FileExistsError): module.preparar(output)
            self.assertEqual((cases[0]/'LEIA-ME.txt').read_bytes(),before)
            for root in cases:
                with self.subTest(case=root.name):
                    bank=root/'Banco Sintetico'
                    self.assertEqual(main(root,lambda _:'1',lambda _:None),0)
                    self.assertEqual(safe_storage.pendencias(bank),[])
                    original=next(bank.rglob('Entrada.ofx'))
                    self.assertEqual(original.read_bytes(),fixture([('20261110120000','20','SYNTH-1','Sintetico')]))
                    clean=limpo_em(original.parent)
                    if root.name.startswith('v1-') and not root.name.endswith('preparado'):
                        self.assertEqual(clean.name,'OFX Limpo.ofx')
                    else:
                        self.assertRegex(clean.name,r'^OFX Limpo-[0-9]{12}\.ofx$')
                    self.assertEqual(carregar_ofx(clean)[1].statements[0].transactions[0].fitid,'SYNTH-1')
