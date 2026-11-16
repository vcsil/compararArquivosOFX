"""Descoberta e planejamento de arquivos, sem acesso fora da raiz escolhida."""
from datetime import date
from pathlib import Path
import os
import re
import stat
import sys

TECNICOS = {'.git', '.github', '.venv', 'venv', 'env', 'src', 'tests', 'docs', 'build', 'dist', '__pycache__', 'node_modules', '.agents', '.codex', 'shared', 'attachments'}
ANEXOS = {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.csv', '.xlsx', '.xls', '.html', '.htm', '.docx'}
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


def csvs_extrato(raiz):
    from .csv_formats import identificar_csv, formato_permitido
    bancos = instituicoes(raiz)
    result = []
    for p in raiz.iterdir():
        if not _regular(p) or p.suffix.casefold() != '.csv' or p.name.startswith(('~', '.')):
            continue
        try:
            formato = identificar_csv(p)
        except (ValueError, OSError):
            continue
        if any(formato_permitido(b, formato) for b in bancos):
            result.append(p)
    return sorted(result, key=lambda p: (p.name.casefold(), p.name))


def csvs_rede(raiz):
    # API anterior preservada, agora filtrando o conteúdo de fato.
    from .csv_formats import identificar_csv
    return [p for p in csvs_extrato(raiz) if identificar_csv(p) == 'rede']


def extrato_permitido(banco, arquivo):
    from .csv_formats import identificar_csv, formato_permitido
    path = Path(arquivo)
    if path.suffix.casefold() == '.ofx':
        return True
    try:
        return path.suffix.casefold() == '.csv' and formato_permitido(banco, identificar_csv(path))
    except (OSError, ValueError):
        return False


def csv_rede_identificado(path):
    from .csv_formats import identificar_csv
    try:
        return identificar_csv(path) == 'rede'
    except (ValueError, OSError):
        return False


def csv_bancario_identificado(path):
    from .csv_formats import csv_bancario
    return csv_bancario(path)


def anexos(raiz):
    return sorted((p for p in raiz.iterdir() if _regular(p) and p.suffix.casefold() in ANEXOS and not csv_bancario_identificado(p)
                   and not p.name.startswith(('~', '.'))), key=lambda p: (p.name.casefold(), p.name))


def pasta_dia(banco, hoje):
    return banco / f'{hoje.year:04d}' / f'{hoje.month:02d} - {MESES[hoje.month-1]} {hoje.year:04d}' / hoje.isoformat()


def proxima_importacao(dia):
    if not dia.exists():
        return dia / '001'
    nums = [int(p.name) for p in dia.iterdir() if not link_inseguro(p) and p.is_dir() and re.fullmatch(r'(?:\d{2}|\d{3})', p.name)]
    numero = max(nums, default=0) + 1
    if numero > 999:
        raise OrganizacaoError('Limite de 999 importações por dia atingido')
    return dia / f'{numero:03d}'


MESES_EXTENSO = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')


def data_diretorio_historico(banco, diretorio):
    """Reconhece somente convenções comprovadas, sem mover nem renomear dados."""
    parts = Path(diretorio).relative_to(banco).parts
    try:
        dia = date.fromisoformat(parts[-1])
    except (ValueError, IndexError) as exc:
        raise OrganizacaoError('Histórico legado: pasta diária inválida') from exc
    if parts[-1] != dia.isoformat() or len(parts) not in (2, 3):
        raise OrganizacaoError('Histórico legado: hierarquia desconhecida')
    if len(parts) == 3 and parts[0] != f'{dia.year:04d}':
        raise OrganizacaoError('Histórico legado: ano inconsistente')
    month = parts[-2]
    atual = f'{dia.month:02d} - {MESES[dia.month-1]} {dia.year:04d}'
    antigo = f'{dia.month:02d} - {MESES_EXTENSO[dia.month-1]}'
    if month != atual and not (len(parts) == 3 and month == antigo):
        raise OrganizacaoError('Histórico legado: mês inconsistente ou desconhecido')
    return dia


def validar_historico_relativo(banco, rel):
    rel = Path(rel)
    if rel.is_absolute() or rel.drive or '..' in rel.parts or len(rel.parts) not in (3, 4):
        raise OrganizacaoError('Histórico legado: caminho de referência inválido')
    dia = data_diretorio_historico(banco, banco / rel.parent)
    nomes = (f'OFXGeral-{dia.isoformat()}.ofx', f'Bradesco Geral - {dia.isoformat()}.ofx')
    if rel.name.casefold() not in {n.casefold() for n in nomes}:
        raise OrganizacaoError('Histórico legado: Geral ausente ou nome/data divergentes; exige conciliação manual')
    return dia


def historicos_validos(banco, hoje):
    """Indexa Gerais modernos e legados; ambiguidades bloqueiam toda a seleção."""
    banco = Path(banco)
    candidatos = []
    for base, dirs, files in os.walk(banco, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        root = Path(base)
        for name in dirs + files:
            if link_inseguro(root / name):
                raise OrganizacaoError('Histórico contém link ou ponto de reparse')
        parts = root.relative_to(banco).parts
        if not parts:
            if '.comparaofx' in dirs:
                dirs.remove('.comparaofx')
            if any(Path(f).suffix.casefold() == '.ofx' for f in files):
                raise OrganizacaoError('OFX fora da estrutura esperada na instituição')
            continue
        # Pais de pastas diárias reconhecidas não podem conter arquivos soltos.
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', parts[-1]):
            if files or len(parts) > 2:
                raise OrganizacaoError('Histórico legado: arquivos ou diretórios fora da estrutura reconhecida')
            if len(parts) == 1 and re.fullmatch(r'\d{4}', parts[0]):
                continue
            month = parts[-1]
            match = re.fullmatch(r'(\d{2}) - ([A-Za-zÀ-ÿ]{3}) (\d{4})', month)
            moderno = bool(match and 1 <= int(match[1]) <= 12
                           and match[2] == MESES[int(match[1])-1] and int(match[3]) > 0
                           and (len(parts) == 1 or match[3] == parts[0]))
            antigo = len(parts) == 2 and month in {f'{i+1:02d} - {m}' for i,m in enumerate(MESES_EXTENSO)}
            if not (moderno or antigo):
                raise OrganizacaoError('Histórico legado: diretório desconhecido')
            continue
        dia = data_diretorio_historico(banco, root)
        importacoes = [d for d in dirs if re.fullmatch(r'(?:0[1-9]|[1-9]\d|00[1-9]|0[1-9]\d|[1-9]\d{2})', d)]
        if len(importacoes) != len(dirs):
            raise OrganizacaoError('Pasta inesperada no histórico diário')
        # Não seguir links ocultos dentro de arquivos históricos de importação.
        for imp in importacoes:
            for child in (root / imp).iterdir():
                if link_inseguro(child) or not child.is_file():
                    raise OrganizacaoError('Arquivo histórico de importação inseguro')
        if dia > hoje and (importacoes or files):
            raise OrganizacaoError('Histórico com data futura')
        gerais = []
        for name in files:
            if name.casefold().startswith(('ofxgeral-', 'bradesco geral - ')) and name.lower().endswith('.ofx'):
                validar_historico_relativo(banco, (root / name).relative_to(banco))
                gerais.append(root / name)
        if len(gerais) != 1 and (importacoes or files):
            raise OrganizacaoError('Histórico legado: Geral ausente ou ambíguo; exige conciliação manual')
        if gerais:
            candidatos.append((dia, gerais[0]))
        dirs[:] = []
    if len({d for d,p in candidatos}) != len(candidatos):
        raise OrganizacaoError('Histórico legado: mais de um Geral para a mesma data')
    return sorted(candidatos, key=lambda item: item[0])


def localizar_historico(banco, hoje):
    candidatos = historicos_validos(banco, hoje)
    return candidatos[-1][1] if candidatos else None
