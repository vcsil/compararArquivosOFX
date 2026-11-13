import contextlib
import io
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from colorama import Fore, Style
from controller import terminal_style as style
from controller.user_navigation import Cancelado, escolher, selecionar


class TerminalStyleTests(unittest.TestCase):
    def test_paleta_semantica(self):
        for tipo, cor in [('titulo', Fore.BLUE), ('erro', Fore.RED),
                          ('aviso', Fore.YELLOW), ('sucesso', Fore.GREEN), ('opcao', Fore.YELLOW)]:
            with self.subTest(tipo=tipo):
                texto = style.formatar('mensagem', tipo, True)
                self.assertIn(cor, texto)
                self.assertTrue(texto.endswith(Style.RESET_ALL))
                self.assertEqual(style.formatar('mensagem', tipo, False), 'mensagem')

    def test_terminal_tty_e_inicializacao_unica(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdout', stream), \
             patch.object(style, '_inicializado', False), patch.object(style, 'just_fix_windows_console') as init:
            a = style.Terminal(print); a.texto('Título', 'titulo')
            style.Terminal(print).texto('Erro', 'erro')
            self.assertTrue(a.colorido)
            init.assert_called_once()
        self.assertIn(Fore.BLUE, stream.getvalue())
        self.assertIn(Fore.RED, stream.getvalue())

    def test_callback_nunca_herda_tty_e_no_color_vazio(self):
        stream = io.StringIO(); stream.isatty = lambda: True
        for env in ({}, {'NO_COLOR': ''}, {'NO_COLOR': '1'}, {'CI': 'true'}, {'TERM': 'dumb'}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), patch('sys.stdout', stream):
                mensagens = []
                style.Terminal(mensagens.append).texto('aviso', 'aviso')
                self.assertEqual(mensagens, ['aviso'])
                if env: self.assertFalse(style.Terminal(print).colorido)

    def test_arquivo_redirecionado_sem_ansi(self):
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as stream, contextlib.redirect_stdout(stream):
            tela = style.Terminal(print); tela.texto('teste', 'titulo'); stream.seek(0)
            self.assertNotIn('\x1b', stream.read())

    def test_relatorio_decimal_exato_e_bloqueado_sem_sucesso(self):
        total = SimpleNamespace(quantidade=2, creditos=Decimal('123.456789'),
                                debitos=Decimal('-0.000001'), liquido=Decimal('123.456788'))
        rel = SimpleNamespace(estado='BLOQUEADO', original=total, anteriores=total, duplicatas=total, novas=total)
        mensagens = []
        style.relatorio_financeiro(rel, style.Terminal(mensagens.append))
        texto = '\n'.join(mensagens)
        for valor in ('123.456789', '-0.000001', '123.456788', 'BLOQUEADO'):
            self.assertIn(valor, texto)
        self.assertNotIn('concluída', texto.lower())
        self.assertNotIn('\x1b', texto)

    def test_bloqueio_no_fluxo_nao_anuncia_conclusao(self):
        from comparaArqOFX import main
        from controller.organization import OrganizacaoError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'Banco').mkdir(); source=root/'entrada.ofx'; source.write_bytes(b'ofx')
            saidas = []
            with patch('controller.workflow.planejar', side_effect=OrganizacaoError('Conflito financeiro')):
                codigo = main(root, lambda _: '1', saidas.append)
            self.assertEqual(codigo, 1)
            self.assertTrue(source.exists())
            self.assertIn('Conflito financeiro', '\n'.join(saidas))
            self.assertFalse(any('Arquivos organizados em:' in msg for msg in saidas))
            self.assertFalse(any('\x1b' in msg for msg in saidas))

    def test_navegacao_indices_invalidos_cancelamento_e_anexos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'Banco A').mkdir(); (root/'Banco B').mkdir()
            (root/'a.ofx').write_bytes(b'ofx'); (root/'anexo.pdf').write_bytes(b'pdf')
            mensagens = []; respostas = iter(['inválido', '2'])
            banco, arquivo, anexos = selecionar(root, lambda _: next(respostas), mensagens.append)
            self.assertEqual((banco.name, arquivo.name, len(anexos)), ('Banco B', 'a.ofx', 1))
            self.assertIn('01 - Banco A', mensagens); self.assertIn('02 - Banco B', mensagens)
            self.assertIn('Entrada inválida.', mensagens)
            self.assertFalse(any('\x1b' in m for m in mensagens))
            with self.assertRaises(Cancelado):
                escolher([banco], 'Instituições', lambda _: '0', mensagens.append)

if __name__ == '__main__': unittest.main()
