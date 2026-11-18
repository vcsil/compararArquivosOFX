"""A janela OFX usa somente referências relevantes e preserva o legado."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_baseline import fixture, limpo_em
from test_organization import ids, tx
from controller import safe_storage
from controller.ofx_functions import carregar_ofx
from controller.organization import OrganizacaoError, localizar_historico, pasta_dia
from controller.workflow import executar, planejar


HOJE = date(2026, 11, 18)


class JanelaHistorica(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(TemporaryDirectory())
        self.raiz = Path(temp).resolve()
        self.banco = self.raiz / 'Banco Sintético'
        self.banco.mkdir()
        self.original = self.raiz / 'Entrada.ofx'
        self.original.write_bytes(fixture([tx(13, 'A'), tx(17, 'B'), tx(18, 'C')]))

    def geral(self, dia, transacoes, **kwargs):
        pasta = pasta_dia(self.banco, dia)
        pasta.mkdir(parents=True, exist_ok=True)
        geral = pasta / f'OFXGeral-{dia}.ofx'
        geral.write_bytes(fixture(transacoes, **kwargs))
        return geral

    def orfao(self, dia):
        pasta = pasta_dia(self.banco, dia) / '01'
        pasta.mkdir(parents=True)
        arquivo = pasta / 'antigo.ofx'
        arquivo.write_bytes(b'original legado sintetico')
        return arquivo

    def plano(self, **kwargs):
        return planejar(self.raiz, self.banco, self.original, hoje=HOJE, **kwargs)

    def test_centenas_de_dias_quatro_orfaos_e_so_uma_referencia_lida(self):
        orfaos = {date(2025, 1, 30), date(2026, 8, 5), date(2026, 8, 31), date(2026, 11, 6)}
        antigos = {}
        dia = date(2025, 1, 1)
        while dia < date(2026, 11, 17):
            arquivo = self.orfao(dia) if dia in orfaos else self.geral(dia, [tx(13, 'A')])
            antigos[arquivo] = arquivo.read_bytes()
            dia += timedelta(days=1)
        ultimo = self.geral(dia, [tx(17, 'B')])
        antes = ultimo.read_bytes()
        pasta_dia(self.banco, HOJE).mkdir()
        with patch.object(Path, 'iterdir', autospec=True, side_effect=Path.iterdir) as listar:
            with patch('test_history_window.carregar_ofx', wraps=carregar_ofx) as leitor:
                plano = self.plano(leitor=leitor)
                self.assertEqual([args[0] for args, _ in leitor.call_args_list], [self.original, ultimo])
            self.assertFalse(set(p.parent for p in antigos) & {args[0] for args, _ in listar.call_args_list})
        self.assertEqual(plano.historico, ultimo)
        destino = executar(plano)
        self.assertEqual(ids(limpo_em(destino)), ['C'])
        self.assertEqual(ids(plano.geral), ['C'])
        self.assertEqual(ultimo.read_bytes(), antes)
        self.assertEqual({arquivo: arquivo.read_bytes() for arquivo in antigos}, antigos)

    def test_hoje_tem_prioridade_sobre_orfao_ontem(self):
        referencia = self.geral(HOJE, [tx(17, 'B')])
        self.orfao(date(2026, 11, 17))
        self.assertEqual(self.plano().historico, referencia)

    def test_lacuna_sem_importacao_usa_ultima_data_disponivel(self):
        anterior = self.geral(date(2026, 11, 13), [tx(13, 'A')])
        self.assertEqual(self.plano().historico, anterior)

    def test_importacao_incompleta_na_janela_bloqueia_com_data(self):
        self.geral(date(2026, 11, 13), [tx(13, 'A')])
        for dia in (date(2026, 11, 17), HOJE):
            with self.subTest(dia=dia):
                arquivo = self.orfao(dia)
                with self.assertRaisesRegex(OrganizacaoError, rf'{dia}.*Geral ausente'):
                    self.plano()
                self.assertTrue(self.original.exists())
                arquivo.unlink()
                arquivo.parent.rmdir()

    def test_sem_geral_so_pasta_vazia_e_primeira_importacao(self):
        self.assertEqual(self.plano().resultado.relatorio.estado, 'PRIMEIRA_IMPORTACAO')
        dia = date(2025, 1, 30)
        self.orfao(dia)
        with self.assertRaisesRegex(OrganizacaoError, rf'{dia}.*Geral ausente'):
            self.plano()

    def test_pasta_diaria_desconhecida_dentro_e_fora_da_janela(self):
        anterior = self.geral(date(2026, 11, 13), [tx(13, 'A')])
        (self.banco / '2026-08-05').mkdir()
        self.assertEqual(self.plano().historico, anterior)
        (self.banco / '2026-11-17').mkdir()
        with self.assertRaisesRegex(OrganizacaoError, r'2026-11-17.*hierarquia'):
            self.plano()

    def test_gerais_da_mesma_data_em_duas_hierarquias_bloqueiam(self):
        dia = date(2026, 11, 17)
        geral = self.geral(dia, [tx(17, 'B')])
        alternativo = self.banco / '11 - Nov 2026' / str(dia)
        alternativo.mkdir(parents=True)
        (alternativo / geral.name).write_bytes(geral.read_bytes())
        with self.assertRaisesRegex(OrganizacaoError, r'2026-11-17.*mais de um Geral'):
            self.plano()

    def test_referencia_com_conflito_ou_conta_distinta_nao_cai_para_mais_antiga(self):
        anterior = date(2026, 11, 17)
        self.geral(date(2026, 11, 13), [tx(13, 'A')])
        for transacoes, conta in (([tx(17, 'B', '999')], '123'), ([tx(17, 'B')], '999')):
            with self.subTest(transacoes=transacoes, conta=conta):
                self.geral(anterior, transacoes, account=conta)
                with self.assertRaises(OrganizacaoError):
                    self.plano()
                self.assertTrue(self.original.exists())

    def test_orfao_surpreende_apos_preparacao_sem_publicar(self):
        self.geral(date(2026, 11, 13), [tx(13, 'A')])
        plano = self.plano()
        atualizar = safe_storage.atualizar_manifesto
        intermediario = date(2026, 11, 17)

        def incluir_orfao(op, manifesto):
            atualizar(op, manifesto)
            if manifesto['estado'] == 'PREPARADO':
                self.orfao(intermediario)

        with patch.object(safe_storage, 'atualizar_manifesto', side_effect=incluir_orfao):
            with self.assertRaisesRegex(OrganizacaoError, rf'{intermediario}.*Geral ausente'):
                executar(plano)
        self.assertTrue(self.original.exists())
        self.assertFalse(plano.importacao.exists())
        safe_storage.recuperar_concluida(self.banco)
        self.assertEqual(safe_storage.pendencias(self.banco), [])

    def test_csv_rede_e_valori_ainda_validam_snapshots_antigos(self):
        from test_rede_csv import csv as dados_rede, linha as rede
        from test_valori_csv import dados as dados_valori, linha as valori

        for nome, payload in (('Rede', dados_rede(rede('REDE-SYNTH'))), ('Valori', dados_valori(valori()))):
            with self.subTest(nome=nome):
                banco = self.raiz / nome
                banco.mkdir()
                arquivo = self.raiz / f'{nome}.csv'
                arquivo.write_bytes(payload)
                anterior = date(2026, 11, 17)
                executar(planejar(self.raiz, banco, arquivo, hoje=anterior))
                antigo = date(2025, 1, 30)
                (pasta_dia(banco, antigo) / '01').mkdir(parents=True)
                arquivo.write_bytes(payload)
                with self.assertRaisesRegex(OrganizacaoError, 'Geral ausente'):
                    planejar(self.raiz, banco, arquivo, hoje=HOJE)
                self.assertEqual(arquivo.read_bytes(), payload)

    def test_numeros_legados_com_mesma_identidade_bloqueiam(self):
        self.geral(HOJE, [tx(17, 'B')])
        (pasta_dia(self.banco, HOJE) / '01').mkdir()
        (pasta_dia(self.banco, HOJE) / '001').mkdir()
        with self.assertRaisesRegex(OrganizacaoError, r'numeração.*ambígua'):
            localizar_historico(self.banco, HOJE)
