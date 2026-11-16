"""Conversão em memória de relatório CSV de vendas Rede para modelo OFX validável.

Baseado no notebook fornecido pelo usuário: somente vendas aprovadas, valor
líquido, FITID 'NSU/CV - HORA', NAME e MEMO conforme o relatório da Rede.
A conversão não cria nem modifica arquivos; workflow gerencia a publicação.
"""
import csv
import io
import re
import unicodedata
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET

from .ofx_io import interpretar_ofx

BANKID = '000'
BRANCHID = '0000'
ACCTID = 'VENDAS_REDE'
ACCTTYPE = 'CHECKING'
CURDEF = 'BRL'
FUSO = '[-3:BRT]'  # Relatório Rede sem fuso; política explícita para vendas no Brasil.
CAMPOS = (
    'status da venda', 'data da venda', 'hora da venda', 'valor líquido',
    'nsu/cv', 'código da maquininha', 'meio de pagamento', 'bandeira',
    'modalidade', 'tipo', 'número de parcelas',
)
CONTROLES_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def normalizar(texto):
    texto = ' '.join(str(texto or '').strip().split()).casefold()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto)
                   if not unicodedata.combining(c))


def _texto_seguro(valor, numero):
    if CONTROLES_XML.search(valor):
        raise ValueError(f'Linha {numero}: caractere de controle inválido')
    return valor


def _ler(arquivo):
    raw = Path(arquivo).read_bytes()
    try:
        conteudo = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            conteudo = raw.decode('cp1252')
        except UnicodeDecodeError as exc:
            raise ValueError('CSV Rede: codificação não suportada (UTF-8 ou Windows-1252)') from exc
    if not conteudo.strip():
        raise ValueError('CSV Rede vazio')
    # Examine apenas a primeira linha; vírgulas decimais não são delimitadores.
    cabecalho = conteudo.splitlines()[0]
    esperado = {normalizar(c) for c in CAMPOS}
    escolhas = []
    for delimitador in (';', ',', '\t'):
        nomes = [normalizar(c.lstrip('\ufeff')) for c in
                 next(csv.reader([cabecalho], delimiter=delimitador))]
        escolhas.append((len(esperado.intersection(nomes)), delimitador, nomes))
    pontuacao, delimitador, nomes = max(escolhas, key=lambda item: item[0])
    if pontuacao != len(esperado) or len(nomes) != len(set(nomes)):
        raise ValueError('CSV Rede: cabeçalho obrigatório ausente, duplicado ou incompatível')
    reader = csv.DictReader(io.StringIO(conteudo, newline=''), delimiter=delimitador, strict=True)
    registros = []
    for n, valores in enumerate(reader, 2):
        if None in valores or any(v is None for v in valores.values()):
            raise ValueError(f'Linha {n}: número de colunas diferente do cabeçalho')
        if not any((v or '').strip() for v in valores.values() if isinstance(v, str)):
            continue
        linha = {normalizar(k): _texto_seguro(v.strip(), n) for k, v in valores.items()}
        linha['_numero_linha'] = n
        registros.append(linha)
    return registros


def _obrigatorio(linha, coluna):
    valor = linha.get(normalizar(coluna), '').strip()
    if not valor:
        raise ValueError(f"Linha {linha['_numero_linha']}: campo obrigatório vazio: {coluna}")
    return valor


def _valor(valor, numero):
    s = valor.replace('R$', '').replace(' ', '').strip()
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+,\d{1,2}|\d+,\d{1,2}', s):
        s = s.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d+', s):
        pass
    else:
        raise ValueError(f'Linha {numero}: valor líquido brasileiro inválido: {valor!r}')
    try:
        v = Decimal(s)
        if not v.is_finite() or v <= 0 or v != v.quantize(Decimal('0.01')):
            raise ValueError
        return v
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Linha {numero}: valor líquido inválido: {valor!r}') from exc


def _data(valor, numero):
    for formato in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    raise ValueError(f'Linha {numero}: data da venda inválida: {valor!r}')


def _hora(valor, numero):
    for formato in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(valor, formato).time()
        except ValueError:
            pass
    raise ValueError(f'Linha {numero}: hora da venda inválida: {valor!r}')


def _nome(valor, mapa, tipo='title'):
    s = str(valor).strip()
    chave = normalizar(s)
    if chave in mapa:
        return mapa[chave]
    return s.title() if tipo == 'title' else s[:1].upper() + s[1:].lower()


def _parcelas(valor, n):
    try:
        d = Decimal(valor.replace(',', '.'))
        if not d.is_finite() or d <= 0 or d != d.to_integral_value():
            raise ValueError
        return f'{int(d)}x'
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Linha {n}: número de parcelas inválido: {valor!r}') from exc


def preparar_transacoes(linhas):
    bandeiras = {'visa': 'Visa', 'mastercard': 'Mastercard', 'elo': 'Elo',
                 'amex': 'Amex', 'american express': 'American Express',
                 'hipercard': 'Hipercard'}
    modalidades = {'credito': 'Crédito', 'debito': 'Débito', 'voucher': 'Voucher', 'pix': 'Pix'}
    tipos = {'a vista': 'À vista', 'parcelado com juros': 'Parcelado Com Juros',
             'parcelado sem juros': 'Parcelado Sem Juros'}
    meios = {'maquininha': 'Maquininha', 'link de pagamento': 'Link de pagamento', 'pix': 'Pix'}
    transacoes = []
    vistos = set()
    for linha in linhas:
        if not normalizar(_obrigatorio(linha, 'status da venda')).startswith('aprovad'):
            continue
        n = linha['_numero_linha']
        data = _data(_obrigatorio(linha, 'data da venda'), n)
        hora_texto = _obrigatorio(linha, 'hora da venda')
        hora = _hora(hora_texto, n)
        valor = _valor(_obrigatorio(linha, 'valor líquido'), n)
        nsu = _obrigatorio(linha, 'NSU/CV')
        codigo = _obrigatorio(linha, 'código da maquininha')
        meio = _nome(_obrigatorio(linha, 'meio de pagamento'), meios, 'sentence')
        bandeira = _nome(_obrigatorio(linha, 'bandeira'), bandeiras)
        modalidade = _nome(_obrigatorio(linha, 'modalidade'), modalidades, 'sentence')
        tipo = _nome(_obrigatorio(linha, 'tipo'), tipos)
        pre = normalizar(linha.get(normalizar('pré-autorizado'), ''))
        if pre in {'sim', 's', 'yes', 'y', 'true', '1', 'pre-auto', 'pre auto'}:
            tipo += ' Pre-Auto'
        parcelas = _parcelas(_obrigatorio(linha, 'número de parcelas'), n)
        fitid = f'{nsu} - {hora_texto}'  # Compatibilidade com histórico do notebook legado.
        if fitid in vistos:
            raise ValueError(f'Linha {n}: FITID Rede duplicado: {fitid!r}')
        vistos.add(fitid)
        transacoes.append({
            'data': data, 'hora': hora, 'fitid': fitid, 'valor': valor,
            'name': f'{codigo} - {meio}',
            'memo': f'{bandeira} - {modalidade} - {tipo} - {parcelas}',
        })
    if not transacoes:
        raise ValueError('CSV Rede: nenhuma venda aprovada encontrada')
    transacoes.sort(key=lambda x: (x['data'], x['hora']))
    return transacoes


def _sub(parent, nome, valor=None):
    el = ET.SubElement(parent, nome)
    if valor is not None:
        el.text = str(valor)
    return el


def montar_modelo(transacoes):
    """Gera árvore OFX XML em memória e usa o mesmo ofxtools que os demais bancos."""
    root = ET.Element('OFX')
    signon = _sub(root, 'SIGNONMSGSRSV1')
    sonrs = _sub(signon, 'SONRS')
    status = _sub(sonrs, 'STATUS')
    _sub(status, 'CODE', '0')
    _sub(status, 'SEVERITY', 'INFO')
    _sub(sonrs, 'DTSERVER', datetime.now().strftime('%Y%m%d%H%M%S') + FUSO)
    _sub(sonrs, 'LANGUAGE', 'POR')
    fi = _sub(sonrs, 'FI')
    _sub(fi, 'ORG', 'REDE')
    _sub(fi, 'FID', 'REDE')
    bank = _sub(root, 'BANKMSGSRSV1')
    response = _sub(bank, 'STMTTRNRS')
    _sub(response, 'TRNUID', uuid.uuid4().hex)
    status = _sub(response, 'STATUS')
    _sub(status, 'CODE', '0')
    _sub(status, 'SEVERITY', 'INFO')
    stmt = _sub(response, 'STMTRS')
    _sub(stmt, 'CURDEF', CURDEF)
    acct = _sub(stmt, 'BANKACCTFROM')
    for tag, value in (('BANKID', BANKID), ('BRANCHID', BRANCHID),
                       ('ACCTID', ACCTID), ('ACCTTYPE', ACCTTYPE)):
        _sub(acct, tag, value)
    txlist = _sub(stmt, 'BANKTRANLIST')
    _sub(txlist, 'DTSTART', transacoes[0]['data'].strftime('%Y%m%d'))
    _sub(txlist, 'DTEND', transacoes[-1]['data'].strftime('%Y%m%d'))
    for item in transacoes:
        tx = _sub(txlist, 'STMTTRN')
        _sub(tx, 'TRNTYPE', 'CREDIT')
        # Data civil, sem hora/fuso, idêntica ao notebook e aos históricos legados.
        stamp = item['data'].strftime('%Y%m%d')
        _sub(tx, 'DTPOSTED', stamp)
        _sub(tx, 'TRNAMT', f"{item['valor']:.2f}")
        _sub(tx, 'FITID', item['fitid'])
        _sub(tx, 'NAME', item['name'])
        _sub(tx, 'MEMO', item['memo'])
    saldo = _sub(stmt, 'LEDGERBAL')
    # Igual ao conversor original: soma de vendas líquidas, NÃO saldo bancário.
    _sub(saldo, 'BALAMT', f"{sum((x['valor'] for x in transacoes), Decimal('0')):.2f}")
    _sub(saldo, 'DTASOF', transacoes[-1]['data'].strftime('%Y%m%d'))
    return interpretar_ofx('xml', ET.tostring(root, encoding='utf-8'))


def carregar_csv_rede(arquivo):
    """Contrato equivalente a carregar_ofx: (cabeçalho, modelo), sem escrita."""
    try:
        registros = _ler(arquivo)
    except csv.Error as exc:
        raise ValueError('CSV Rede malformado: ' + str(exc)) from exc
    transacoes = preparar_transacoes(registros)
    modelo = montar_modelo(transacoes)
    coluna = normalizar('número do estabelecimento')
    if any(coluna in r for r in registros):
        estabelecimentos = {_obrigatorio(r, coluna) for r in registros}
        if len(estabelecimentos) != 1:
            raise ValueError('CSV Rede mistura estabelecimentos; separe os relatórios')
        estabelecimento = estabelecimentos.pop()
        if not re.fullmatch(r'[0-9]{1,22}', estabelecimento):
            raise ValueError('Número do estabelecimento Rede inválido')
        modelo.statements[0].bankacctfrom.acctkey = estabelecimento
    return 'CSV Rede convertido em memória', modelo


def analisar_lotes(atual, anterior=None, estabelecimento_legado=None):
    """Lotes independentes, sem alegação de cobertura entre arquivos.

    Retém todo o acumulador; datas anteriores inéditas e IDs ambíguos bloqueiam.
    A identidade adicional é o número real do estabelecimento, nunca inventado.
    """
    from .ofx_comparison import (analisar, identificar_conta, _validar_transacoes,
                                 _totais, Resultado, Relatorio)
    r = Relatorio()
    try:
        r.conta = identificar_conta(atual)
        esperada = (BANKID, ACCTID, ACCTTYPE, CURDEF)
        for modelo in (atual, anterior):
            if modelo is None:
                continue
            c = identificar_conta(modelo)
            if (c.banco, c.conta, c.tipo, c.moeda) != esperada:
                raise ValueError('Histórico incompatível com a identidade Rede')
            if c.instituicao not in (None, 'REDE') or c.fid not in (None, 'REDE'):
                raise ValueError('Instituição incompatível com Rede')
        tx = atual.statements[0].transactions
        _validar_transacoes(tx, 'CSV Rede')
        if anterior is None:
            return analisar(atual)
        key = atual.statements[0].bankacctfrom.acctkey
        oldkey = anterior.statements[0].bankacctfrom.acctkey
        if key != oldkey and not (oldkey is None and key and key == estabelecimento_legado):
            raise ValueError('Estabelecimento não comprovado: configure .rede.json para vincular histórico legado ou separe os ambientes')
        antigas = anterior.statements[0].transactions
        ids = _validar_transacoes(antigas, 'Histórico Rede')
        r.original = _totais(tx)
        r.referencia = max((t.dtposted.date() for t in antigas), default=None)
        indices = []
        duplicatas = []
        for i, t in enumerate(tx):
            old = ids.get(t.fitid)
            if old is not None:
                if (t.dtposted.date(), t.trnamt, t.trntype, t.checknum) != (old.dtposted.date(), old.trnamt, old.trntype, old.checknum):
                    raise ValueError('Conflito de FITID Rede: data, valor ou tipo incompatível')
                duplicatas.append(t)
                if t.memo != old.memo or t.name != old.name:
                    r.divergencias_memo.append(f'FITID {t.fitid!r}: descrição diferente')
            else:
                if r.referencia and t.dtposted.date() < r.referencia:
                    raise ValueError('Venda inédita anterior ao histórico Rede; exige conciliação manual')
                indices.append(i)
        r.duplicatas = _totais(duplicatas)
        r.novas = _totais([tx[i] for i in indices])
        r.estado = 'APROVADO' if indices else 'SEM_NOVIDADES'
        return Resultado(r, tuple(indices))
    except (ValueError, AttributeError, TypeError, ArithmeticError) as exc:
        r.motivo = str(exc)
        return Resultado(r)


def consolidar_historicos(modelos, estabelecimento_legado=None):
    """Une snapshots Rede antigos em memória; nunca reescreve os arquivos lidos."""
    from .ofx_comparison import _validar_transacoes
    from .ofx_io import serializar_ofx
    if not modelos:
        return None
    copia = interpretar_ofx('xml', serializar_ofx(modelos[-1]))
    ids = {}
    chave = copia.statements[0].bankacctfrom.acctkey
    for modelo in modelos:
        validacao = analisar_lotes(modelo)
        if validacao.relatorio.estado == 'BLOQUEADO':
            raise ValueError(validacao.relatorio.motivo)
        outra = modelo.statements[0].bankacctfrom.acctkey
        if outra != chave and not (outra is None and chave == estabelecimento_legado):
            raise ValueError('Snapshots Rede com estabelecimentos incompatíveis')
        for t in modelo.statements[0].transactions:
            old = ids.get(t.fitid)
            if old and (old.dtposted.date(), old.trnamt, old.trntype, old.checknum) != (t.dtposted.date(), t.trnamt, t.trntype, t.checknum):
                raise ValueError('Snapshots Rede contêm FITID conflitante')
            ids[t.fitid] = t
    stmt = copia.statements[0]
    stmt.transactions[:] = sorted(ids.values(), key=lambda t: t.dtposted.date())
    _validar_transacoes(stmt.transactions, 'Snapshots Rede')
    if stmt.transactions:
        stmt.banktranlist.dtstart = min(t.dtposted for t in stmt.transactions)
        stmt.banktranlist.dtend = max(t.dtposted for t in stmt.transactions)
        stmt.ledgerbal.dtasof = stmt.banktranlist.dtend
    stmt.ledgerbal.balamt = sum((t.trnamt for t in stmt.transactions), Decimal('0'))
    return copia
