"""Bloqueio por instituição e publicação segura de arquivos preparados."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import uuid
from datetime import date

from .organization import OrganizacaoError, link_inseguro


_ativos = {}


class Bloqueio:
    def __init__(self, banco):
        self.banco = Path(banco)
        self.ativo = True


def bloqueio_valido(token, banco):
    registro = _ativos.get(id(token))
    return (isinstance(token, Bloqueio) and token.ativo and token.banco == Path(banco)
            and registro is not None and registro == (token, os.getpid(), threading.get_ident()))


@contextlib.contextmanager
def bloquear(banco):
    banco = Path(banco)
    if link_inseguro(banco) or not banco.is_dir():
        raise OrganizacaoError('Instituição inválida para bloqueio')
    locks = banco.parent / '.comparaofx-locks'
    if link_inseguro(locks):
        raise OrganizacaoError('Pasta de bloqueios insegura')
    locks.mkdir(exist_ok=True)
    lockpath = locks / (hashlib.sha256(os.fsencode(os.path.normcase(str(banco.resolve())))).hexdigest() + '.lock')
    if link_inseguro(lockpath):
        raise OrganizacaoError('Arquivo de bloqueio inseguro')
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_BINARY', 0)
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(lockpath, flags, 0o600)
    try:
        if os.fstat(fd).st_nlink != 1:
            raise OrganizacaoError('Arquivo de bloqueio com links adicionais')
        f = os.fdopen(fd, 'r+b', buffering=0)
        fd = -1
        try:
            if sys.platform == 'win32':
                import msvcrt
                if os.fstat(f.fileno()).st_size == 0:
                    f.write(b'0')
                f.seek(0)
                try: msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc: raise OrganizacaoError('Instituição já está em processamento') from exc
            else:
                import fcntl
                try: fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc: raise OrganizacaoError('Instituição já está em processamento') from exc
            try:
                token = Bloqueio(banco)
                _ativos[id(token)] = (token, os.getpid(), threading.get_ident())
                yield token
            finally:
                token.ativo = False
                _ativos.pop(id(token), None)
                if sys.platform == 'win32':
                    f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally: f.close()
    finally:
        if fd != -1: os.close(fd)


def pendencias(banco):
    base = Path(banco) / '.comparaofx'
    if link_inseguro(base):
        raise OrganizacaoError('Área de recuperação insegura')
    if not base.exists(): return []
    if not base.is_dir(): raise OrganizacaoError('Área de recuperação inválida')
    return sorted(base.iterdir())


def exigir_sem_pendencias(banco):
    if pendencias(banco):
        raise OrganizacaoError('Operação pendente em .comparaofx; preserve os arquivos e faça inspeção antes de continuar')


def recuperar_concluida(banco, *, bloqueio=None):
    """Remove somente registro inequivocamente concluído; outros estados bloqueiam.

    Adquire o bloqueio quando necessário. Não remove cópias arquivadas.
    """
    banco = Path(banco)
    if bloqueio is None:
        bloqueio = next((item[0] for item in list(_ativos.values())
                         if bloqueio_valido(item[0], banco)), None)
        if bloqueio is None:
            with bloquear(banco) as token:
                return recuperar_concluida(banco, bloqueio=token)
    if not bloqueio_valido(bloqueio, banco):
        raise OrganizacaoError('Bloqueio da instituição não está ativo')
    for op in pendencias(banco):
        if link_inseguro(op) or not op.is_dir():
            raise OrganizacaoError('Registro de recuperação inseguro')
        try:
            manifest_path = op / 'manifesto.json'
            if link_inseguro(manifest_path) or manifest_path.stat().st_size > 65536:
                raise ValueError('manifesto inválido')
            m = json.loads(manifest_path.read_text(encoding='utf-8'))
            if m['versao'] != 1 or m['estado'] not in ('PASTA_PUBLICADA', 'HISTORICO_ATUALIZADO', 'CONCLUIDO'):
                raise ValueError('operação ainda não concluída')
            if sorted(x.name for x in op.iterdir()) != ['manifesto.json']:
                raise ValueError('arquivos auxiliares pendentes')
            pasta, geral = Path(m['pasta']), Path(m['geral'])
            for path in (pasta, geral):
                if path.is_absolute() or path.drive or '..' in path.parts or len(path.parts) != 4:
                    raise ValueError('caminho inválido')
            if pasta.parent != geral.parent or not (len(pasta.name) == 3 and pasta.name.isascii() and pasta.name.isdigit() and pasta.name != '000'):
                raise ValueError('pasta de importação inválida')
            from .organization import pasta_dia
            data = date.fromisoformat(geral.parent.name)
            if pasta_dia(banco, data).relative_to(banco) != geral.parent:
                raise ValueError('hierarquia da operação inválida')
            if geral.name != f'OFXGeral-{geral.parent.name}.ofx':
                raise ValueError('nome do geral inválido')
            pasta, geral = banco / pasta, banco / geral
            for path in (pasta, geral, *pasta.parents):
                if path == banco.parent: break
                if link_inseguro(path): raise ValueError('link inseguro')
            def sha(path):
                h = hashlib.sha256()
                with path.open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
                return h.hexdigest()
            if link_inseguro(pasta / 'OFX Limpo.ofx') or sha(geral) != m['geral_hash'] or sha(pasta / 'OFX Limpo.ofx') != m['limpo_hash']:
                raise ValueError('hash de saída divergente')
            referencia = None
            if m.get('historico'):
                historico_rel = Path(m['historico'])
                if historico_rel.is_absolute() or historico_rel.drive or '..' in historico_rel.parts or len(historico_rel.parts) != 4:
                    raise ValueError('caminho do histórico inválido')
                historico_data = date.fromisoformat(historico_rel.parent.name)
                if (pasta_dia(banco, historico_data).relative_to(banco) != historico_rel.parent
                        or historico_rel.name != f'OFXGeral-{historico_data.isoformat()}.ofx'):
                    raise ValueError('hierarquia do histórico inválida')
                historico = banco / historico_rel
                if historico != geral:
                    referencia = historico
                    for path in (historico, *historico.parents):
                        if path == banco.parent: break
                        if link_inseguro(path): raise ValueError('histórico inseguro')
                    if sha(historico) != m['historico_hash']:
                        raise ValueError('histórico de referência alterado')
            arquivos = m['arquivos']
            if not isinstance(arquivos, list) or not arquivos:
                raise ValueError('lista de arquivos inválida')
            origens = []
            vistos = set()
            from .organization import ANEXOS
            for idx, item in enumerate(arquivos):
                nome = item['nome']
                if not isinstance(nome, str) or nome in ('', '.', '..') or Path(nome).name != nome or '\\' in nome:
                    raise ValueError('nome de arquivo inválido')
                if nome.casefold() in vistos or nome.casefold() == 'ofx limpo.ofx':
                    raise ValueError('nomes duplicados')
                vistos.add(nome.casefold())
                if (idx == 0 and Path(nome).suffix.casefold() != '.ofx') or (idx > 0 and Path(nome).suffix.casefold() not in ANEXOS):
                    raise ValueError('tipo de arquivo inválido')
                origem, copia = banco.parent / nome, pasta / nome
                if link_inseguro(origem) or link_inseguro(copia) or sha(copia) != item['sha256']:
                    raise ValueError('cópia divergente')
                if origem.exists():
                    if not origem.is_file() or origem.stat().st_nlink != 1 or sha(origem) != item['sha256']:
                        raise ValueError('origem divergente')
                    origens.append((origem, copia, item['sha256']))
            # Todos os dados e a ausência de alterações são verificados antes de
            # cada remoção. O manifesto persiste mesmo após uma remoção parcial.
            for origem, copia, digest in origens:
                if (link_inseguro(origem) or link_inseguro(copia)
                        or origem.stat().st_nlink != 1 or link_inseguro(geral)
                        or sha(origem) != digest or sha(copia) != digest
                        or sha(geral) != m['geral_hash']
                        or link_inseguro(pasta / 'OFX Limpo.ofx')
                        or sha(pasta / 'OFX Limpo.ofx') != m['limpo_hash']
                        or (referencia and (link_inseguro(referencia) or sha(referencia) != m['historico_hash']))):
                    raise ValueError('arquivo alterado durante recuperação')
                origem.unlink()
                fsync_dir(origem.parent)
            m['estado'] = 'CONCLUIDO'
            atualizar_manifesto(op, m)
            finalizar(op)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OrganizacaoError('Recuperação requer inspeção manual; preserve .comparaofx e os arquivos') from exc


def fsync_dir(path):
    if sys.platform == 'win32': return
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(fd)
    finally: os.close(fd)


def escrever(path, data):
    with Path(path).open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def atualizar_manifesto(op, manifesto):
    temp = op / ('manifesto-' + uuid.uuid4().hex + '.tmp')
    escrever(temp, (json.dumps(manifesto, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8'))
    os.replace(temp, op / 'manifesto.json')
    fsync_dir(op)


def iniciar(banco, manifesto):
    base = Path(banco) / '.comparaofx'
    if link_inseguro(base): raise OrganizacaoError('Área de recuperação insegura')
    base.mkdir(exist_ok=True)
    fsync_dir(base.parent)
    op = base / uuid.uuid4().hex
    op.mkdir()
    fsync_dir(base)
    atualizar_manifesto(op, manifesto)
    return op


def publicar_pasta(origem, destino):
    """Renomeia sem substituir destino; falha em plataformas não suportadas."""
    if sys.platform == 'win32':
        os.rename(origem, destino)
    elif sys.platform.startswith('linux'):
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        fn = getattr(libc, 'renameat2', None)
        if fn is None: raise OrganizacaoError('Renomeação exclusiva não suportada neste sistema')
        fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        fn.restype = ctypes.c_int
        if fn(-100, os.fsencode(origem), -100, os.fsencode(destino), 1) != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(destino))
    else:
        raise OrganizacaoError('Publicação exclusiva de pasta não suportada neste sistema')
    fsync_dir(Path(destino).parent)


def publicar_arquivo(temp, destino, substituir):
    if substituir:
        os.replace(temp, destino)
    else:
        # Criação exclusiva: link falha se destino existe, mesmo sob corrida.
        os.link(temp, destino)
        os.unlink(temp)
    fsync_dir(Path(destino).parent)


def finalizar(op):
    # Somente após todas as verificações e exclusões terem terminado.
    if sorted(p.name for p in op.iterdir()) != ['manifesto.json']:
        raise OrganizacaoError('Área de operação contém arquivos inesperados')
    (op / 'manifesto.json').unlink()
    op.rmdir()
    fsync_dir(op.parent)
