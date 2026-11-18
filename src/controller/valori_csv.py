"""Recebimentos pagos Valori: conversão em memória, sem inferir conta bancária."""

import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from types import SimpleNamespace
from decimal import Decimal, InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET
from .csv_formats import VALORI_CAMPOS, decodificar
from .rede_csv import normalizar
from .ofx_io import interpretar_ofx
from .ofx_comparison import (
    identificar_conta,
    _validar_transacoes,
    _totais,
    Relatorio,
    Resultado,
)
from .organization import OrganizacaoError

PREFIXO_META = "VALORI:1 "
PREFIXO_META_V2 = "VALORI:2 "
PARCELA_SEPARADOR = ":PARC:"
MODALIDADES = {"credito a vista": "Crédito à Vista", "debito": "Débito", "pix": "Pix", "parcelamento sem juros": "Parcelamento sem Juros"}
BANKID = "000"  # Conta virtual do livro de liquidações, não um código bancário real.


def identidade_loja(loja):
    # Não remover acentos, alterar caixa ou inferir equivalência entre lojas.
    return (
        "VLR"
        + hashlib.sha256(
            unicodedata.normalize("NFC", loja.strip()).encode("utf-8")
        ).hexdigest()[:19]
    )


def _valor(texto, campo, linha, positivo=False):
    s = texto.strip().removeprefix("R$").strip()
    if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?", s):
        raise ValueError(f"CSV Valori linha {linha}: {campo} inválido")
    try:
        value = Decimal(s.replace(".", "").replace(",", "."))
        if not value.is_finite() or (positivo and value <= 0):
            raise ValueError
        return value
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"CSV Valori linha {linha}: {campo} inválido") from exc


def _data(texto, hora=False):
    try:
        return datetime.strptime(texto, "%d/%m/%Y %H:%M:%S" if hora else "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError("CSV Valori: data de venda ou pagamento inválida") from exc


def ler_transacoes(path):
    texto = decodificar(Path(path).read_bytes())
    obrigatorios = {normalizar(c) for c in VALORI_CAMPOS}
    delimitadores = []
    for sep in (";", ",", "\t"):
        try:
            names = [
                normalizar(c)
                for c in next(
                    csv.reader(
                        io.StringIO(texto, newline=""), delimiter=sep, strict=True
                    )
                )
            ]
            if obrigatorios <= set(names) and len(names) == len(set(names)):
                delimitadores.append(sep)
        except (StopIteration, csv.Error):
            continue
    if len(delimitadores) != 1:
        raise ValueError("CSV Valori: cabeçalho ausente, duplicado ou incompatível")
    reader = csv.DictReader(
        io.StringIO(texto, newline=""), delimiter=delimitadores[0], strict=True
    )
    txs = []
    lojas = set()
    nsus = {}
    pixids = set()
    fitids = set()
    try:
        for row in reader:
            n = reader.line_num
            if None in row or any(v is None for v in row.values()):
                raise ValueError(
                    f"CSV Valori linha {n}: colunas incompletas ou excedentes"
                )
            row = {normalizar(k): v.strip() for k, v in row.items()}
            if not any(row.values()):
                continue
            if any(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", v) for v in row.values()):
                raise ValueError(f"CSV Valori linha {n}: caractere inválido")

            def get(k, required=True):
                v = row[normalizar(k)]
                if required and not v:
                    raise ValueError(
                        f"CSV Valori linha {n}: campo obrigatório vazio: {k}"
                    )
                return v

            status = normalizar(get("Status"))
            if status not in ("pago", "pendente"):
                raise ValueError("CSV Valori: status não homologado")
            loja = unicodedata.normalize("NFC", get("Loja"))
            lojas.add(loja)
            if len(lojas) != 1:
                raise ValueError("CSV Valori mistura lojas; separe os relatórios")
            venda = _data(get("Data de transação"), hora=True)
            pagamento = _data(get("Data de pagamento"))
            if pagamento.date() < venda.date():
                raise ValueError("CSV Valori: pagamento anterior à venda")
            modalidade = normalizar(get("Tipo compra"))
            if modalidade not in MODALIDADES:
                raise ValueError("CSV Valori: modalidade não homologada")
            parcelas = get("Parcelas")
            parcelado = modalidade == "parcelamento sem juros"
            if not parcelas.isascii() or not parcelas.isdecimal():
                raise ValueError("CSV Valori: quantidade de parcelas inválida")
            numero_parcelas = int(parcelas)
            if (parcelado and not 2 <= numero_parcelas <= 99) or (
                not parcelado and numero_parcelas != 1
            ):
                raise ValueError("CSV Valori: modalidade e número de parcelas incompatíveis")
            liquido = _valor(get("Valor líquido"), "valor líquido", n, True)
            bruto = _valor(get("Valor parcela bruto"), "valor parcela bruto", n, True)
            total = _valor(get("Valor total bruto"), "valor total bruto", n, True)
            tarifa = _valor(get("Valor tarifa"), "tarifa", n)
            split = _valor(get("Valor split"), "split", n)
            if tarifa != 0 or split != 0:
                raise ValueError(
                    "CSV Valori: tarifa/split não zero exige contrato financeiro confirmado"
                )
            if liquido > bruto or (not parcelado and total != bruto) or (
                parcelado and (bruto >= total or total <= 0)
            ):
                raise ValueError("CSV Valori: relação bruto/parcela/líquido inválida")
            taxa = get("Taxa Adm")
            if not re.fullmatch(r"\d+(?:,\d+)?", taxa):
                raise ValueError(
                    "CSV Valori: Taxa Adm inválida; unidade não é inferida"
                )
            nsu = get("NSU operação")
            pix = get("Id do Pix", False)
            if nsu.startswith("PIX:") or PARCELA_SEPARADOR in nsu:
                raise ValueError("CSV Valori: NSU reservado; identificador ambíguo")
            if nsu in nsus:
                anterior = nsus[nsu]
                if not parcelado or anterior["modalidade"] != modalidade or anterior["parcelas"] != parcelas:
                    raise ValueError("CSV Valori: NSU duplicado em modalidades incompatíveis")
                if len(anterior["fitids"]) >= numero_parcelas:
                    raise ValueError("CSV Valori: parcelas excedem a quantidade declarada")
            if modalidade == "pix":
                if not pix or pix in pixids:
                    raise ValueError("CSV Valori: Id do Pix ausente ou duplicado")
                pixids.add(pix)
                fitid = "PIX:" + pix
            elif pix:
                raise ValueError("CSV Valori: Id do Pix em modalidade não Pix")
            else:
                fitid = nsu
            meta = {
                "loja": loja,
                "nsu": nsu,
                "pix": pix,
                "venda": venda.isoformat(),
                "pagamento": pagamento.date().isoformat(),
                "modalidade": MODALIDADES[modalidade],
                "autorizacao": get("Autorização", False),
                "bandeira": get("Bandeira"),
                "bruto": f"{bruto:.2f}",
                "pos": get("POS", False),
                "adquirente": get("Cod. acquirer", False),
                "parcelas": parcelas,
                "taxa_adm": taxa,
                "tarifa": f"{tarifa:.2f}",
                "split": f"{split:.2f}",
                "status": "Pago" if status == "pago" else "Pendente",
            }
            if parcelado:
                meta["total_bruto"] = f"{total:.2f}"
                # O NSU identifica a venda, não a parcela. Não depender da
                # posição da linha: líquidos distintos identificam parcelas
                # sem inventar números que o relatório não informa.
                prova = {
                    "origem": {k: v for k, v in meta.items() if k not in ("pagamento", "status")},
                    "liquido": f"{liquido:.2f}",
                }
                chave = hashlib.sha256(
                    json.dumps(prova, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()[:24]
                fitid = nsu + PARCELA_SEPARADOR + chave
            else:
                chave = ""
            if fitid in fitids:
                raise ValueError("CSV Valori: FITID de parcela repetido ou linha duplicada")
            if len(fitid) > 255:
                raise ValueError("CSV Valori: identificador excede limite OFX")
            fitids.add(fitid)
            if nsu not in nsus:
                nsus[nsu] = {"modalidade": modalidade, "parcelas": parcelas, "fitids": set()}
            nsus[nsu]["fitids"].add(fitid)
            txs.append(
                {
                    "fitid": fitid,
                    "valor": liquido,
                    "data": pagamento.date(),
                    "meta": meta,
                    "chave_parcela": chave,
                }
            )
    except csv.Error as exc:
        raise ValueError("CSV Valori malformado") from exc
    if not txs:
        raise ValueError("CSV Valori sem movimentações")
    txs.sort(key=lambda t: (t["data"], t["fitid"]))
    return txs


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def metadados(t):
    # Lista compacta: preserva a prova da origem sem ultrapassar MEMO(255).
    # Descrições completas e dados opcionais ficam no CSV original arquivado.
    meta = t["meta"]
    origem = json.dumps({k: v for k, v in meta.items() if k != "status"}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    modalidade = {"Crédito à Vista": "C", "Débito": "D", "Pix": "P", "Parcelamento sem Juros": "S"}[meta["modalidade"]]
    comuns = [
        _sha(meta["loja"]),
        _sha(meta["nsu"]),
        _sha(origem),
        meta["venda"],
        modalidade,
    ]
    # MEMO OFX tem limite de 255 caracteres: hash de origem com 128 bits
    # para registrar estado, quantidade e chave da parcela.
    comuns[2] = comuns[2][:32]
    return comuns + [
        "P" if meta["status"] == "Pago" else "N",
        meta["parcelas"],
        t["chave_parcela"],
    ]


def montar_modelo(txs):
    _validar_transacoes(
        [
            SimpleNamespace(
                fitid=t["fitid"],
                dtposted=datetime.combine(t["data"], datetime.min.time(), timezone.utc),
                trnamt=t["valor"],
                trntype="CREDIT",
            )
            for t in txs
        ],
        "CSV Valori",
    )

    def sub(parent, tag, value=None):
        node = ET.SubElement(parent, tag)
        if value is not None:
            node.text = str(value)
        return node

    root = ET.Element("OFX")
    sonrs = sub(sub(root, "SIGNONMSGSRSV1"), "SONRS")
    st = sub(sonrs, "STATUS")
    sub(st, "CODE", 0)
    sub(st, "SEVERITY", "INFO")
    sub(sonrs, "DTSERVER", max(t["data"] for t in txs).strftime("%Y%m%d"))
    sub(sonrs, "LANGUAGE", "POR")
    fi = sub(sonrs, "FI")
    sub(fi, "ORG", "VALORI")
    sub(fi, "FID", "VALORI")
    resp = sub(sub(root, "BANKMSGSRSV1"), "STMTTRNRS")
    sub(
        resp,
        "TRNUID",
        hashlib.sha256(
            json.dumps(txs, default=str, sort_keys=True).encode()
        ).hexdigest()[:32],
    )
    st = sub(resp, "STATUS")
    sub(st, "CODE", 0)
    sub(st, "SEVERITY", "INFO")
    stmt = sub(resp, "STMTRS")
    sub(stmt, "CURDEF", "BRL")
    acct = sub(stmt, "BANKACCTFROM")
    sub(acct, "BANKID", BANKID)
    sub(acct, "ACCTID", identidade_loja(txs[0]["meta"]["loja"]))
    sub(acct, "ACCTTYPE", "CHECKING")
    period = sub(stmt, "BANKTRANLIST")
    sub(period, "DTSTART", min(t["data"] for t in txs).strftime("%Y%m%d"))
    sub(period, "DTEND", max(t["data"] for t in txs).strftime("%Y%m%d"))
    for t in txs:
        node = sub(period, "STMTTRN")
        sub(node, "TRNTYPE", "CREDIT")
        sub(node, "DTPOSTED", t["data"].strftime("%Y%m%d"))
        sub(node, "TRNAMT", str(t["valor"]))
        sub(node, "FITID", t["fitid"])
        status = t["meta"]["status"]
        nome = t["meta"]["modalidade"] if status == "Pago" else (
            "Pendente - Parcelado" if t["meta"]["modalidade"] == "Parcelamento sem Juros"
            else "Pendente - " + t["meta"]["modalidade"]
        )
        sub(node, "NAME", nome)
        dados_meta = metadados(t)
        prefixo = PREFIXO_META if len(dados_meta) == 5 else PREFIXO_META_V2
        memo = prefixo + json.dumps(dados_meta, separators=(",", ":"))
        if len(memo) > 255:
            raise ValueError("CSV Valori: MEMO excede limite OFX")
        sub(node, "MEMO", memo)
    ledger = sub(stmt, "LEDGERBAL")
    # O livro virtual registra pendências, mas o saldo é apenas o recebido.
    sub(ledger, "BALAMT", sum(
        (t["valor"] for t in txs if t["meta"]["status"] == "Pago"), Decimal("0")
    ))
    sub(ledger, "DTASOF", max(t["data"] for t in txs).strftime("%Y%m%d"))
    return interpretar_ofx("xml", ET.tostring(root, encoding="utf-8"))


def carregar_csv_valori(path):
    return "CSV Valori convertido em memória", montar_modelo(ler_transacoes(path))


def carregar_historico(path):
    # Nunca alterar o leitor OFX global para adivinhar que CC significa CHECKING.
    from .ofx_io import preparar_ofx
    from ofxtools.Parser import TreeBuilder
    from .ofx_functions import carregar_ofx

    _, _, body = preparar_ofx(Path(path).read_bytes())
    try:
        tree = ET.fromstring(body)
    except ET.ParseError:
        builder = TreeBuilder()
        builder.feed(body)
        tree = builder.close()
    if tree.findtext(".//BANKACCTFROM/ACCTTYPE") == "CC":
        raise OrganizacaoError(
            "Histórico Valori incompatível: ACCTTYPE CC e conta bancária não comprovada pelo CSV de loja; não mapear automaticamente para CHECKING nem ignorar o histórico"
        )
    return carregar_ofx(path)


def _metas(model):
    conta = identificar_conta(model)
    if (conta.banco, conta.tipo, conta.moeda, conta.instituicao, conta.fid) != (
        BANKID, "CHECKING", "BRL", "VALORI", "VALORI"
    ):
        raise ValueError("Histórico Valori não pertence ao livro de liquidações CSV")
    if model.statements[0].bankacctfrom.branchid is not None:
        raise ValueError("Agência bancária inesperada no livro Valori CSV")
    result = {}
    nsus = {}
    pixs = set()
    lojas = set()
    for t in model.statements[0].transactions:
        if not t.memo:
            raise ValueError("Histórico Valori sem metadados de origem verificáveis")
        v2 = t.memo.startswith(PREFIXO_META_V2)
        if not v2 and not t.memo.startswith(PREFIXO_META):
            raise ValueError("Histórico Valori sem metadados de origem verificáveis")
        prefixo = PREFIXO_META_V2 if v2 else PREFIXO_META
        try:
            meta = json.loads(t.memo[len(prefixo):])
            if (
                not isinstance(meta, list)
                or len(meta) != (8 if v2 else 5)
                or any(not isinstance(v, str) for v in meta)
                or any(not re.fullmatch(r"[0-9a-f]{64}", v) for v in meta[:2])
                or not re.fullmatch(r"[0-9a-f]{32}" if v2 else r"[0-9a-f]{64}", meta[2])
                or meta[4] not in ("C", "D", "P", "S")
            ):
                raise ValueError("Metadados Valori inválidos")
            loja, nsu, origem, venda, modalidade = meta[:5]
            status = meta[5] if v2 else "P"
            parcelas = meta[6] if v2 else "1"
            chave = meta[7] if v2 else ""
            if status not in ("P", "N") or not parcelas.isascii() or not parcelas.isdecimal():
                raise ValueError("Status ou parcelas Valori inválidos")
            if modalidade == "S":
                if not v2 or not 2 <= int(parcelas) <= 99 or not re.fullmatch(r"[0-9a-f]{24}", chave):
                    raise ValueError("Identidade de parcela inválida")
                if t.fitid != nsu + PARCELA_SEPARADOR + chave:
                    raise ValueError("FITID de parcela inconsistente")
            elif chave or parcelas != "1":
                raise ValueError("Metadados de parcela inesperados")
            instante = datetime.strptime(venda, "%Y-%m-%dT%H:%M:%S")
            if (
                "VLR" + loja[:19] != conta.conta
                or t.trntype != "CREDIT"
                or t.trnamt <= 0
                or instante.date() > t.dtposted.date()
                or (status == "N") != t.name.startswith("Pendente - ")
            ):
                raise ValueError("Identidade financeira Valori incompatível")
            lojas.add(loja)
            pix = t.fitid[4:] if modalidade == "P" and t.fitid.startswith("PIX:") else ""
            if (
                len(lojas) > 1 or (modalidade == "P" and not pix)
                or (pix and pix in pixs)
                or (modalidade != "P" and (
                    (modalidade != "S" and _sha(t.fitid) != nsu)
                    or t.fitid.startswith("PIX:")
                ))
                or (nsu in nsus and (modalidade != "S" or nsus[nsu] != "S"))
            ):
                raise ValueError("Identificador Valori ambíguo no histórico")
            nsus[nsu] = modalidade
            if pix:
                pixs.add(pix)
            result[t.fitid] = {
                "loja": loja, "nsu": nsu, "pix": pix,
                "origem": origem, "venda": venda,
                "modalidade": modalidade, "status": status,
                "parcelas": parcelas, "chave": chave,
            }
        except (TypeError, KeyError, IndexError) as exc:
            raise ValueError("Metadados Valori incompletos") from exc
    statement = model.statements[0]
    txs = statement.transactions
    if not txs:
        raise ValueError("Histórico Valori vazio sem prova do estabelecimento")
    confirmado = sum(
        (t.trnamt for t in txs if result[t.fitid]["status"] == "P"),
        Decimal("0"),
    )
    if (
        statement.ledgerbal is None
        or statement.ledgerbal.balamt != confirmado
        or statement.banktranlist.dtstart != min(t.dtposted for t in txs)
        or statement.banktranlist.dtend != max(t.dtposted for t in txs)
        or statement.ledgerbal.dtasof != statement.banktranlist.dtend
    ):
        raise ValueError("Acumulador Valori com saldo ou período divergente")
    return result


def analisar_lotes(atual, anterior=None):
    r = Relatorio()
    try:
        r.conta = identificar_conta(atual)
        tx = atual.statements[0].transactions
        _validar_transacoes(tx, "CSV Valori")
        meta = _metas(atual)
        r.original = _totais(tx)
        if anterior is None:
            r.novas = r.original
            r.estado = "PRIMEIRA_IMPORTACAO"
            return Resultado(r, tuple(range(len(tx))))
        if identificar_conta(anterior) != r.conta:
            raise ValueError("Loja ou identidade financeira Valori incompatível")
        oldtx = anterior.statements[0].transactions
        oldids = _validar_transacoes(oldtx, "Histórico Valori")
        oldmeta = _metas(anterior)
        if {m["loja"] for m in meta.values()} != {m["loja"] for m in oldmeta.values()}:
            raise ValueError("Identidade completa de loja Valori divergente")
        oldnsu = {}
        for k, m in oldmeta.items():
            oldnsu.setdefault(m["nsu"], set()).add(k)
        oldpix = {m["pix"]: k for k, m in oldmeta.items() if m["pix"]}
        indices = []
        dups = []
        for i, t in enumerate(tx):
            m = meta[t.fitid]
            if (m["nsu"] in oldnsu and t.fitid not in oldnsu[m["nsu"]] and m["modalidade"] != "S") or (
                m["pix"] and m["pix"] in oldpix and oldpix[m["pix"]] != t.fitid
            ):
                raise ValueError("Identificador secundário Valori conflitante")
            old = oldids.get(t.fitid)
            if old is not None:
                om = oldmeta[t.fitid]
                campos = ("loja", "nsu", "pix", "venda", "modalidade", "parcelas", "chave")
                metadados_iguais = all(m[c] == om[c] for c in campos)
                # V1 conserva o hash completo da origem; V2 guarda seu prefixo.
                origem_igual = (
                    m["origem"].startswith(om["origem"])
                    or om["origem"].startswith(m["origem"])
                )
                if (t.dtposted, t.trnamt, t.trntype) != (
                    old.dtposted, old.trnamt, old.trntype
                ) or not metadados_iguais or not origem_igual:
                    raise ValueError("Conflito financeiro ou identidade ambígua Valori")
                if om["status"] == "N" and m["status"] == "P":
                    # Atualização do lançamento, não novo recebimento.
                    indices.append(i)
                elif m["status"] == om["status"]:
                    dups.append(t)
                else:
                    raise ValueError("Regressão de pagamento para pendente; exige conciliação")
            else:
                indices.append(i)
        r.anteriores = _totais(oldtx)
        r.duplicatas = _totais(dups)
        r.novas = _totais([tx[i] for i in indices if tx[i].fitid not in oldids])
        r.estado = "APROVADO" if indices else "SEM_NOVIDADES"
        return Resultado(r, tuple(indices))
    except (ValueError, AttributeError, TypeError, KeyError, ArithmeticError) as exc:
        r.motivo = str(exc)
        return Resultado(r)


def _metas_sem_saldo(transacoes):
    """Estados de pagamento já autenticados no MEMO; sem validar saldo anterior."""
    estados = {}
    for t in transacoes:
        memo = t.memo or ""
        if memo.startswith(PREFIXO_META_V2):
            dados = json.loads(memo[len(PREFIXO_META_V2):])
            estados[t.fitid] = dados[5]
        elif memo.startswith(PREFIXO_META):
            estados[t.fitid] = "P"
        else:
            raise ValueError("Transação Valori sem prova de origem")
    return estados


def _atualizar_acumulador(model):
    statement = model.statements[0]
    _validar_transacoes(statement.transactions, "Acumulador Valori")
    statement.transactions.sort(key=lambda t: (t.dtposted, t.fitid))
    statement.banktranlist.dtstart = min(t.dtposted for t in statement.transactions)
    statement.banktranlist.dtend = max(t.dtposted for t in statement.transactions)
    statement.ledgerbal.dtasof = statement.banktranlist.dtend
    meta = _metas_sem_saldo(statement.transactions)
    statement.ledgerbal.balamt = sum(
        (t.trnamt for t in statement.transactions if meta[t.fitid] == "P"),
        Decimal("0")
    )


def consolidar_historicos(modelos):
    from .ofx_io import serializar_ofx

    if not modelos:
        return None
    result = interpretar_ofx("xml", serializar_ofx(modelos[0]))
    validation = analisar_lotes(result)
    if validation.relatorio.estado == "BLOQUEADO":
        raise OrganizacaoError(validation.relatorio.motivo)
    for model in modelos[1:]:
        r = analisar_lotes(model, result)
        if r.relatorio.estado == "BLOQUEADO":
            raise OrganizacaoError(r.relatorio.motivo)
        incoming = r.modelo_filtrado(model).statements[0].transactions
        por_id = {t.fitid: i for i, t in enumerate(result.statements[0].transactions)}
        for tx in incoming:
            if tx.fitid in por_id:
                result.statements[0].transactions[por_id[tx.fitid]] = tx
            else:
                result.statements[0].transactions.append(tx)
        _atualizar_acumulador(result)
    return result
