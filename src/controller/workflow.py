"""Planejamento e execução de uma importação OFX validada."""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import hashlib
import os
import shutil
from . import safe_storage
from .storage_capabilities import links_seguros
from .ofx_names import validar_nome_limpo

from .organization import ANEXOS, OrganizacaoError, caminho_direto, link_inseguro, pasta_dia, proxima_importacao, localizar_historico, historicos_validos, validar_historico_relativo, extrato_permitido

@dataclass
class Plano:
    banco: Path
    original: Path
    anexos: tuple
    dia: Path
    importacao: Path
    geral: Path
    historico: Path | None
    resultado: object
    limpo: bytes
    geral_bytes: bytes | None
    hashes: dict
    assinatura_limpo: object
    assinatura_geral: object
    limpo_nome: str


def _assinatura(modelo):
    from .ofx_comparison import identificar_conta
    conta = identificar_conta(modelo)
    statement = modelo.statements[0]
    transacoes = statement.transactions
    periodo = getattr(statement, 'banktranlist', None)
    ledger = getattr(statement, 'ledgerbal', None)
    disponivel = getattr(statement, 'availbal', None)
    saldos = (getattr(periodo, 'dtstart', None), getattr(periodo, 'dtend', None),
              getattr(ledger, 'balamt', None), getattr(ledger, 'dtasof', None),
              getattr(disponivel, 'balamt', None), getattr(disponivel, 'dtasof', None),
              getattr(statement.bankacctfrom, 'acctkey', None))
    return (conta, saldos, tuple((t.fitid, t.dtposted, t.dtposted.utcoffset(), t.trnamt,
                          t.trntype, t.memo, t.checknum, t.name) for t in transacoes))


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.digest()


def planejar(raiz, banco, original, anexos=(), hoje=None, leitor=None, relogio=None):
    from .ofx_functions import carregar_ofx
    from .ofx_comparison import analisar
    from .ofx_io import serializar_ofx, interpretar_ofx
    raiz = Path(raiz).resolve(strict=True)
    banco = caminho_direto(raiz, banco)
    original = caminho_direto(raiz, original)
    anexos = tuple(caminho_direto(raiz, p) for p in anexos)
    hoje = hoje or date.today()
    instante = (relogio or datetime.now)()
    limpo_nome = validar_nome_limpo('OFX Limpo-' + instante.strftime('%d%m%Y%H%M') + '.ofx')
    if not banco.is_dir():
        raise OrganizacaoError('Instituição deve ser uma pasta real diretamente na raiz')
    safe_storage.exigir_sem_pendencias(banco)
    arquivos = (original, *anexos)
    if any(not p.is_file() for p in arquivos):
        raise OrganizacaoError('Originais e anexos devem ser arquivos regulares na raiz')
    names = [p.name.casefold() for p in arquivos] + [limpo_nome.casefold()]
    if len(set(names)) != len(names):
        raise OrganizacaoError('Colisão entre nomes de arquivos de destino')
    from .organization import csv_bancario_identificado
    if not extrato_permitido(banco, original) or any(p.suffix.casefold() not in ANEXOS or csv_bancario_identificado(p) for p in anexos):
        raise OrganizacaoError('Tipo de extrato ou anexo não permitido')
    if any(not links_seguros(p) for p in arquivos):
        raise OrganizacaoError('Arquivos com múltiplos links físicos não são suportados')
    hashes = {p: _hash(p) for p in arquivos}
    leitor = leitor or carregar_ofx
    formato_csv = None
    if original.suffix.casefold() == '.csv':
        from .csv_formats import identificar_csv, carregar_csv
        formato_csv = identificar_csv(original)
        _, atual = carregar_csv(original, formato_csv)
    else:
        _, atual = leitor(original)
    snapshots = historicos_validos(banco, hoje) if formato_csv else []
    if formato_csv:
        historico = snapshots[-1][1] if snapshots else None
    else:
        historico = localizar_historico(banco, hoje)
    if historico and not links_seguros(historico):
        raise OrganizacaoError('Histórico com múltiplos links físicos não é suportado')
    antes = _hash(historico) if historico else None
    if formato_csv == 'valori':
        from .valori_csv import carregar_historico
        ler_historico = carregar_historico
    else:
        ler_historico = leitor
    anterior = ler_historico(historico)[1] if historico else None
    if historico and _hash(historico) != antes:
        raise OrganizacaoError('Histórico alterado durante a leitura')
    if formato_csv == 'rede':
        import json
        from .rede_csv import analisar_lotes
        config = banco / '.rede.json'
        estabelecimento = None
        if config.exists() or link_inseguro(config):
            if link_inseguro(config) or link_inseguro(config.parent) or not links_seguros(config):
                raise OrganizacaoError('Configuração Rede insegura')
            hashes[config] = _hash(config)
            try:
                estabelecimento = json.loads(config.read_text(encoding='utf-8'))['estabelecimento']
                if not isinstance(estabelecimento, str) or not estabelecimento:
                    raise ValueError('Estabelecimento deve ser texto não vazio')
            except (ValueError, KeyError, TypeError) as exc:
                raise OrganizacaoError('Configuração .rede.json inválida') from exc
            if atual.statements[0].bankacctfrom.acctkey != estabelecimento:
                raise OrganizacaoError('CSV não pertence ao estabelecimento configurado')
        if historico:
            from .rede_csv import consolidar_historicos
            modelos = []
            for _, snapshot in snapshots:
                if not links_seguros(snapshot):
                    raise OrganizacaoError('Snapshot Rede com múltiplos links')
                digest = _hash(snapshot)
                modelos.append(leitor(snapshot)[1])
                if _hash(snapshot) != digest:
                    raise OrganizacaoError('Snapshot Rede alterado durante leitura')
                hashes[snapshot] = digest
            anterior = consolidar_historicos(modelos, estabelecimento)
        resultado = analisar_lotes(atual, anterior, estabelecimento)
    elif formato_csv == 'valori':
        from .valori_csv import analisar_lotes, consolidar_historicos
        modelos = []
        for _, snapshot in snapshots:
            if not links_seguros(snapshot):
                raise OrganizacaoError('Snapshot Valori com múltiplos links')
            digest = _hash(snapshot)
            modelos.append(ler_historico(snapshot)[1])
            if _hash(snapshot) != digest:
                raise OrganizacaoError('Snapshot Valori alterado durante leitura')
            hashes[snapshot] = digest
        anterior = consolidar_historicos(modelos)
        resultado = analisar_lotes(atual, anterior)
    else:
        resultado = analisar(atual, anterior)
    if resultado.relatorio.estado == 'BLOQUEADO':
        raise OrganizacaoError(resultado.relatorio.motivo)
    filtrado = resultado.modelo_filtrado(atual)
    assinatura_limpo = _assinatura(filtrado)
    limpo = serializar_ofx(filtrado)
    dia = pasta_dia(banco, hoje)
    geral = dia / f'OFXGeral-{hoje.isoformat()}.ofx'
    if historico and validar_historico_relativo(banco, historico.relative_to(banco)) == hoje:
        if formato_csv and historico != geral:
            raise OrganizacaoError('Histórico legado no mesmo dia do destino: exige conciliação antes de criar outro Geral')
        # O dia atual pode ter sido iniciado pelo legado. Use o mesmo Geral.
        geral = historico
        dia = geral.parent
    destino = proxima_importacao(dia)
    if destino.exists() or link_inseguro(destino):
        raise OrganizacaoError('Pasta de importação já existe')
    if link_inseguro(geral) or (geral.exists() and historico != geral):
        raise OrganizacaoError('Geral de destino não corresponde ao histórico validado')
    for diretorio in (raiz, banco, dia if dia.exists() else banco):
        if not os.access(diretorio, os.W_OK | os.X_OK):
            raise OrganizacaoError('Sem permissão de escrita na raiz ou no destino')
    if geral.exists() and not os.access(geral, os.W_OK):
        raise OrganizacaoError('Sem permissão de escrita no OFX Geral')
    if resultado.relatorio.estado == 'SEM_NOVIDADES':
        # Se o dia ainda não tem Geral, preserve a referência anterior.
        geral_bytes = None if historico == geral else serializar_ofx(anterior)
        if original.suffix.casefold() == '.csv' and historico == geral:
            if _assinatura(leitor(historico)[1]) != _assinatura(anterior):
                geral_bytes = serializar_ofx(anterior)
        assinatura_geral = _assinatura(anterior)
    elif historico == geral or (historico and original.suffix.casefold() == '.csv'):
        copia = interpretar_ofx('xml', serializar_ofx(anterior))
        if formato_csv == 'valori':
            # Pagamento de uma pendência substitui o mesmo FITID no acumulador.
            txs = copia.statements[0].transactions
            pos = {tx.fitid: i for i, tx in enumerate(txs)}
            for tx in filtrado.statements[0].transactions:
                if tx.fitid in pos:
                    txs[pos[tx.fitid]] = tx
                else:
                    txs.append(tx)
        else:
            copia.statements[0].transactions.extend(filtrado.statements[0].transactions)
        if original.suffix.casefold() == '.csv':
            copia.statements[0].bankacctfrom.acctkey = atual.statements[0].bankacctfrom.acctkey
            from decimal import Decimal
            from .ofx_comparison import _validar_transacoes
            statement = copia.statements[0]
            _validar_transacoes(statement.transactions, 'Acumulador CSV')
            if formato_csv == 'valori':
                from .valori_csv import _metas_sem_saldo
                estados = _metas_sem_saldo(statement.transactions)
                statement.ledgerbal.balamt = sum(
                    (t.trnamt for t in statement.transactions if estados[t.fitid] == 'P'),
                    Decimal('0'),
                )
            else:
                statement.ledgerbal.balamt = sum((t.trnamt for t in statement.transactions), Decimal('0'))
            if formato_csv == 'valori':
                statement.banktranlist.dtstart = min(t.dtposted for t in statement.transactions)
            statement.banktranlist.dtend = max(t.dtposted for t in statement.transactions)
            statement.ledgerbal.dtasof = statement.banktranlist.dtend
        geral_bytes = serializar_ofx(copia)
        assinatura_geral = _assinatura(copia)
    else:
        geral_bytes = limpo
        assinatura_geral = assinatura_limpo
    if historico:
        hashes[historico] = antes
    return Plano(banco, original, tuple(anexos), dia, destino, geral, historico,
                 resultado, limpo, geral_bytes, hashes, assinatura_limpo, assinatura_geral, limpo_nome)


def _revalidar_historico(plano):
    hoje = date.fromisoformat(plano.dia.name)
    if plano.original.suffix.casefold() == '.csv':
        snapshots = historicos_validos(plano.banco, hoje)
        esperado = set(plano.hashes) - {plano.original, *plano.anexos, plano.banco / '.rede.json'}
        if {path for _, path in snapshots} != esperado:
            raise OrganizacaoError('Snapshots CSV mudaram desde o planejamento')
    elif localizar_historico(plano.banco, hoje) != plano.historico:
        raise OrganizacaoError('Histórico mudou desde o planejamento')


def executar(plano, *, bloqueio=None):
    """Publica dados preparados; uma interrupção deixa registro e bloqueia nova operação."""
    if bloqueio is None:
        with safe_storage.bloquear(plano.banco) as token:
            return executar(plano, bloqueio=token)
    if not safe_storage.bloqueio_valido(bloqueio, plano.banco):
        raise OrganizacaoError('Bloqueio da instituição não está ativo')
    from .ofx_functions import carregar_ofx
    safe_storage.exigir_sem_pendencias(plano.banco)
    _revalidar_historico(plano)
    for p, digest in plano.hashes.items():
        if link_inseguro(p) or not links_seguros(p) or _hash(p) != digest:
            raise OrganizacaoError('Arquivo alterado após validação: ' + p.name)
    for path in (plano.dia, *plano.dia.parents):
        if path == plano.banco.parent:
            break
        if link_inseguro(path):
            raise OrganizacaoError('Caminho de saída contém link simbólico')
    if plano.importacao.exists() or link_inseguro(plano.importacao):
        raise OrganizacaoError('Pasta de importação já existe')
    if plano.historico != plano.geral and (plano.geral.exists() or link_inseguro(plano.geral)):
        raise OrganizacaoError('Geral de destino surgiu após planejamento')
    limpo_nome = validar_nome_limpo(plano.limpo_nome)
    nomes = [p.name.casefold() for p in (plano.original, *plano.anexos)] + [limpo_nome.casefold()]
    if len(nomes) != len(set(nomes)):
        raise OrganizacaoError('Colisão entre nomes de arquivos de destino')
    manifest = {
        'versao': 2, 'estado': 'PREPARANDO', 'limpo_nome': limpo_nome,
        'pasta': str(plano.importacao.relative_to(plano.banco)),
        'geral': str(plano.geral.relative_to(plano.banco)),
        'historico': str(plano.historico.relative_to(plano.banco)) if plano.historico else None,
        'historico_hash': plano.hashes[plano.historico].hex() if plano.historico else None,
        'geral_hash': hashlib.sha256(plano.geral_bytes).hexdigest() if plano.geral_bytes is not None else plano.hashes[plano.geral].hex(),
        'limpo_hash': hashlib.sha256(plano.limpo).hexdigest(),
        'arquivos': [{'nome': p.name, 'sha256': plano.hashes[p].hex()} for p in (plano.original, *plano.anexos)]
    }
    if plano.original.suffix.casefold() == '.csv':
        from .csv_formats import identificar_csv
        formato = identificar_csv(plano.original)
        manifest['formato_csv'] = formato
        campo = 'referencias_rede' if formato == 'rede' else 'referencias_csv'
        manifest[campo] = [
            {'nome': p.relative_to(plano.banco).as_posix(), 'sha256': digest.hex()}
            for p, digest in plano.hashes.items()
            if p not in (plano.original, *plano.anexos, plano.geral)
        ]
    op = safe_storage.iniciar(plano.banco, manifest)
    stage = op / 'pasta'
    stage.mkdir()
    safe_storage.escrever(stage / limpo_nome, plano.limpo)
    if _hash(stage / limpo_nome) != hashlib.sha256(plano.limpo).digest():
        raise OrganizacaoError('Falha na validação do OFX Limpo preparado')
    assinatura_lida = _assinatura(carregar_ofx(stage / limpo_nome)[1])
    if assinatura_lida != plano.assinatura_limpo:
        raise OrganizacaoError('Falha na validação do OFX Limpo preparado')
    for origem in (plano.original, *plano.anexos):
        destino = stage / origem.name
        with origem.open('rb') as src, destino.open('xb') as dst:
            shutil.copyfileobj(src, dst); dst.flush(); os.fsync(dst.fileno())
        if _hash(destino) != plano.hashes[origem] or _hash(origem) != plano.hashes[origem]:
            raise OrganizacaoError('Falha na verificação da cópia: ' + origem.name)
    safe_storage.fsync_dir(stage)
    temp_geral = op / 'geral.tmp'
    if plano.geral_bytes is not None:
        safe_storage.escrever(temp_geral, plano.geral_bytes)
        if _hash(temp_geral) != hashlib.sha256(plano.geral_bytes).digest():
            raise OrganizacaoError('Falha na validação do Geral preparado')
        # Se os bytes e a assinatura esperada são idênticos aos do Limpo já
        # relido, o hash do Geral comprova o mesmo conteúdo validado. Em todos
        # os demais casos o Geral é interpretado e conferido separadamente.
        identico = plano.geral_bytes == plano.limpo and plano.assinatura_geral == assinatura_lida
        if not identico and _assinatura(carregar_ofx(temp_geral)[1]) != plano.assinatura_geral:
            raise OrganizacaoError('Falha na validação do Geral preparado')
    manifest['estado'] = 'PREPARADO'
    safe_storage.atualizar_manifesto(op, manifest)
    # Revalidar logo antes de publicar: não confiar na verificação inicial.
    _revalidar_historico(plano)
    for p, digest in plano.hashes.items():
        if link_inseguro(p) or not links_seguros(p) or _hash(p) != digest:
            raise OrganizacaoError('Arquivo alterado antes da publicação: ' + p.name)
    if plano.historico != plano.geral and (plano.geral.exists() or link_inseguro(plano.geral)):
        raise OrganizacaoError('Geral de destino surgiu após planejamento')
    manifest['estado'] = 'PUBLICANDO'
    safe_storage.atualizar_manifesto(op, manifest)
    plano.dia.mkdir(parents=True, exist_ok=True)
    safe_storage.publicar_pasta(stage, plano.importacao)
    manifest['estado'] = 'PASTA_PUBLICADA'
    safe_storage.atualizar_manifesto(op, manifest)
    if plano.geral_bytes is not None:
        if plano.historico == plano.geral and (link_inseguro(plano.geral) or _hash(plano.geral) != plano.hashes[plano.geral]):
            raise OrganizacaoError('Histórico alterado antes da substituição')
        safe_storage.publicar_arquivo(temp_geral, plano.geral, plano.historico == plano.geral)
    if _hash(plano.geral).hex() != manifest['geral_hash']:
        raise OrganizacaoError('Geral publicado não corresponde ao esperado')
    manifest['estado'] = 'HISTORICO_ATUALIZADO'
    safe_storage.atualizar_manifesto(op, manifest)
    for origem in (plano.original, *plano.anexos):
        safe_storage._verificar_referencias(plano.banco, manifest)
        arquivo = plano.importacao / origem.name
        if (link_inseguro(origem) or link_inseguro(arquivo)
                or not links_seguros(origem) or link_inseguro(plano.geral)
                or _hash(arquivo) != plano.hashes[origem]
                or _hash(origem) != plano.hashes[origem]
                or _hash(plano.geral).hex() != manifest['geral_hash']
                or link_inseguro(plano.importacao / limpo_nome)
                or _hash(plano.importacao / limpo_nome).hex() != manifest['limpo_hash']
                or (plano.historico and plano.historico != plano.geral
                    and (link_inseguro(plano.historico) or _hash(plano.historico) != plano.hashes[plano.historico]))):
            raise OrganizacaoError('Alteração detectada antes da remoção: ' + origem.name)
        origem.unlink()
        safe_storage.fsync_dir(origem.parent)
    manifest['estado'] = 'CONCLUIDO'
    safe_storage.atualizar_manifesto(op, manifest)
    safe_storage.finalizar(op)
    return plano.importacao
