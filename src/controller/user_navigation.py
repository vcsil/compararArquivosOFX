"""Menus simples para escolher arquivos e instituições."""
from .organization import instituicoes, extratos, anexos, raiz_aplicacao

class Cancelado(Exception):
    pass


def escolher(opcoes, titulo, entrada=input, saida=print):
    saida(titulo)
    for i, item in enumerate(opcoes, 1):
        saida(f'{i:02} - {item.name}')
    saida('00 - Cancelar')
    while True:
        valor = entrada('Escolha: ').strip()
        if valor.isdigit() and int(valor) == 0:
            raise Cancelado()
        if valor.isdigit() and 1 <= int(valor) <= len(opcoes):
            return opcoes[int(valor)-1]
        saida('Entrada inválida.')


def escolher_anexos(opcoes, entrada=input, saida=print):
    if not opcoes:
        return []
    saida('Anexos disponíveis:')
    for i, item in enumerate(opcoes, 1):
        saida(f'{i:02} - {item.name}')
    while True:
        valor = entrada('Números separados por vírgula, T para todos, N para nenhum ou C para cancelar: ').strip().casefold()
        if valor == 'c':
            raise Cancelado()
        if valor == 'n':
            return []
        if valor == 't':
            return list(opcoes)
        partes = [x.strip() for x in valor.split(',')]
        if all(x.isdigit() and 1 <= int(x) <= len(opcoes) for x in partes):
            indices = {int(x)-1 for x in partes}
            return [p for i, p in enumerate(opcoes) if i in indices]
        saida('Entrada inválida.')


def selecionar(raiz, entrada=input, saida=print):
    arquivos = extratos(raiz)
    if not arquivos:
        saida('Nenhum arquivo OFX encontrado na raiz.')
        return None
    arquivo = arquivos[0] if len(arquivos) == 1 else escolher(arquivos, 'Arquivos OFX encontrados:', entrada, saida)
    saida('Arquivo selecionado: ' + arquivo.name)
    bancos = instituicoes(raiz)
    if not bancos:
        saida('Nenhuma pasta de instituição encontrada.')
        return None
    banco = escolher(bancos, 'Selecione a instituição:', entrada, saida)
    disponiveis = anexos(raiz)
    selecionados = disponiveis if len(arquivos) == 1 else escolher_anexos(disponiveis, entrada, saida)
    saida('Anexos: ' + (', '.join(p.name for p in selecionados) or 'nenhum'))
    return banco, arquivo, selecionados
