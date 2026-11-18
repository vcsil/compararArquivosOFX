"""Auditoria local e privada Valori. Saída contém somente contagens e códigos.

Não executar no CI com dados reais. Não executa nenhum conteúdo do ZIP.
Extração e publicação, quando aprovadas, ocorrem em cópia temporária privada.
"""

import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_private_zip import extrair_seguro, sha
from controller.csv_formats import decodificar, identificar_csv
from controller.ofx_io import preparar_ofx, serializar_ofx, interpretar_ofx
from controller.ofx_compat import OFXCompatError
from controller.ofx_functions import carregar_ofx
from controller.organization import OrganizacaoError
from controller.valori_csv import carregar_csv_valori
from controller.workflow import planejar, executar, _assinatura


def codigo(exc):
    # Nunca imprimir a exceção: pode conter identificadores privados.
    text = str(exc).casefold()
    if isinstance(exc, OrganizacaoError):
        if "conflito" in text:
            return "CONFLITO_FINANCEIRO"
        if "cc" in text or "histórico" in text:
            return "HISTORICO_INCOMPATIVEL"
        if "identidade" in text:
            return "METADADO_INCOMPATIVEL"
        if "continuidade" in text or "cobertura" in text:
            return "FALTA_CONTINUIDADE"
        return "BLOQUEIO_SEGURO"
    if isinstance(exc, OFXCompatError):
        return "METADADO_INCOMPATIVEL"
    if isinstance(exc, ValueError):
        return "FALHA_PARSING_OU_CONTRATO"
    return "FALHA_AUDITORIA"


def auditar(arquivo):
    zip_hash = sha(arquivo)
    with tempfile.TemporaryDirectory(prefix="valori-private-") as temp:
        root = Path(temp)
        ref = root / "reference"
        ref.mkdir(mode=0o700)
        extrair_seguro(arquivo, ref)
        originais = {p: sha(p) for p in ref.rglob("*") if p.is_file()}
        csvs = [
            p
            for p in originais
            if p.suffix.casefold() == ".csv" and identificar_csv(p) == "valori"
        ]
        ofxs = [p for p in originais if p.suffix.casefold() == ".ofx"]
        if len(csvs) != 1:
            return {"conversao": "CSV_AUSENTE_OU_AMBIGUO"}
        source = csvs[0]
        rows = list(
            csv.DictReader(io.StringIO(decodificar(source.read_bytes())), delimiter=";")
        )
        try:
            _, model = carregar_csv_valori(source)
        except Exception as exc:
            return {"conversao": codigo(exc), "publicacao": "NAO_EXECUTADA"}
        txs = {t.fitid: t for t in model.statements[0].transactions}
        assert len(rows) == len(txs)
        total = Decimal("0")
        modalidades = Counter()
        pares = 0
        # Leitura independente de CADA linha: valor, sinal, ID e data financeira.
        for row in rows:
            pix = row["Tipo compra"].strip().casefold() == "pix"
            fitid = (
                "PIX:" + row["Id do Pix"].strip()
                if pix
                else row["NSU operação"].strip()
            )
            value = Decimal(
                row["Valor líquido"]
                .strip()
                .removeprefix("R$")
                .strip()
                .replace(".", "")
                .replace(",", ".")
            )
            day = datetime.strptime(row["Data de pagamento"].strip(), "%d/%m/%Y").date()
            sale = datetime.strptime(
                row["Data de transação"].strip(), "%d/%m/%Y %H:%M:%S"
            )
            tx = txs[fitid]
            assert tx.fitid == fitid and tx.trnamt == value and tx.trntype == "CREDIT"
            assert tx.dtposted.date() == day and sale.date() <= day
            assert tx.refnum.startswith("V3") and len(tx.refnum) == 32
            assert " - " + row["Bandeira"].strip() + " - " in tx.memo
            assert row["Tipo compra"].strip() in tx.memo
            assert tx.memo.endswith(" - PENDENTE") == (row["Status"].strip().casefold() == "pendente")
            total += value
            modalidades[row["Tipo compra"].strip().casefold()] += 1
            pares += 1
        assert (
            total
            == sum((t.trnamt for t in txs.values()), Decimal("0"))
            == model.statements[0].ledgerbal.balamt
        )
        assert _assinatura(model) == _assinatura(
            interpretar_ofx("xml", serializar_ofx(model))
        )
        matches = 0
        cc = 0
        from ofxtools.Parser import TreeBuilder

        # Analisa os históricos brutos sem lhes alterar ACCTTYPE ou dados financeiros.
        seen = set()
        for old in ofxs:
            _, _, body = preparar_ofx(old.read_bytes())
            try:
                tree = ET.fromstring(body)
            except ET.ParseError:
                builder = TreeBuilder()
                builder.feed(body)
                tree = builder.close()
            if tree.findtext(".//BANKACCTFROM/ACCTTYPE") == "CC":
                cc += 1
            if sha(old) in seen:
                continue
            seen.add(sha(old))
            for node in tree.iter("STMTTRN"):
                fitid = node.findtext("FITID")
                if fitid in txs:
                    tx = txs[fitid]
                    assert Decimal(node.findtext("TRNAMT")) == tx.trnamt
                    assert node.findtext("TRNTYPE") == tx.trntype
                    assert node.findtext("DTPOSTED")[:8] == tx.dtposted.strftime(
                        "%Y%m%d"
                    )
                    matches += 1
        result = {
            "conversao": "APROVADA",
            "registros_conferidos_individualmente": pares,
            "modalidades": dict(modalidades),
            "conservacao_totais": True,
            "historicos": len(ofxs),
            "conteudos_historicos_distintos": len(seen),
            "historicos_cc": cc,
            "correspondencias_historicas_conferidas": matches,
        }
        work = root / "work"
        work.mkdir(mode=0o700)
        candidates = [
            p for p in ref.rglob("*") if p.is_dir() and p.name.casefold() == "valori"
        ]
        bank = work / "Valori"
        if len(candidates) == 1:
            shutil.copytree(candidates[0], bank)
        elif ofxs:
            return {**result, "publicacao": "ESTRUTURA_HISTORICA_AMBIGUA"}
        else:
            bank.mkdir()
        entrada = work / "entrada.csv"
        shutil.copyfile(source, entrada)
        annexes = []
        for i, p in enumerate(p for p in originais if p.suffix.casefold() == ".xlsx"):
            target = work / f"anexo-{i}.xlsx"
            shutil.copyfile(p, target)
            annexes.append(target)
        history_before = {p: sha(p) for p in bank.rglob("*") if p.is_file()}
        input_hashes = {p: sha(p) for p in (entrada, *annexes)}
        try:
            plan = planejar(work, bank, entrada, annexes)
            out = executar(plan)
        except Exception as exc:
            result["publicacao"] = codigo(exc)
            assert all(p.exists() and sha(p) == h for p, h in input_hashes.items())
            assert all(p.exists() and sha(p) == h for p, h in history_before.items())
        else:
            assert all(
                not p.exists() and sha(out / p.name) == h
                for p, h in input_hashes.items()
            )
            assert _assinatura(carregar_ofx(plan.geral)[1]) == plan.assinatura_geral
            assert (
                _assinatura(carregar_ofx(out / plan.limpo_nome)[1])
                == plan.assinatura_limpo
            )
            result["publicacao"] = "IMPORTACAO_APROVADA"
        assert (
            all(sha(p) == h for p, h in originais.items()) and sha(arquivo) == zip_hash
        )
        result["referencias_preservadas"] = True
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    args = parser.parse_args()
    try:
        result = auditar(args.zip)
    except Exception as exc:
        result = {"auditoria": codigo(exc), "publicacao": "NAO_COMPROVADA"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "auditoria" in result or result.get("conversao") != "APROVADA":
        return 1
    # Distinção explícita: conversão válida não é publicação aprovada.
    return 0 if result.get("publicacao") == "IMPORTACAO_APROVADA" else 2


if __name__ == "__main__":
    sys.exit(main())
