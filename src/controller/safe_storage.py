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

from .organization import OrganizacaoError, link_inseguro, validar_historico_relativo
from .ofx_names import nome_limpo_manifesto


_ativos = {}


class Bloqueio:
    def __init__(self, banco):
        self.banco = Path(banco)
        self.ativo = True


def bloqueio_valido(token, banco):
    registro = _ativos.get(id(token))
    return (isinstance(token, Bloqueio) and token.ativo and token.banco == Path(banco)
            and registro is not None and registro == (token, os.getpid(), threading.get_ident()))


def _verificar_pasta_sincronizada(banco):
    # Locks locais não constituem um protocolo entre dispositivos OneDrive.
    for key in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        value = os.environ.get(key)
        if value and banco.is_relative_to(Path(value).resolve()):
            raise OrganizacaoError('Bloqueio do sistema de arquivos: pasta OneDrive identificada; trabalhe em cópia local fora da sincronização. Exclusão entre dispositivos não é garantida')


def _verificar_volume_windows(banco):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    volume = ctypes.create_unicode_buffer(1024)
    getpath = kernel.GetVolumePathNameW
    getpath.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    getpath.restype = wintypes.BOOL
    if not getpath(str(banco), volume, len(volume)):
        raise OrganizacaoError('Bloqueio do sistema de arquivos: volume não verificável')
    drive = kernel.GetDriveTypeW
    drive.argtypes = (wintypes.LPCWSTR,); drive.restype = wintypes.UINT
    fs = ctypes.create_unicode_buffer(128)
    info = kernel.GetVolumeInformationW
    info.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
                     ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                     ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD)
    info.restype = wintypes.BOOL
    if not info(volume.value, None, 0, None, None, None, fs, len(fs)):
        raise OrganizacaoError('Bloqueio do sistema de arquivos: tipo do volume não verificável')
    if drive(volume.value) != 3 or fs.value.upper() not in ('NTFS', 'REFS'):
        raise OrganizacaoError('Bloqueio do sistema de arquivos: use volume local NTFS/ReFS fora de Drive virtual ou rede; exclusão entre dispositivos não homologada')


@contextlib.contextmanager
def bloquear(banco):
    banco = Path(banco).absolute()
    if link_inseguro(banco) or link_inseguro(banco.parent) or not banco.is_dir():
        raise OrganizacaoError('Instituição inválida para bloqueio')
    banco = banco.resolve(strict=True)
    _verificar_pasta_sincronizada(banco)
    if sys.platform == 'win32':
        _verificar_volume_windows(banco)
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
        links = os.fstat(fd).st_nlink
        if links > 1:
            raise OrganizacaoError('Bloqueio do sistema de arquivos: lock possui hardlinks adicionais; processamento suspenso')
        if links != 1:
            raise OrganizacaoError('Bloqueio do sistema de arquivos: contagem de links não verificável. Use pasta local fora do Drive; sincronização entre dispositivos não garante exclusão mútua')
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


def _validar_csv_manifesto(banco, manifesto, arquivo):
    from .csv_formats import identificar_csv, formato_permitido
    formato = manifesto.get('formato_csv')
    if arquivo.suffix.casefold() != '.csv':
        if formato is not None:
            raise ValueError('Descritor CSV associado a OFX')
        return
    identificado = identificar_csv(arquivo)
    if not formato_permitido(banco, identificado):
        raise ValueError('CSV não corresponde à instituição na recuperação')
    if formato is not None and formato != identificado:
        raise ValueError('Descritor CSV diverge do conteúdo')
    if identificado == 'valori' and formato != 'valori':
        raise ValueError('CSV Valori exige descritor explícito no manifesto')


def _verificar_referencias(banco, manifesto):
    """Verifica referências CSV sem mudar manifestos v1/v2 anteriores."""
    from .organization import pasta_dia
    refs_rede = manifesto.get('referencias_rede', [])
    refs_csv = manifesto.get('referencias_csv', [])
    if not isinstance(refs_rede, list) or not isinstance(refs_csv, list):
        raise ValueError('Referências CSV inválidas')
    if refs_rede and banco.name.casefold() != 'rede':
        raise ValueError('Referências Rede fora da instituição')
    formato = manifesto.get('formato_csv')
    if refs_csv or formato is not None:
        from .csv_formats import formato_permitido
        if not formato_permitido(banco, formato):
            raise ValueError('Formato CSV não autorizado para a instituição')
    refs = refs_rede + refs_csv
    for item in refs:
        rel = Path(item['nome'])
        if rel.is_absolute() or rel.drive or '..' in rel.parts or '\\' in item['nome']:
            raise ValueError('Caminho de referência inválido')
        if not (rel == Path('.rede.json') and banco.name.casefold() == 'rede'):
            validar_historico_relativo(banco, rel)
        path = banco / rel
        for parent in (path, *path.parents):
            if parent == banco.parent:
                break
            if link_inseguro(parent):
                raise ValueError('Referência insegura')
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('Referência ausente ou com múltiplos links')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Referência CSV alterada')


def _limpar_preparacao(banco, op, m):
    """Remove apenas preparação própria quando ainda não houve publicação."""
    import re
    from .organization import ANEXOS, pasta_dia, extrato_permitido, csv_bancario_identificado
    if not re.fullmatch(r'[0-9a-f]{32}', op.name):
        raise ValueError('identificador de operação inválido')
    pasta, geral = Path(m['pasta']), Path(m['geral'])
    for path in (pasta, geral):
        if path.is_absolute() or path.drive or '..' in path.parts or len(path.parts) != 4:
            raise ValueError('caminho inválido')
    data = date.fromisoformat(geral.parent.name)
    if (pasta.parent != geral.parent or pasta_dia(banco, data).relative_to(banco) != geral.parent
            or not re.fullmatch(r'00[1-9]|0[1-9][0-9]|[1-9][0-9]{2}', pasta.name)
            or geral.name != f'OFXGeral-{data.isoformat()}.ofx'):
        raise ValueError('destino inválido')
    pasta, geral = banco / pasta, banco / geral
    for path in (pasta, geral, *pasta.parents):
        if path == banco.parent: break
        if link_inseguro(path): raise ValueError('link inseguro')
    historico_rel = m.get('historico')
    historico = None
    if historico_rel is not None:
        rel = Path(historico_rel)
        validar_historico_relativo(banco, rel)
        historico = banco / rel
        for path in (historico, *historico.parents):
            if path == banco.parent: break
            if link_inseguro(path): raise ValueError('link inseguro')
    def sha(path):
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
        return h.hexdigest()
    limpo_nome = nome_limpo_manifesto(m)
    arquivos = m['arquivos']
    if not isinstance(arquivos, list) or not arquivos:
        raise ValueError('lista inválida')
    nomes = set()
    hashes_esperados = {limpo_nome.casefold(): m['limpo_hash']}
    for i, item in enumerate(arquivos):
        nome = item['nome']
        if (not isinstance(nome, str) or nome in ('', '.', '..') or Path(nome).name != nome
                or '\\' in nome or nome.casefold() in nomes or nome.casefold() == limpo_nome.casefold()):
            raise ValueError('nome inválido')
        nomes.add(nome.casefold())
        hashes_esperados[nome.casefold()] = item['sha256']
        origem = banco.parent / nome
        if link_inseguro(origem) or not origem.is_file() or origem.stat().st_nlink != 1:
            raise ValueError('origem insegura')
        if (i == 0 and not extrato_permitido(banco, banco.parent / nome)) or (i > 0 and (Path(nome).suffix.casefold() not in ANEXOS or csv_bancario_identificado(banco.parent / nome))):
            raise ValueError('tipo inválido')
    _validar_csv_manifesto(banco, m, banco.parent / arquivos[0]['nome'])
    def verificar():
        _verificar_referencias(banco, m)
        for path in (banco, banco / '.comparaofx', op, op / 'pasta', *pasta.parents):
            if path == banco.parent: break
            if link_inseguro(path): raise ValueError('link inseguro durante limpeza')
        if pasta.exists() or link_inseguro(pasta): raise ValueError('pasta já publicada')
        if historico:
            for path in (historico, *historico.parents):
                if path == banco.parent: break
                if link_inseguro(path): raise ValueError('histórico inseguro durante limpeza')
            if link_inseguro(historico) or not historico.is_file() or historico.stat().st_nlink != 1 or sha(historico) != m['historico_hash']:
                raise ValueError('histórico alterado')
        elif m.get('historico_hash') is not None:
            raise ValueError('hash histórico inválido')
        if historico != geral and (geral.exists() or link_inseguro(geral)):
            raise ValueError('geral já publicado')
        for item in arquivos:
            origem = banco.parent / item['nome']
            if link_inseguro(origem) or not origem.is_file() or origem.stat().st_nlink != 1 or sha(origem) != item['sha256']:
                raise ValueError('original ausente ou alterado')
    verificar()
    elementos = list(op.iterdir())
    if any(p.name not in ('manifesto.json','pasta','geral.tmp') for p in elementos):
        raise ValueError('arquivos auxiliares desconhecidos')
    stage = op / 'pasta'
    if stage.exists():
        if link_inseguro(stage) or not stage.is_dir(): raise ValueError('preparação inválida')
        for file in stage.iterdir():
            if (file.name.casefold() not in nomes | {limpo_nome.casefold()} or link_inseguro(file)
                    or not file.is_file() or file.stat().st_nlink != 1
                    or sha(file) != hashes_esperados[file.name.casefold()]):
                raise ValueError('arquivo temporário desconhecido')
    temp = op / 'geral.tmp'
    if temp.exists() and (link_inseguro(temp) or not temp.is_file() or temp.stat().st_nlink != 1 or sha(temp) != m['geral_hash']):
        raise ValueError('geral temporário inválido')
    if stage.exists():
        for file in stage.iterdir():
            verificar()
            if link_inseguro(file) or file.stat().st_nlink != 1 or sha(file) != hashes_esperados[file.name.casefold()]:
                raise ValueError('temporário alterado durante a limpeza')
            file.unlink()
        stage.rmdir()
    if temp.exists():
        verificar()
        if link_inseguro(temp) or temp.stat().st_nlink != 1 or sha(temp) != m['geral_hash']:
            raise ValueError('geral temporário alterado durante a limpeza')
        temp.unlink()
    verificar()
    finalizar(op)


def recuperar_concluida(banco, *, bloqueio=None):
    """Remove somente registro inequivocamente concluído; outros estados bloqueiam.

    Adquire o bloqueio quando necessário. Não remove cópias arquivadas.
    """
    banco = Path(banco).absolute()
    if link_inseguro(banco) or link_inseguro(banco.parent):
        raise OrganizacaoError('Instituição inválida para recuperação')
    banco = banco.resolve(strict=True)
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
            limpo_nome = nome_limpo_manifesto(m)
            if m['estado'] in ('PREPARANDO', 'PREPARADO', 'PUBLICANDO'):
                _limpar_preparacao(banco, op, m)
                continue
            if m['estado'] not in ('PASTA_PUBLICADA', 'HISTORICO_ATUALIZADO', 'CONCLUIDO'):
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
            if link_inseguro(pasta / limpo_nome) or sha(geral) != m['geral_hash'] or sha(pasta / limpo_nome) != m['limpo_hash']:
                raise ValueError('hash de saída divergente')
            referencia = None
            if m.get('historico'):
                historico_rel = Path(m['historico'])
                validar_historico_relativo(banco, historico_rel)
                historico = banco / historico_rel
                if historico != geral:
                    referencia = historico
                    for path in (historico, *historico.parents):
                        if path == banco.parent: break
                        if link_inseguro(path): raise ValueError('histórico inseguro')
                    if sha(historico) != m['historico_hash']:
                        raise ValueError('histórico de referência alterado')
            _verificar_referencias(banco, m)
            arquivos = m['arquivos']
            if not isinstance(arquivos, list) or not arquivos:
                raise ValueError('lista de arquivos inválida')
            origens = []
            vistos = set()
            from .organization import ANEXOS, extrato_permitido, csv_bancario_identificado
            for idx, item in enumerate(arquivos):
                nome = item['nome']
                if not isinstance(nome, str) or nome in ('', '.', '..') or Path(nome).name != nome or '\\' in nome:
                    raise ValueError('nome de arquivo inválido')
                if nome.casefold() in vistos or nome.casefold() == limpo_nome.casefold():
                    raise ValueError('nomes duplicados')
                vistos.add(nome.casefold())
                origem, copia = banco.parent / nome, pasta / nome
                if link_inseguro(origem) or link_inseguro(copia) or not copia.is_file() or copia.stat().st_nlink != 1 or sha(copia) != item['sha256']:
                    raise ValueError('cópia divergente')
                if (idx == 0 and not extrato_permitido(banco, pasta / nome)) or (idx > 0 and (Path(nome).suffix.casefold() not in ANEXOS or csv_bancario_identificado(pasta / nome))):
                    raise ValueError('tipo de arquivo inválido')
                if idx == 0:
                    _validar_csv_manifesto(banco, m, pasta / nome)
                if origem.exists():
                    if not origem.is_file() or origem.stat().st_nlink != 1 or sha(origem) != item['sha256']:
                        raise ValueError('origem divergente')
                    origens.append((origem, copia, item['sha256']))
            # Todos os dados e a ausência de alterações são verificados antes de
            # cada remoção. O manifesto persiste mesmo após uma remoção parcial.
            for origem, copia, digest in origens:
                _verificar_referencias(banco, m)
                if (link_inseguro(origem) or link_inseguro(copia)
                        or origem.stat().st_nlink != 1 or link_inseguro(geral)
                        or sha(origem) != digest or sha(copia) != digest
                        or sha(geral) != m['geral_hash']
                        or link_inseguro(pasta / limpo_nome)
                        or sha(pasta / limpo_nome) != m['limpo_hash']
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
