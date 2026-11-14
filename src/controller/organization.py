"""Descoberta e planejamento de arquivos, sem acesso fora da raiz escolhida."""
from datetime import date
from pathlib import Path
import os
import re
import stat
import sys

TECNICOS = {'.git', '.github', '.venv', 'venv', 'env', 'src', 'tests', 'docs', 'build', 'dist', '__pycache__', 'node_modules', '.agents', '.codex', 'shared', 'attachments'}
ANEXOS = {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.csv', '.xlsx', '.docx'}
MESES = ('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')

class OrganizacaoError(ValueError):
    pass


def raiz_aplicacao(raiz=None):
    if raiz is not None:
        return Path(raiz).resolve(strict=True)
    # Nuitka normalizes argv[0] to the original executable in both modes.
    # containing_dir points ABOVE .dist in standalone; __file__ and
    # sys.executable can point inside the extraction directory in onefile.
    if '__compiled__' in globals():
        return Path(sys.argv[0]).resolve(strict=True).parent
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve(strict=True).parent
    return Path(__file__).resolve().parents[2]


def link_inseguro(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return (path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0)
                                     & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)))


def caminho_direto(raiz, caminho):
    """Valida links antes de normalizar e exige que o pai seja a raiz real.

    samefile compara identidade no sistema, inclusive nomes curtos Windows;
    construir a partir da raiz validada evita continuar usando um alias externo.
    """
    caminho = Path(caminho).absolute()
    if link_inseguro(caminho) or link_inseguro(caminho.parent):
        raise OrganizacaoError('Links ou pontos de reparse não são permitidos')
    try:
        if not os.path.samefile(caminho.parent, raiz):
            raise OrganizacaoError('Caminho não pertence diretamente à raiz')
        normalizado = (raiz / caminho.name).resolve(strict=True)
        if not os.path.samefile(normalizado.parent, raiz):
            raise OrganizacaoError('Caminho resolvido fora da raiz')
        return normalizado
    except OSError as exc:
        raise OrganizacaoError('Não foi possível verificar a identidade do caminho') from exc


def _regular(path):
    return not link_inseguro(path) and path.is_file()


def instituicoes(raiz):
    return sorted((p for p in raiz.iterdir() if not link_inseguro(p) and p.is_dir()
                   and not p.name.startswith('.') and p.name.casefold() not in TECNICOS),
                  key=lambda p: (p.name.casefold(), p.name))


def extratos(raiz):
    return sorted((p for p in raiz.iterdir() if _regular(p) and p.suffix.casefold() == '.ofx'
                   and not p.name.startswith(('~', '.'))), key=lambda p: (p.name.casefold(), p.name))


def csvs_rede(raiz):
    """Relatórios CSV elegíveis somente para a instituição 'Rede'."""
    if not any(p.name.casefold() == 'rede' for p in instituicoes(raiz)):
        return []
    return sorted((p for p in raiz.iterdir()
                   if _regular(p) and p.suffix.casefold() == '.csv'
                   and not p.name.startswith(('~', '.'))),
                  key=lambda p: (p.name.casefold(), p.name))


def extrato_permitido(banco, arquivo):
    """Não autorizar CSV como extrato de outras instituições."""
    extensao = Path(arquivo).suffix.casefold()
    return extensao == '.ofx' or (extensao == '.csv' and Path(banco).name.casefold() == 'rede')


def anexos(raiz):
    return sorted((p for p in raiz.iterdir() if _regular(p) and p.suffix.casefold() in ANEXOS
                   and not p.name.startswith(('~', '.'))), key=lambda p: (p.name.casefold(), p.name))


def pasta_dia(banco, hoje):
    return banco / f'{hoje.year:04d}' / f'{hoje.month:02d} - {MESES[hoje.month-1]} {hoje.year:04d}' / hoje.isoformat()


def proxima_importacao(dia):
    if not dia.exists():
        return dia / '001'
    nums = [int(p.name) for p in dia.iterdir() if not link_inseguro(p) and p.is_dir() and re.fullmatch(r'\d{3}', p.name)]
    numero = max(nums, default=0) + 1
    if numero > 999:
        raise OrganizacaoError('Limite de 999 importações por dia atingido')
    return dia / f'{numero:03d}'


def localizar_historico(banco, hoje):
    """Exige estrutura íntegra; nunca segue links nem ignora importação órfã."""
    candidatos = []
    for base, dirs, files in os.walk(banco, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        root = Path(base)
        for name in dirs + files:
            if link_inseguro(root / name):
                raise OrganizacaoError('Histórico contém link simbólico; verifique a instituição')
        rel = root.relative_to(banco)
        parts = rel.parts
        if not parts:
            if '.comparaofx' in dirs:
                dirs.remove('.comparaofx')
            if any(Path(f).suffix.casefold() == '.ofx' for f in files):
                raise OrganizacaoError('OFX fora da estrutura esperada na instituição')
            continue
        if len(parts) == 1:
            if not re.fullmatch(r'\d{4}', parts[0]):
                raise OrganizacaoError('Diretório inesperado na instituição: ' + parts[0])
            if files:
                raise OrganizacaoError('Arquivos fora da pasta diária de histórico')
        elif len(parts) == 2:
            month = re.fullmatch(r'(\d{2}) - ([A-Za-z]{3}) (\d{4})', parts[1])
            if (not month or not 1 <= int(month.group(1)) <= 12
                    or month.group(2) != MESES[int(month.group(1))-1]
                    or month.group(3) != parts[0]):
                raise OrganizacaoError('Pasta de mês inconsistente')
            if files:
                raise OrganizacaoError('Arquivos fora da pasta diária de histórico')
        elif len(parts) == 3:
            try:
                dia = date.fromisoformat(parts[2])
            except ValueError as exc:
                raise OrganizacaoError('Data de histórico inválida') from exc
            if parts[0] != f'{dia.year:04d}' or parts[1] != f'{dia.month:02d} - {MESES[dia.month-1]} {dia.year:04d}' or parts[2] != dia.isoformat():
                raise OrganizacaoError('Hierarquia de histórico inconsistente')
            oficial = f'OFXGeral-{dia.isoformat()}.ofx'
            importacoes = [d for d in dirs if re.fullmatch(r'\d{3}', d)]
            ofxs = [f for f in files if f.lower().endswith('.ofx')]
            if any(d not in importacoes for d in dirs):
                raise OrganizacaoError('Pasta inesperada no histórico diário')
            if dia > hoje and (importacoes or ofxs):
                raise OrganizacaoError('Histórico com data futura')
            if oficial in files:
                if not _regular(root / oficial):
                    raise OrganizacaoError('Geral não é arquivo regular')
                candidatos.append((dia, root / oficial))
            elif importacoes or files:
                raise OrganizacaoError('Evidências de importação sem OFX Geral oficial')
            # Não percorrer arquivos das importações para selecionar o histórico.
            dirs[:] = []
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1] if candidatos else None
