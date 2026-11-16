"""Compatibilidade determinística de exportadores; nunca escreve no original."""
from decimal import Decimal, InvalidOperation
import hashlib
import re
from ofxtools.Types import DateTime


class OFXCompatError(ValueError):
    """Erro sanitizado: detalhes do documento não devem aparecer no terminal."""


def normalizar_arvore(root):
    alteracoes = []
    # ORG é nome textual, não BANKID/FID/ACCTID. Hash evita colisão de prefixos.
    for org in root.findall('./SIGNONMSGSRSV1/SONRS/FI/ORG'):
        if org.text and len(org.text) > 32:
            org.text = 'ORG:' + hashlib.sha256(org.text.encode('utf-8')).hexdigest()[:28]
            alteracoes.append('FI.ORG longo normalizado por hash')
    # DTASOF zerado: vincular ao DTEND válido do MESMO demonstrativo, sem
    # tocar em BALAMT ou DTPOSTED e sem usar relógio local.
    for stmt in root.findall('./BANKMSGSRSV1/STMTTRNRS/STMTRS'):
        saldo_data = stmt.find('./LEDGERBAL/DTASOF')
        if saldo_data is not None and re.fullmatch(r'0+', saldo_data.text or ''):
            referencia = stmt.findtext('./BANKTRANLIST/DTEND')
            try:
                if DateTime().convert(referencia) is None:
                    raise ValueError
            except (ValueError, TypeError, OverflowError) as exc:
                raise OFXCompatError('Metadado de saldo incompatível: data zerada sem DTEND válido no demonstrativo') from exc
            saldo_data.text = referencia
            alteracoes.append('Data do saldo zerada associada ao DTEND do demonstrativo')
    # Exportação legada com SIGNON após BANKMSGS: reposicionar o agregado
    # de resposta; não altera sua identificação nem movimentações.
    signons = root.findall('SIGNONMSGSRSV1')
    if len(signons) == 1 and list(root).index(signons[0]) != 0:
        root.remove(signons[0]); root.insert(0, signons[0])
        alteracoes.append('Ordem de resposta SIGNON corrigida')
    for servidor in root.findall('./SIGNONMSGSRSV1/SONRS/DTSERVER'):
        if re.fullmatch(r'0+', servidor.text or ''):
            referencias = []
            for tag in ('DTASOF', 'DTEND'):
                for node in root.iter(tag):
                    try:
                        dt = DateTime().convert(node.text)
                        if dt is not None:
                            referencias.append((dt, node.text))
                    except (ValueError, TypeError, OverflowError):
                        continue
                if referencias:
                    break
            if not referencias:
                raise OFXCompatError('Metadado OFX incompatível: DTSERVER zerado sem data de referência válida')
            servidor.text = max(referencias, key=lambda x: (x[0], x[1]))[1]
            alteracoes.append('DTSERVER zerado substituído por referência do demonstrativo')
    externos = root.findall('./BANKACCTFROM')
    if externos:
        statements = root.findall('./BANKMSGSRSV1/STMTTRNRS/STMTRS')
        if len(externos) != 1 or len(statements) != 1 or statements[0].find('BANKACCTFROM') is not None:
            raise OFXCompatError('OFX inválido: identificação de conta fora do demonstrativo é ambígua')
        root.remove(externos[0])
        stmt = statements[0]
        stmt.insert(1 if stmt.find('CURDEF') is not None else 0, externos[0])
        alteracoes.append('Conta única realocada para o demonstrativo')
    for response in root.findall('./BANKMSGSRSV1/STMTTRNRS'):
        ids = response.findall('TRNUID')
        if len(ids) == 1 and list(response).index(ids[0]) != 0:
            response.remove(ids[0]); response.insert(0, ids[0])
            alteracoes.append('Ordem de metadado TRNUID corrigida')
    for tx in root.iter('STMTTRN'):
        kind = tx.find('TRNTYPE')
        if kind is None or kind.text not in ('IN', 'OUT'):
            continue
        try:
            value = Decimal(tx.findtext('TRNAMT'))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise OFXCompatError('OFX inválido: tipo IN/OUT sem valor financeiro válido') from exc
        if not value.is_finite() or (kind.text == 'IN' and value <= 0) or (kind.text == 'OUT' and value >= 0):
            raise OFXCompatError('Conflito financeiro: tipo IN/OUT incompatível com o sinal do valor')
        kind.text = 'CREDIT' if kind.text == 'IN' else 'DEBIT'
        alteracoes.append('Tipo IN/OUT convertido com verificação de sinal')
    return tuple(dict.fromkeys(alteracoes))
