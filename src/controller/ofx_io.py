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
    """A codificação declarada é ambígua ou não corresponde ao conteúdo."""


def preparar_ofx(raw):
    """Retorna (formato, cabeçalho, corpo) a partir de bytes originais.

    Para CHARSET 1252, UTF-8 válido e não ASCII tem prioridade com aviso;
    bytes inválidos em UTF-8 são decodificados estritamente como cp1252.
    """
    raw = raw.removeprefix(b'\xef\xbb\xbf')
    stripped = raw.lstrip()
    if stripped.startswith(b'<?xml') or stripped.startswith(b'<OFX'):
        return 'xml', str(OFXHeaderV2(version=203)), raw
    # Cabeçalhos SGML são ASCII e encerram antes do elemento raiz.
    match = re.search(br'<OFX(?:\s|>)', raw, re.IGNORECASE)
    if not match:
        raise ValueError('Cabeçalho ou elemento OFX ausente')
    head, body = raw[:match.start()], raw[match.start():]
    charset = re.search(br'(?im)^\s*CHARSET\s*:\s*([^\s]+)', head)
    if charset and charset.group(1).upper() == b'1252':
        try:
            utf8 = body.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            if not utf8.isascii():
                warnings.warn('CHARSET 1252 e bytes UTF-8 válidos: interpretação UTF-8 escolhida; confirme a origem.', OFXEncodingWarning, stacklevel=2)
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
