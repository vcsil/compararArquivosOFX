"""Recebimentos inteiramente fictícios; nenhum dado do ZIP privado."""

import csv
import io
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from controller import safe_storage
from controller.csv_formats import VALORI_CAMPOS, identificar_csv
from controller.ofx_functions import carregar_ofx
from controller.ofx_io import serializar_ofx, interpretar_ofx
from controller.ofx_names import eh_nome_limpo
from controller.organization import (
    OrganizacaoError,
    anexos,
    csvs_extrato,
    extrato_permitido,
)
from controller.user_navigation import selecionar
from controller.valori_csv import (
    carregar_csv_valori,
    analisar_lotes,
    consolidar_historicos,
)
from controller.workflow import planejar, executar
from test_rede_csv import csv as rede_csv, linha as rede_linha
from test_baseline import fixture


def linha(nsu="SYNTH-001", **changes):
    row = dict(
        zip(
            VALORI_CAMPOS,
            (
                "AUTH-SYNTH",
                "Loja Sintética A",
                "POS-TESTE",
                "10/11/2026 14:01:02",
                "12/11/2026",
                "Visa",
                "ADQ-TESTE",
                "Crédito à Vista",
                "1",
                "1.000,00",
                "1.000,00",
                "970,25",
                "2,5",
                "0,00",
                "0,00",
                "Pago",
                nsu,
                "",
                "",
                "",
                "",
            ),
        )
    )
    row.update(changes)
    return row


def dados(*rows, encoding="utf-8-sig", sep=";"):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=VALORI_CAMPOS, delimiter=sep)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode(encoding)


class ValoriCSV(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bank = self.root / "Valori"
        self.bank.mkdir()
        self.day = date(2026, 11, 14)

    def criar(self, *rows, name="recebimentos.csv", **kwargs):
        path = self.root / name
        path.write_bytes(dados(*rows, **kwargs))
        return path

    def modelo(self, *rows):
        return carregar_csv_valori(self.criar(*rows))[1]

    def test_modalidades_sao_creditos_liquidos_na_data_de_pagamento(self):
        model = self.modelo(
            linha("C"),
            linha("D", **{"Tipo compra": "Débito"}),
            linha(
                "P",
                **{
                    "Tipo compra": "PIX",
                    "Bandeira": "PIX",
                    "Autorização": "",
                    "Id do Pix": "E-SYNTH-001",
                }
            ),
        )
        txs = model.statements[0].transactions
        self.assertEqual([t.fitid for t in txs], ["C", "D", "PIX:E-SYNTH-001"])
        for t in txs:
            self.assertEqual(
                (t.trntype, t.trnamt, t.dtposted.date()),
                ("CREDIT", Decimal("970.25"), date(2026, 11, 12)),
            )
            self.assertIn("2026-11-10T14:01:02", t.memo)
            self.assertLessEqual(len(t.memo), 255)
        self.assertEqual(model.statements[0].ledgerbal.balamt, Decimal("2910.75"))

    def test_cp1252_utf8_separadores_e_opcionais_vazios(self):
        row = linha(**{"Autorização": "", "POS": "", "Cod. acquirer": ""})
        for encoding in ("cp1252", "utf-8-sig"):
            for sep in (";", ",", "\t"):
                with self.subTest(encoding=encoding, sep=sep):
                    p = self.criar(row, encoding=encoding, sep=sep)
                    self.assertEqual(identificar_csv(p), "valori")
                    self.assertEqual(
                        carregar_csv_valori(p)[1].statements[0].transactions[0].trnamt,
                        Decimal("970.25"),
                    )

    def test_fitid_e_bytes_estaveis_apos_reordenar_linhas(self):
        rows = [linha("A"), linha("B")]
        a = serializar_ofx(self.modelo(*rows))
        b = serializar_ofx(self.modelo(*reversed(rows)))
        self.assertEqual(a, b)

    def test_status_nao_pago_bloqueia_arquivo_inteiro(self):
        for status in (
            "Cancelado",
            "Estornado",
            "Revertido",
            "",
            "Ignorado",
        ):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.modelo(linha("A"), linha("B", Status=status))

    def test_pendentes_e_parcelas_distintas_no_mesmo_csv(self):
        a = linha("PENDING-A", Status="Pendente")
        b = linha("PENDING-B", Status="Pendente")
        comum = dict(
            **{
                "Tipo compra": "Parcelamento sem Juros",
                "Parcelas": "2",
                "Valor total bruto": "210,00",
                "Valor parcela bruto": "105,00",
            }
        )
        p1 = linha("PARCELADO", **{**comum, "Valor líquido": "100,40"})
        p2 = linha("PARCELADO", **{**comum, "Valor líquido": "98,71"})
        model = self.modelo(a, p1, b, p2)
        txs = model.statements[0].transactions
        self.assertEqual(len(txs), 4)
        self.assertEqual(len({t.fitid for t in txs}), 4)
        parcelas = [t for t in txs if ":PARC:" in t.fitid]
        self.assertEqual({t.trnamt for t in parcelas}, {Decimal("100.40"), Decimal("98.71")})
        self.assertEqual(model.statements[0].ledgerbal.balamt, Decimal("199.11"))
        self.assertEqual(sum(t.name.startswith("Pendente - ") for t in txs), 2)
        from controller.valori_csv import _metas
        self.assertEqual(len(_metas(model)), 4)
        self.assertEqual(
            serializar_ofx(self.modelo(p2, b, p1, a)),
            serializar_ofx(model),
        )

    def test_pendente_que_vira_pago_substitui_sem_duplicar(self):
        pendente = linha("STATUS-1", Status="Pendente")
        pago = linha("STATUS-1", Status="Pago")
        first = self.modelo(pendente)
        second = self.modelo(pago)
        result = analisar_lotes(second, first)
        self.assertEqual(result.relatorio.estado, "APROVADO")
        self.assertEqual(result.relatorio.novas.quantidade, 0)
        self.assertEqual(result.indices_novos, (0,))
        from controller.valori_csv import consolidar_historicos
        merged = consolidar_historicos([first, second])
        self.assertEqual(len(merged.statements[0].transactions), 1)
        self.assertEqual(merged.statements[0].ledgerbal.balamt, Decimal("970.25"))
        self.assertEqual(
            analisar_lotes(first, second).relatorio.estado, "BLOQUEADO"
        )

    def test_fluxo_publica_entrada_com_pendentes_e_liquida_depois(self):
        src = self.criar(linha("STATUS-2", Status="Pendente"))
        first = planejar(self.root, self.bank, src, hoje=self.day)
        executar(first)
        self.assertEqual(
            carregar_ofx(first.geral)[1].statements[0].ledgerbal.balamt,
            Decimal("0"),
        )
        src = self.criar(linha("STATUS-2", Status="Pago"))
        second = planejar(self.root, self.bank, src, hoje=date(2026, 11, 15))
        executar(second)
        ledger = carregar_ofx(second.geral)[1]
        self.assertEqual(len(ledger.statements[0].transactions), 1)
        self.assertEqual(ledger.statements[0].ledgerbal.balamt, Decimal("970.25"))

    def test_recusa_duplicados_de_nsu_e_pix(self):
        for rows in (
            [linha("A"), linha("A")],
            [
                linha("A", **{"Tipo compra": "PIX", "Id do Pix": "E-X"}),
                linha("B", **{"Tipo compra": "PIX", "Id do Pix": "E-X"}),
            ],
        ):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                self.modelo(*rows)

    def test_recusa_campos_identificadores_ambiguos(self):
        for changes in (
            {"NSU operação": ""},
            {"NSU operação": "PIX:RESERVADO"},
            {"Tipo compra": "PIX"},
            {"Id do Pix": "E-CARTAO"},
            {"Loja": ""},
            {"Tipo compra": "Parcelado"},
            {"Parcelas": "2"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.modelo(linha(**changes))

    def test_lojas_distintas_bloqueiam_inclusive_no_historico(self):
        with self.assertRaises(ValueError):
            self.modelo(linha("A"), linha("B", Loja="Outra loja sintética"))
        model = self.modelo(linha("A"))
        other = self.modelo(linha("B", Loja="Outra loja sintética"))
        self.assertEqual(analisar_lotes(other, model).relatorio.estado, "BLOQUEADO")

    def test_limites_ofx_sem_truncar_identidade_ou_descricao_origem(self):
        row = linha(Loja="Loja Sintética com nome extenso " * 10, POS="TERMINAL" * 30)
        model = self.modelo(row)
        self.assertLessEqual(len(model.statements[0].transactions[0].memo), 255)
        self.assertEqual(len(model.statements[0].bankacctfrom.acctid), 22)
        self.assertEqual(analisar_lotes(model).relatorio.estado, "PRIMEIRA_IMPORTACAO")

    def test_valores_datas_tarifas_split_e_precisao_nao_homologados_bloqueiam(self):
        cases = [
            {"Valor líquido": v}
            for v in ("-1,00", "0,00", "NaN", "1.23", "100,001", "2.000,00")
        ]
        cases += [
            {"Valor tarifa": "1,00"},
            {"Valor split": "1,00"},
            {"Valor total bruto": "2.000,00"},
            {"Taxa Adm": "2%"},
            {"Data de pagamento": "09/11/2026"},
            {"Data de pagamento": "31/02/2026"},
            {
                "Valor líquido": "9" * 40,
                "Valor total bruto": "9" * 40,
                "Valor parcela bruto": "9" * 40,
            },
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.modelo(linha(**changes))

    def test_cabecalho_incompleto_duplicado_e_linha_malformada(self):
        raw = dados(linha()).decode("utf-8-sig")
        for bad in (
            raw.replace("Loja;", "Outra;"),
            raw.replace("POS;", "Loja;"),
            raw + "Pago;incompleto\n",
            raw.replace("SYNTH-001", "ID\x00INVALIDO"),
        ):
            p = self.root / "bad.csv"
            p.write_text(bad, encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_csv_valori(p)

    def test_reimportacao_e_conflitos_de_valor_data_e_metadados(self):
        first = self.modelo(linha())
        self.assertEqual(
            analisar_lotes(self.modelo(linha()), first).relatorio.estado,
            "SEM_NOVIDADES",
        )
        for change in (
            {"Valor líquido": "960,00"},
            {"Data de pagamento": "13/11/2026"},
            {"Autorização": "OUTRA"},
            {"POS": "OUTRO"},
        ):
            with self.subTest(change=change):
                self.assertEqual(
                    analisar_lotes(
                        self.modelo(linha(**change)), first
                    ).relatorio.estado,
                    "BLOQUEADO",
                )

    def test_nsu_secundario_pix_conflita_entre_lotes(self):
        first = self.modelo(linha("A", **{"Tipo compra": "PIX", "Id do Pix": "E-1"}))
        for row in (
            linha("A", **{"Tipo compra": "PIX", "Id do Pix": "E-2"}),
            linha("A"),
        ):
            self.assertEqual(
                analisar_lotes(self.modelo(row), first).relatorio.estado, "BLOQUEADO"
            )

    def test_lote_independente_sem_sobreposicao_preserva_inclusive_datas_anteriores(
        self,
    ):
        first = self.modelo(linha("A", **{"Data de pagamento": "14/11/2026"}))
        second = self.modelo(linha("B"))
        self.assertEqual(analisar_lotes(second, first).relatorio.novas.quantidade, 1)
        union = consolidar_historicos([first, second, first])
        self.assertEqual(
            {t.fitid for t in union.statements[0].transactions}, {"A", "B"}
        )
        self.assertEqual(union.statements[0].ledgerbal.balamt, Decimal("1940.50"))
        self.assertEqual(
            union.statements[0].banktranlist.dtstart.date(), date(2026, 11, 12)
        )

    def test_historicos_nao_canonicos_e_metadados_adulterados_bloqueiam(self):
        first = self.modelo(linha())
        for alter in ("banco", "memo", "tipo", "loja", "agencia", "saldo", "periodo"):
            old = interpretar_ofx("xml", serializar_ofx(first))
            st = old.statements[0]
            if alter == "saldo":
                st.ledgerbal.balamt = Decimal("1")
            if alter == "periodo":
                st.banktranlist.dtend = st.banktranlist.dtend.replace(year=2027)
            if alter == "banco":
                st.bankacctfrom.bankid = "999"
            if alter == "memo":
                st.transactions[0].memo = "sem origem"
            if alter == "tipo":
                st.transactions[0].trntype = "DEBIT"
            if alter == "agencia":
                st.bankacctfrom.branchid = "0001"
            if alter == "loja":
                meta = json.loads(st.transactions[0].memo[9:])
                meta[0] = "0" * 64
                st.transactions[0].memo = "VALORI:1 " + json.dumps(
                    meta, separators=(",", ":")
                )
            with self.subTest(alter=alter):
                self.assertEqual(
                    analisar_lotes(first, old).relatorio.estado, "BLOQUEADO"
                )

    def test_publicacao_original_xlsx_limpo_geral_reimportacao_e_novo_dia(self):
        src = self.criar(linha("A"))
        original = src.read_bytes()
        xlsx = self.root / "anexo.xlsx"
        xlsx.write_bytes(b"ANEXO SINTETICO")
        first = planejar(self.root, self.bank, src, [xlsx], hoje=self.day)
        out = executar(first)
        self.assertEqual((out / src.name).read_bytes(), original)
        self.assertEqual((out / xlsx.name).read_bytes(), b"ANEXO SINTETICO")
        self.assertFalse(src.exists())
        self.assertFalse(xlsx.exists())
        src = self.criar(linha("A"))
        second = planejar(self.root, self.bank, src, hoje=self.day)
        self.assertEqual(second.resultado.relatorio.estado, "SEM_NOVIDADES")
        before = first.geral.read_bytes()
        executar(second)
        self.assertEqual(first.geral.read_bytes(), before)
        clean = next(p for p in second.importacao.iterdir() if eh_nome_limpo(p.name))
        self.assertEqual(len(carregar_ofx(clean)[1].statements[0].transactions), 0)
        src = self.criar(linha("B", **{"Data de pagamento": "13/11/2026"}))
        third = planejar(self.root, self.bank, src, hoje=date(2026, 11, 15))
        executar(third)
        self.assertEqual(
            {t.fitid for t in carregar_ofx(third.geral)[1].statements[0].transactions},
            {"A", "B"},
        )
        self.assertEqual(first.geral.read_bytes(), before)
        src = self.criar(linha("A", **{"Valor líquido": "900,00"}))
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.bank, src, hoje=date(2026, 11, 15))
        self.assertTrue(src.exists())

    def test_cc_legado_bloqueia_sem_modificar_historico(self):
        from controller.organization import pasta_dia

        olddir = pasta_dia(self.bank, date(2026, 11, 13))
        olddir.mkdir(parents=True)
        old = olddir / "OFXGeral-2026-11-13.ofx"
        raw = fixture([("20261112120000", "10", "OLD", "Sintetico")]).replace(
            b"CHECKING", b"CC"
        )
        old.write_bytes(raw)
        src = self.criar(linha())
        with self.assertRaisesRegex(OrganizacaoError, "CC.*não comprovada"):
            planejar(self.root, self.bank, src, hoje=self.day)
        self.assertEqual(old.read_bytes(), raw)
        self.assertTrue(src.exists())
        self.assertFalse(safe_storage.pendencias(self.bank))

    def interromper(self, plan, phase="depois"):
        real = (
            safe_storage.publicar_arquivo
            if phase == "depois"
            else safe_storage.escrever
        )

        def fail(*args):
            if phase == "antes" and args[0].name != plan.limpo_nome:
                return real(*args)
            if phase == "depois":
                real(*args)
            raise OSError("interrupção sintética")

        target = "publicar_arquivo" if phase == "depois" else "escrever"
        with patch.object(safe_storage, target, side_effect=fail):
            with self.assertRaises(OSError):
                executar(plan)
        return safe_storage.pendencias(plan.banco)[0]

    def test_recuperacao_valori_preparando_e_depois_publicar_geral(self):
        for phase in ("antes", "depois"):
            with self.subTest(phase=phase):
                src = self.criar(linha("A"))
                plan = planejar(self.root, self.bank, src, hoje=self.day)
                op = self.interromper(plan, phase)
                manifest = json.loads(
                    (op / "manifesto.json").read_text(encoding="utf-8")
                )
                self.assertEqual(manifest["formato_csv"], "valori")
                with safe_storage.bloquear(plan.banco):
                    safe_storage.recuperar_concluida(plan.banco)
                self.assertFalse(safe_storage.pendencias(plan.banco))
                self.assertEqual(src.exists(), phase == "antes")
                if src.exists():
                    src.unlink()

    def test_manifesto_descritor_errado_ou_ausente_bloqueia_recuperacao(self):
        for formato in (None, "rede", "desconhecido"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bank = root / "Valori"
                bank.mkdir()
                src = root / "entrada.csv"
                src.write_bytes(dados(linha()))
                plan = planejar(root, bank, src, hoje=self.day)
                op = self.interromper(plan)
                m = json.loads((op / "manifesto.json").read_text(encoding="utf-8"))
                if formato is None:
                    m.pop("formato_csv")
                else:
                    m["formato_csv"] = formato
                safe_storage.atualizar_manifesto(op, m)
                with safe_storage.bloquear(plan.banco), self.assertRaises(
                    OrganizacaoError
                ):
                    safe_storage.recuperar_concluida(plan.banco)
                self.assertTrue(src.exists())

    def test_historico_de_outro_dia_alterado_bloqueia_recuperacao(self):
        src = self.criar(linha("A"))
        first = planejar(self.root, self.bank, src, hoje=self.day)
        executar(first)
        src = self.criar(linha("B"))
        plan = planejar(self.root, self.bank, src, hoje=date(2026, 11, 15))
        self.interromper(plan)
        first.geral.write_bytes(first.geral.read_bytes() + b"\n")
        with safe_storage.bloquear(plan.banco), self.assertRaises(OrganizacaoError):
            safe_storage.recuperar_concluida(plan.banco)
        self.assertTrue(src.exists())

    def test_rede_valori_banking_roteamento_conjunto_e_anexo_explicito(self):
        rede = self.root / "Rede"
        rede.mkdir()
        banking = self.root / "Valori - Banking"
        banking.mkdir()
        val = self.criar(linha(), name="B-valori.csv")
        red = self.root / "A-rede.csv"
        red.write_bytes(rede_csv(rede_linha("REDE-SYNTH")))
        xlsx = self.root / "C-anexo.xlsx"
        xlsx.write_bytes(b"SINTETICO")
        self.assertEqual(csvs_extrato(self.root), [red, val])
        self.assertEqual(anexos(self.root), [xlsx])
        hybrid = self.root / "hibrido.csv"
        hybrid.write_text(
            "Loja;NSU operação;Data de pagamento;Tipo compra;Status da venda;NSU/CV\n"
        )
        self.assertEqual(identificar_csv(hybrid), "ambiguo")
        self.assertNotIn(hybrid, anexos(self.root))
        self.assertNotIn(hybrid, csvs_extrato(self.root))
        hybrid.unlink()
        for bank, src in (
            (rede, val),
            (self.bank, red),
            (banking, val),
            (banking, red),
        ):
            self.assertFalse(extrato_permitido(bank, src))
            with self.assertRaises(OrganizacaoError):
                planejar(self.root, bank, src, hoje=self.day)
        answers = iter(["2", "1", "1"])
        bank, src, attachments = selecionar(
            self.root, lambda _: next(answers), lambda _: None
        )
        self.assertEqual((bank, src, attachments), (self.bank, val, [xlsx]))
        plan = planejar(self.root, bank, src, attachments, hoje=self.day)
        executar(plan)
        self.assertTrue(red.exists())
        self.assertFalse(val.exists())
        executar(planejar(self.root, rede, red, hoje=self.day))
        self.assertFalse(red.exists())
        self.assertEqual(list(banking.iterdir()), [])

    def test_valori_casefold_banking_e_csv_desconhecido(self):
        src = self.criar(linha())
        self.assertTrue(extrato_permitido(Path("vAlOrI"), src))
        self.assertFalse(extrato_permitido(Path("Valori - Banking"), src))
        unknown = self.root / "unknown.csv"
        unknown.write_text("abc;xyz\n1;2\n")
        self.assertFalse(extrato_permitido(self.bank, unknown))
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.bank, unknown, hoje=self.day)
        self.bank.rmdir()
        (self.root / "Valori - Banking").mkdir()
        with self.assertRaises(OrganizacaoError):
            selecionar(self.root, lambda _: "1", lambda _: None)

    def test_csv_bancario_nao_pode_ser_anexo(self):
        src = self.criar(linha())
        other = self.criar(linha("B"), name="outro.csv")
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.bank, src, [other], hoje=self.day)
        ofx = self.root / "entrada.ofx"
        ofx.write_bytes(fixture([("20261112120000", "10", "X", "Sintetico")]))
        with self.assertRaises(OrganizacaoError):
            planejar(self.root, self.bank, ofx, [src], hoje=self.day)
