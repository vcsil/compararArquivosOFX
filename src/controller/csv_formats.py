"""Identificação por cabeçalho e despacho dos formatos CSV bancários."""

import csv
import io
from pathlib import Path
from .rede_csv import normalizar

VALORI_CAMPOS = (
    "Autorização",
    "Loja",
    "POS",
    "Data de transação",
    "Data de pagamento",
    "Bandeira",
    "Cod. acquirer",
    "Tipo compra",
    "Parcelas",
    "Valor total bruto",
    "Valor parcela bruto",
    "Valor líquido",
    "Taxa Adm",
    "Valor tarifa",
    "Valor split",
    "Status",
    "NSU operação",
    "CPF/CNPJ ecomm.",
    "Nome ecomm",
    "Nº Pedido",
    "Id do Pix",
)
INSTITUICOES = {"rede": "rede", "valori": "valori"}
ASSINATURAS = {
    "rede": {"status da venda", "nsu/cv"},
    "valori": {"loja", "nsu operacao", "data de pagamento", "tipo compra"},
}


def decodificar(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV: codificação incompatível") from exc


def identificar_csv(path):
    path = Path(path)
    if path.suffix.casefold() != ".csv":
        return None
    texto = decodificar(path.read_bytes())
    if not texto.strip():
        return None
    encontrados = set()
    for sep in (";", ",", "\t"):
        try:
            campos = {
                normalizar(s)
                for s in next(
                    csv.reader(
                        io.StringIO(texto, newline=""), delimiter=sep, strict=True
                    )
                )
            }
        except (csv.Error, StopIteration):
            continue
        for formato, assinatura in ASSINATURAS.items():
            if assinatura <= campos:
                encontrados.add(formato)
    return (
        next(iter(encontrados))
        if len(encontrados) == 1
        else "ambiguo" if encontrados else None
    )


def csv_bancario(path):
    try:
        return identificar_csv(path) is not None
    except (ValueError, OSError, csv.Error):
        # Arquivo ilegível não pode ser anexado automaticamente por precaução.
        return Path(path).suffix.casefold() == ".csv"


def formato_permitido(banco, formato):
    return (
        formato in INSTITUICOES and Path(banco).name.casefold() == INSTITUICOES[formato]
    )


def carregar_csv(path, formato):
    if identificar_csv(path) != formato:
        raise ValueError("CSV: formato mudou ou não foi reconhecido inequivocamente")
    if formato == "rede":
        from .rede_csv import carregar_csv_rede

        return carregar_csv_rede(path)
    if formato == "valori":
        from .valori_csv import carregar_csv_valori

        return carregar_csv_valori(path)
    raise ValueError("CSV: formato não suportado")
