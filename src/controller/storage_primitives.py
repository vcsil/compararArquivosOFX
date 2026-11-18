"""Primitivas compartilhadas pelo fluxo e pelo diagnóstico de armazenamento."""
import os
from pathlib import Path
import sys
from .organization import OrganizacaoError


def fsync_dir(path):
    if sys.platform == 'win32': return
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(fd)
    finally: os.close(fd)


def escrever(path, data):
    with Path(path).open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


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
        if sys.platform == 'win32':
            os.rename(temp, destino)  # Windows: sem REPLACE_EXISTING, sem cópia.
        else:
            os.link(temp, destino)
            os.unlink(temp)
    fsync_dir(Path(destino).parent)
