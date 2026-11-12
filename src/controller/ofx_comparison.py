"""Comparação incremental de extratos: análise sem modificar os modelos."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Optional

ZERO = Decimal('0')


@dataclass(frozen=True)
class Conta:
    banco: str
    conta: str
    tipo: str
    moeda: str
    instituicao: Optional[str] = None
    fid: Optional[str] = None

    def mascarada(self):
        return f'{self.banco} / ***{self.conta[-4:]} / {self.tipo} / {self.moeda}'


@dataclass(frozen=True)
class Totais:
    quantidade: int = 0
    creditos: Decimal = ZERO
    debitos: Decimal = ZERO
    liquido: Decimal = ZERO


@dataclass
class Relatorio:
    estado: str = 'BLOQUEADO'
    conta: Optional[Conta] = None
    referencia: object = None
    original: Totais = field(default_factory=Totais)
    anteriores: Totais = field(default_factory=Totais)
    duplicatas: Totais = field(default_factory=Totais)
    novas_intersecao: Totais = field(default_factory=Totais)
    posteriores: Totais = field(default_factory=Totais)
    novas: Totais = field(default_factory=Totais)
    conflitos: list = field(default_factory=list)
    divergencias_memo: list = field(default_factory=list)
    motivo: str = ''


@dataclass
class Resultado:
    relatorio: Relatorio
    indices_novos: tuple = ()

    def modelo_filtrado(self, atual):
        if self.relatorio.estado == 'BLOQUEADO':
            raise ValueError('Processamento bloqueado: ' + self.relatorio.motivo)
        # Uma única cópia independente, inclusive das transações selecionadas.
        from .ofx_io import interpretar_ofx, serializar_ofx
        copia = interpretar_ofx("xml", serializar_ofx(atual))
        if hasattr(atual, "_caminho_origem"):
            copia._caminho_origem = atual._caminho_origem
        lista = copia.statements[0].transactions
        lista[:] = [lista[i] for i in self.indices_novos]
        return copia


def identificar_conta(ofx):
    demonstrativos = ofx.statements
    if len(demonstrativos) != 1:
        raise ValueError('É necessário exatamente um demonstrativo por arquivo')
    statement = demonstrativos[0]
    conta = getattr(statement, 'bankacctfrom', None)
    if conta is None:
        raise ValueError('Identificação de conta bancária ausente ou não suportada')
    dados = [getattr(conta, x, None) for x in ('bankid', 'acctid', 'accttype')]
    dados.append(getattr(statement, 'curdef', None))
    if any(not isinstance(x, str) or not x.strip() for x in dados):
        raise ValueError('BANKID, ACCTID, ACCTTYPE e CURDEF são obrigatórios')
    signon = getattr(ofx, 'signonmsgsrsv1', None)
    sonrs = getattr(signon, 'sonrs', None)
    fi = getattr(sonrs, 'fi', None)
    return Conta(*dados, getattr(fi, 'org', None), getattr(fi, 'fid', None))


def _validar_transacoes(lista, nome):
    ids = {}
    maior_ordem = None
    menor_expoente = None
    for transacao in lista:
        fitid = getattr(transacao, 'fitid', None)
        dt = getattr(transacao, 'dtposted', None)
        amount = getattr(transacao, 'trnamt', None)
        kind = getattr(transacao, 'trntype', None)
        if not isinstance(fitid, str) or not fitid.strip():
            raise ValueError(f'{nome}: FITID ausente')
        if fitid in ids:
            raise ValueError(f'{nome}: FITID repetido {fitid!r}')
        if not isinstance(dt, datetime) or dt.utcoffset() is None:
            raise ValueError(f'{nome}: data ausente ou sem fuso verificável')
        if not isinstance(amount, Decimal) or not amount.is_finite() or not kind:
            raise ValueError(f'{nome}: valor Decimal finito e tipo são obrigatórios')
        if amount:
            ordem, expoente = amount.adjusted(), amount.as_tuple().exponent
            maior_ordem = ordem if maior_ordem is None else max(maior_ordem, ordem)
            menor_expoente = expoente if menor_expoente is None else min(menor_expoente, expoente)
        ids[fitid] = transacao
    # Não permitir que a precisão corrente arredonde qualquer soma de categorias.
    if maior_ordem is not None:
        precisao = maior_ordem - menor_expoente + 1 + len(str(len(lista)))
        contexto = getcontext()
        if (precisao > contexto.prec or menor_expoente < contexto.Emin
                or maior_ordem + len(str(len(lista))) > contexto.Emax):
            raise ValueError(f'{nome}: contexto Decimal insuficiente para somas exatas')
    return ids


def _totais(transacoes):
    positivos = ZERO
    negativos = ZERO
    n = 0
    for t in transacoes:
        n += 1
        valor = t.trnamt
        if valor > ZERO:
            positivos += valor
        elif valor < ZERO:
            negativos += valor
    return Totais(n, positivos, negativos, positivos + negativos)


def analisar(atual, anterior=None):
    """Retorna Resultado. Não altera nenhum modelo nem efetua escrita."""
    r = Relatorio()
    try:
        r.conta = identificar_conta(atual)
        transacoes = atual.statements[0].transactions
        atuais = _validar_transacoes(transacoes, 'Extrato atual')
        r.original = _totais(transacoes)
        if anterior is None:
            r.novas = r.original
            r.estado = 'PRIMEIRA_IMPORTACAO'
            return Resultado(r, tuple(range(len(transacoes))))
        conta_anterior = identificar_conta(anterior)
        if (r.conta.banco, r.conta.conta, r.conta.tipo, r.conta.moeda) != (conta_anterior.banco, conta_anterior.conta, conta_anterior.tipo, conta_anterior.moeda):
            raise ValueError('Banco, conta, tipo ou moeda incompatível')
        for attr in ('instituicao', 'fid'):
            a, b = getattr(r.conta, attr), getattr(conta_anterior, attr)
            if a and b and a != b:
                raise ValueError('Instituições incompatíveis')
        antigas = anterior.statements[0].transactions
        historico = _validar_transacoes(antigas, 'Histórico')
        if not antigas:
            r.novas = r.original
            r.estado = 'APROVADO' if transacoes else 'SEM_NOVIDADES'
            return Resultado(r, tuple(range(len(transacoes))))
        if not transacoes:
            r.estado = 'SEM_NOVIDADES'
            return Resultado(r)
        referencia = max(t.dtposted.date() for t in antigas)
        r.referencia = referencia
        ids_referencia = {t.fitid for t in antigas if t.dtposted.date() == referencia}
        dias = [t.dtposted.date() for t in transacoes]
        if referencia not in dias:
            raise ValueError('Sem última data do histórico no extrato atual; cronologia ou cobertura não comprovada')
        faltantes = ids_referencia - atuais.keys()
        if faltantes:
            raise ValueError(f'Histórico da data de referência não está integralmente presente ({len(faltantes)} FITIDs ausentes)')
        # Conflitos por ID são verificados também fora da data de referência;
        # nenhuma busca quadrática ou comparação individual por memo é feita.
        for fitid, t in atuais.items():
            old = historico.get(fitid)
            if old is None:
                continue
            mesma_data = t.dtposted.date() == old.dtposted.date() or t.dtposted == old.dtposted
            if (not mesma_data or t.trnamt != old.trnamt or t.trntype != old.trntype
                    or getattr(t, 'checknum', None) != getattr(old, 'checknum', None)):
                r.conflitos.append(f'FITID {fitid!r}: data, valor, tipo ou número de cheque incompatível')
            elif t.memo != old.memo:
                r.divergencias_memo.append(f'FITID {fitid!r}: descrição diferente')
        if r.conflitos:
            raise ValueError('Conflitos de identidade encontrados')
        anteriores, duplicatas, novas_ref, posteriores = [], [], [], []
        indices = []
        for i, (t, dia) in enumerate(zip(transacoes, dias)):
            if dia < referencia:
                anteriores.append(t)
            elif t.fitid in historico:
                duplicatas.append(t)
            elif dia == referencia:
                novas_ref.append(t); indices.append(i)
            else:
                posteriores.append(t); indices.append(i)
        # Um ID do dia de referência com dia local anterior é inseguro para corte.
        if any(t.fitid in ids_referencia for t in anteriores):
            raise ValueError('FITID de referência aparece antes da data local de corte')
        r.anteriores = _totais(anteriores)
        r.duplicatas = _totais(duplicatas)
        r.novas_intersecao = _totais(novas_ref)
        r.posteriores = _totais(posteriores)
        r.novas = _totais(novas_ref + posteriores)
        for nome in ('quantidade', 'creditos', 'debitos', 'liquido'):
            if getattr(r.original, nome) != sum((getattr(x, nome) for x in (r.anteriores, r.duplicatas, r.novas)), 0):
                raise ValueError('Falha de conservação: ' + nome)
        r.estado = 'APROVADO' if indices else 'SEM_NOVIDADES'
        return Resultado(r, tuple(indices))
    except (ValueError, AttributeError, TypeError, IndexError, KeyError, ArithmeticError) as err:
        r.estado = 'BLOQUEADO'; r.motivo = str(err)
        return Resultado(r)
