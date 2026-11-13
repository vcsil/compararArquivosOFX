"""O terminal moderno não pode chamar o fluxo legado inseguro da baseline."""
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_baseline import fixture
from comparaArqOFX import main
from controller import ofx_functions, browse_folders


class AuditoriaLegada(unittest.TestCase):
    def test_terminal_nao_chama_comparacao_navegacao_ou_gravacao_legadas(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            root=Path(tmp); bank=root/'Banco'; bank.mkdir()
            source=root/'Entrada.ofx'
            for module, names in ((ofx_functions, ('pegar_dia_insterseccao','pegar_infos_transacoes',
                    'remove_transacao','remove_anteriores','salvar_ofx','salvar_ofx_geral','junta_transacoes')),
                    (browse_folders, ('get_name_ofx','get_old_directory'))):
                for name in names:
                    stack.enter_context(patch.object(module,name,side_effect=AssertionError('Fluxo legado: '+name)))
            rows=[('20261110120000','20','A','Mesmo memo'),('20261110120000','20','B','Mesmo memo')]
            for count in (2,3):
                if count==3: rows.append(('20261110120000','20','C','Mesmo memo'))
                raw=fixture(rows); source.write_bytes(raw)
                self.assertEqual(main(root,lambda _:'1',lambda _:None),0)
                self.assertFalse(source.exists())
                general=next(bank.rglob('OFXGeral-*.ofx'))
                items=ofx_functions.carregar_ofx(general)[1].statements[0].transactions
                self.assertEqual(len(items),count)
                self.assertEqual(sum(t.trnamt for t in items),20*count)
            before=general.read_bytes()
            bad=fixture(rows,account='999'); source.write_bytes(bad)
            self.assertEqual(main(root,lambda _:'1',lambda _:None),1)
            self.assertEqual(source.read_bytes(),bad); self.assertEqual(general.read_bytes(),before)
