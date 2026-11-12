"""Leitura e serialização OFX sem modificar o arquivo de entrada."""
import io
import re
import warnings
from datetime import timezone
import xml.etree.ElementTree as ET

from ofxtools.Parser import OFXTree, TreeBuilder
from ofxtools.header import OFXHeaderV2, parse_header
from ofxtools.Types import DateTime


class OFXEncodingWarning(UserWarning):
    """A codificação declarada não corresponde ao conteúdo."""


class OFXEncodingAmbiguaError(ValueError):
    """O conteúdo tem interpretações distintas e válidas em UTF-8 e CP1252."""


def preparar_ofx(raw, *, codificacao=None):
    """Retorna (formato, cabeçalho, corpo) a partir de bytes originais.

    Para CHARSET 1252, aceita escolha explícita 'utf-8' ou 'cp1252'.
    Sem escolha, rejeita interpretações diferentes igualmente válidas.
    """
    raw = raw.removeprefix(b'\xef\xbb\xbf')
    stripped = raw.lstrip()
    if stripped.startswith(b'<?xml') or stripped.startswith(b'<OFX'):
        if codificacao is not None:
            raise ValueError('Escolha de codificação disponível apenas para SGML com CHARSET:1252')
        return 'xml', str(OFXHeaderV2(version=203)), raw
    # Cabeçalhos SGML são ASCII e encerram antes do elemento raiz.
    match = re.search(br'<OFX(?:\s|>)', raw, re.IGNORECASE)
    if not match:
        raise ValueError('Cabeçalho ou elemento OFX ausente')
    head, body = raw[:match.start()], raw[match.start():]
    charset = re.search(br'(?im)^\s*CHARSET\s*:\s*([^\s]+)', head)
    if codificacao not in (None, 'utf-8', 'cp1252'):
        raise ValueError("codificacao deve ser 'utf-8', 'cp1252' ou None")
    if codificacao is not None and not (charset and charset.group(1).upper() == b'1252'):
        raise ValueError('Escolha de codificação disponível apenas para SGML com CHARSET:1252')
    if charset and charset.group(1).upper() == b'1252':
        try:
            cp1252 = body.decode('cp1252')
        except UnicodeDecodeError:
            cp1252 = None
        try:
            utf8 = body.decode('utf-8')
        except UnicodeDecodeError:
            utf8 = None
        if codificacao == 'cp1252':
            body.decode('cp1252')  # valida sem substituição
        elif codificacao == 'utf-8':
            body.decode('utf-8')
        elif cp1252 is None:
            if utf8 is None:
                body.decode('cp1252')  # propaga erro de decodificação
            codificacao = 'utf-8'
            warnings.warn('CHARSET 1252 inválido; conteúdo UTF-8 será validado como OFX.', OFXEncodingWarning, stacklevel=2)
        elif utf8 is not None and utf8 != cp1252:
            raise OFXEncodingAmbiguaError("CHARSET 1252: UTF-8 e CP1252 são válidos e produzem textos diferentes; informe codificacao='utf-8' ou 'cp1252'.")
        if codificacao == 'utf-8':
            head = head[:charset.start(1)] + b'NONE' + head[charset.end(1):]
    header, message = parse_header(io.BytesIO(head + body))
    return 'sgml', str(header).replace('\r\n', '\n'), message


def interpretar_ofx(formato, corpo):
    """Converte árvore XML ou SGML para o modelo existente do ofxtools."""
    tree = OFXTree()
    if formato == 'xml':
        root = ET.fromstring(corpo)
    else:
        # A saída histórica possui cabeçalho v1 e corpo XML completo.
        try:
            root = ET.fromstring(corpo)
        except ET.ParseError:
            builder = TreeBuilder()
            builder.feed(corpo)
            root = builder.close()
    # ElementTree mantém a indentação entre agregados; ofxtools a interpreta
    # como valor quando não é removida. Preserve textos dos elementos folha.
    for element in root.iter():
        if len(element) and element.text is not None and not element.text.strip():
            element.text = None
        element.tail = None
    if root.tag != 'OFX':
        raise ValueError('O elemento raiz deve ser OFX')
    tree._root = root
    model = tree.convert()
    # ofxtools normaliza datas lidas em UTC; restaure o deslocamento explícito
    # de DTPOSTED para preservar também o dia local e a informação de fuso.
    nodes = list(root.iter('STMTTRN'))
    transactions = [item for statement in model.statements for item in statement.transactions]
    if len(nodes) != len(transactions):
        raise ValueError('Não foi possível associar todas as transações do OFX')
    field = DateTime()
    for node, transaction in zip(nodes, transactions):
        if node.findtext('FITID') != transaction.fitid:
            raise ValueError('Ordem das transações não corresponde ao documento')
        value = node.findtext('DTPOSTED')
        match = field.regex.fullmatch(value or '')
        if match and match.group('gmt_offset_hours') is not None:
            hours, minutes, name = (match.group('gmt_offset_hours'),
                                    match.group('gmt_offset_minutes'),
                                    match.group('tz_name'))
            offset = field.parse_gmt_offset(hours, minutes, name)
            zone = timezone(offset, name) if name else timezone(offset)
            transaction.dtposted = transaction.dtposted.astimezone(zone)
    return model


def serializar_ofx(ofx):
    """Gera XML OFX 2.03 em UTF-8, independente do encoding do processo."""
    header = str(OFXHeaderV2(version=203)).encode('utf-8')
    return header + ET.tostring(ofx.to_etree(), encoding='utf-8')
