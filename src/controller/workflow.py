"""Planejamento e execução de uma importação OFX validada."""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import hashlib
import os
import shutil
from . import safe_storage
from .ofx_names import validar_nome_limpo

from .organization import ANEXOS, OrganizacaoError, caminho_direto, link_inseguro, pasta_dia, proxima_importacao, localizar_historico

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
              getattr(disponivel, 'balamt', None), getattr(disponivel, 'dtasof', None))
    return (conta, saldos, tuple((t.fitid, t.dtposted, t.dtposted.utcoffset(), t.trnamt,
                          t.trntype, t.memo, t.checknum) for t in transacoes))


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
    if original.suffix.casefold() != '.ofx' or any(p.suffix.casefold() not in ANEXOS for p in anexos):
        raise OrganizacaoError('Tipo de extrato ou anexo não permitido')
    if any(p.stat().st_nlink > 1 for p in arquivos):
        raise OrganizacaoError('Arquivos com múltiplos links físicos não são suportados')
    hashes = {p: _hash(p) for p in arquivos}
    leitor = leitor or carregar_ofx
    _, atual = leitor(original)
    historico = localizar_historico(banco, hoje)
    if historico and historico.stat().st_nlink > 1:
        raise OrganizacaoError('Histórico com múltiplos links físicos não é suportado')
    antes = _hash(historico) if historico else None
    anterior = leitor(historico)[1] if historico else None
    if historico and _hash(historico) != antes:
        raise OrganizacaoError('Histórico alterado durante a leitura')
    resultado = analisar(atual, anterior)
    if resultado.relatorio.estado == 'BLOQUEADO':
        raise OrganizacaoError(resultado.relatorio.motivo)
    filtrado = resultado.modelo_filtrado(atual)
    assinatura_limpo = _assinatura(filtrado)
    limpo = serializar_ofx(filtrado)
    dia = pasta_dia(banco, hoje)
    destino = proxima_importacao(dia)
    geral = dia / f'OFXGeral-{hoje.isoformat()}.ofx'
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
        assinatura_geral = _assinatura(anterior)
    elif historico == geral:
        copia = interpretar_ofx('xml', serializar_ofx(anterior))
        copia.statements[0].transactions.extend(filtrado.statements[0].transactions)
        geral_bytes = serializar_ofx(copia)
        assinatura_geral = _assinatura(copia)
    else:
        geral_bytes = limpo
        assinatura_geral = assinatura_limpo
    if historico:
        hashes[historico] = antes
    return Plano(banco, original, tuple(anexos), dia, destino, geral, historico,
                 resultado, limpo, geral_bytes, hashes, assinatura_limpo, assinatura_geral, limpo_nome)


def executar(plano, *, bloqueio=None):
    """Publica dados preparados; uma interrupção deixa registro e bloqueia nova operação."""
    if bloqueio is None:
        with safe_storage.bloquear(plano.banco) as token:
            return executar(plano, bloqueio=token)
    if not safe_storage.bloqueio_valido(bloqueio, plano.banco):
        raise OrganizacaoError('Bloqueio da instituição não está ativo')
    from .ofx_functions import carregar_ofx
    safe_storage.exigir_sem_pendencias(plano.banco)
    if localizar_historico(plano.banco, date.fromisoformat(plano.dia.name)) != plano.historico:
        raise OrganizacaoError('Histórico mudou desde o planejamento')
    for p, digest in plano.hashes.items():
        if link_inseguro(p) or p.stat().st_nlink != 1 or _hash(p) != digest:
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
        if _assinatura(carregar_ofx(temp_geral)[1]) != plano.assinatura_geral:
            raise OrganizacaoError('Falha na validação do Geral preparado')
    manifest['estado'] = 'PREPARADO'
    safe_storage.atualizar_manifesto(op, manifest)
    # Revalidar logo antes de publicar: não confiar na verificação inicial.
    for p, digest in plano.hashes.items():
        if link_inseguro(p) or p.stat().st_nlink != 1 or _hash(p) != digest:
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
        arquivo = plano.importacao / origem.name
        if (link_inseguro(origem) or link_inseguro(arquivo)
                or origem.stat().st_nlink != 1 or link_inseguro(plano.geral)
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
