"""Planejamento e execução de uma importação OFX validada."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
import os
import shutil

from .organization import ANEXOS, OrganizacaoError, link_inseguro, pasta_dia, proxima_importacao, localizar_historico

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


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.digest()


def planejar(raiz, banco, original, anexos=(), hoje=None, leitor=None):
    from .ofx_functions import carregar_ofx
    from .ofx_comparison import analisar
    from .ofx_io import serializar_ofx, interpretar_ofx
    raiz = Path(raiz).resolve(strict=True)
    banco, original = Path(banco), Path(original)
    hoje = hoje or date.today()
    if link_inseguro(banco) or banco.parent != raiz or not banco.is_dir():
        raise OrganizacaoError('Instituição deve ser uma pasta real diretamente na raiz')
    arquivos = (original, *anexos)
    if any(p.parent != raiz or link_inseguro(p) or not p.is_file() for p in arquivos):
        raise OrganizacaoError('Originais e anexos devem ser arquivos regulares na raiz')
    if original.suffix.casefold() != '.ofx' or any(p.suffix.casefold() not in ANEXOS for p in anexos):
        raise OrganizacaoError('Tipo de extrato ou anexo não permitido')
    if any(p.stat().st_nlink > 1 for p in arquivos):
        raise OrganizacaoError('Arquivos com múltiplos links físicos não são suportados')
    names = [p.name.casefold() for p in arquivos] + ['ofx limpo.ofx']
    if len(set(names)) != len(names):
        raise OrganizacaoError('Colisão entre nomes de arquivos de destino')
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
    elif historico == geral:
        copia = interpretar_ofx('xml', serializar_ofx(anterior))
        copia.statements[0].transactions.extend(filtrado.statements[0].transactions)
        geral_bytes = serializar_ofx(copia)
    else:
        geral_bytes = limpo
    if historico:
        hashes[historico] = antes
    return Plano(banco, original, tuple(anexos), dia, destino, geral, historico,
                 resultado, limpo, geral_bytes, hashes)


def executar(plano):
    """Grava saídas, copia e verifica originais, então remove cópias da raiz.

    Não é transacional: falhas podem deixar saídas parciais. Etapa 4 tratará
    substituição atômica, concorrência e recuperação.
    """
    for p, digest in plano.hashes.items():
        if link_inseguro(p) or _hash(p) != digest:
            raise OrganizacaoError('Arquivo alterado após validação: ' + p.name)
    # Recusar qualquer link em componentes de saída, inclusive se introduzido.
    for path in (plano.dia, *plano.dia.parents):
        if path == plano.banco.parent:
            break
        if link_inseguro(path):
            raise OrganizacaoError('Caminho de saída contém link simbólico')
    plano.dia.mkdir(parents=True, exist_ok=True)
    plano.importacao.mkdir(exist_ok=False)
    with (plano.importacao / 'OFX Limpo.ofx').open('xb') as f:
        f.write(plano.limpo)
    for origem in (plano.original, *plano.anexos):
        destino = plano.importacao / origem.name
        with origem.open('rb') as src, destino.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        if _hash(destino) != plano.hashes[origem] or _hash(origem) != plano.hashes[origem]:
            raise OrganizacaoError('Falha na verificação da cópia: ' + origem.name)
    if plano.geral_bytes is not None:
        modo = 'wb' if plano.historico == plano.geral else 'xb'
        with plano.geral.open(modo) as f:
            f.write(plano.geral_bytes)
    for origem in (plano.original, *plano.anexos):
        origem.unlink()
    return plano.importacao
