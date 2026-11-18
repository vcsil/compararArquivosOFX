"""Capacidades observadas, sem inferir segurança pelo nome/tipo do Drive."""
import contextlib
import ctypes
import hashlib
import os
from pathlib import Path
import sys
import tempfile

from .organization import OrganizacaoError


def volume_windows(path):
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    root = ctypes.create_unicode_buffer(32768)
    kernel.GetVolumePathNameW.argtypes = (w.LPCWSTR, w.LPWSTR, w.DWORD)
    kernel.GetVolumePathNameW.restype = w.BOOL
    if not kernel.GetVolumePathNameW(str(Path(path).resolve()), root, len(root)):
        raise OrganizacaoError('Armazenamento: não foi possível consultar capacidades do volume')
    flags = w.DWORD()
    kernel.GetVolumeInformationW.argtypes = (w.LPCWSTR, w.LPWSTR, w.DWORD,
        ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD), w.LPWSTR, w.DWORD)
    kernel.GetVolumeInformationW.restype = w.BOOL
    if not kernel.GetVolumeInformationW(root.value, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise OrganizacaoError('Armazenamento: capacidades de hardlinks não verificáveis')
    return flags.value


def links_seguros(path):
    """Zero não prova hardlink; só aceitar se o volume não oferece hardlinks.

    Se o provedor declara hardlinks, uma contagem indisponível não permite
    excluir aliases com segurança. Não memorizar esta informação entre operações.
    """
    count = Path(path).stat().st_nlink
    if count == 1:
        return True
    if count > 1:
        return False
    if sys.platform == 'win32' and not volume_windows(path) & 0x00400000:  # FILE_SUPPORTS_HARD_LINKS
        return True
    raise OrganizacaoError('Armazenamento: contagem de links indisponível em volume com hardlinks ou capacidade desconhecida; não é possível excluir aliases com segurança')


@contextlib.contextmanager
def mutex_windows(banco):
    """Mutex do kernel: exclusão na máquina, inclusive entre sessões Windows.

    Não fica no volume sincronizado e não depende de msvcrt.locking/st_nlink.
    Não constitui exclusão contra outro computador ou editor externo.
    """
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    # Normaliza nomes 8.3 antes de formar a identidade da instituição.
    longpath = ctypes.create_unicode_buffer(32768)
    kernel.GetLongPathNameW.argtypes = (w.LPCWSTR, w.LPWSTR, w.DWORD)
    kernel.GetLongPathNameW.restype = w.DWORD
    length = kernel.GetLongPathNameW(str(banco), longpath, len(longpath))
    if not length or length >= len(longpath):
        raise OrganizacaoError('Bloqueio local: identidade do caminho não verificável')
    name = 'Global\\ComparaOFX-' + hashlib.sha256(os.path.normcase(longpath.value).encode('utf-8')).hexdigest()
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, w.BOOL, w.LPCWSTR)
    kernel.CreateMutexW.restype = w.HANDLE
    kernel.WaitForSingleObject.argtypes = (w.HANDLE, w.DWORD)
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.ReleaseMutex.argtypes = (w.HANDLE,)
    kernel.CloseHandle.argtypes = (w.HANDLE,)
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise OrganizacaoError('Bloqueio local: não foi possível abrir mutex do Windows')
    acquired = False
    try:
        # Mutexes Windows são recursivos: recusar também reentrada na thread.
        if name in _mutexes:
            raise OrganizacaoError('Instituição já está em processamento')
        result = kernel.WaitForSingleObject(handle, 0)
        if result not in (0, 0x80):  # WAIT_OBJECT_0 / WAIT_ABANDONED
            raise OrganizacaoError('Instituição já está em processamento' if result == 0x102 else 'Bloqueio local: espera do mutex falhou')
        acquired = True
        _mutexes.add(name)
        yield
    finally:
        if acquired:
            _mutexes.discard(name)
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


_mutexes = set()


def verificar_capacidades(banco):
    """Exercita primitivas reais num diretório descartável antes da importação.

    O teste não prova persistência após queda de energia nem atomicidade de
    sincronização remota. Publicação usa rename, nunca cópia no nome definitivo.
    """
    from .storage_primitives import escrever, publicar_arquivo, publicar_pasta
    etapa = 'criação de diretório de diagnóstico'
    try:
        with tempfile.TemporaryDirectory(prefix='.comparaofx-probe-', dir=banco) as tmp:
            root = Path(tmp)
            a, b = root / 'a.tmp', root / 'b.ofx'
            data = b'ComparaOFX synthetic storage probe\n' * 4096
            etapa = 'escrita exclusiva, flush e releitura SHA-256'
            escrever(a, data)
            if hashlib.sha256(a.read_bytes()).digest() != hashlib.sha256(data).digest():
                raise ValueError('conteúdo relido divergente')
            etapa = 'criação exclusiva sem sobrescrita'
            try:
                escrever(a, b'nao sobrescrever')
            except FileExistsError:
                pass
            else:
                raise ValueError('criação substituiu arquivo existente')
            etapa = 'publicação de arquivo por renomeação exclusiva'
            publicar_arquivo(a, b, False)
            escrever(a, b'novo')
            try:
                publicar_arquivo(a, b, False)
            except FileExistsError:
                pass
            else:
                raise ValueError('destino existente substituído')
            if a.read_bytes() != b'novo' or b.read_bytes() != data:
                raise ValueError('colisão alterou conteúdo')
            etapa = 'substituição controlada de arquivo'
            publicar_arquivo(a, b, True)
            if b.read_bytes() != b'novo':
                raise ValueError('substituição não preservou conteúdo')
            etapa = 'renomeação exclusiva de pasta'
            src, dst = root / 'stage', root / 'final'
            src.mkdir(); escrever(src / 'arquivo', data)
            publicar_pasta(src, dst)
            src.mkdir()
            try:
                publicar_pasta(src, dst)
            except OSError:
                pass
            else:
                raise ValueError('pasta existente substituída')
            if (dst / 'arquivo').read_bytes() != data or not src.is_dir():
                raise ValueError('renomeação alterou conteúdo')
            etapa = 'substituição e releitura de manifesto'
            for value in (b'{"probe": 1}', b'{"probe": 2}'):
                escrever(root / 'manifesto.tmp', value)
                os.replace(root / 'manifesto.tmp', root / 'manifesto.json')
            import json
            if json.loads((root / 'manifesto.json').read_text(encoding='utf-8')) != {'probe': 2}:
                raise ValueError('manifesto divergente')
            etapa = 'verificação de hardlinks'
            if not links_seguros(b):
                raise ValueError('arquivo sintético possui aliases físicos')
    except (OSError, ValueError) as exc:
        raise OrganizacaoError(f'Armazenamento: falha em {etapa}; operação não autorizada ({exc})') from exc
