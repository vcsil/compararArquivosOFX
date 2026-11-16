"""Menus simples para escolher arquivos e instituições."""
from .organization import instituicoes, extratos, csvs_extrato, anexos, raiz_aplicacao
from .terminal_style import Terminal

class Cancelado(Exception):
    pass


def escolher(opcoes, titulo, entrada=input, saida=print):
    tela = Terminal(saida)
    tela.texto(titulo, 'cabecalho')
    for i, item in enumerate(opcoes, 1):
        tela.opcao(i, item.name)
    tela.texto('00 - Cancelar', 'aviso')
    while True:
        valor = entrada('Escolha: ').strip()
        if valor.isdigit() and int(valor) == 0:
            raise Cancelado()
        if valor.isdigit() and 1 <= int(valor) <= len(opcoes):
            return opcoes[int(valor)-1]
        tela.texto('Entrada inválida.', 'aviso')


def escolher_anexos(opcoes, entrada=input, saida=print):
    if not opcoes:
        return []
    tela = Terminal(saida)
    tela.texto('Anexos disponíveis:', 'cabecalho')
    for i, item in enumerate(opcoes, 1):
        tela.opcao(i, item.name)
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
        tela.texto('Entrada inválida.', 'aviso')


def selecionar(raiz, entrada=input, saida=print):
    tela = Terminal(saida)
    arquivos = extratos(raiz) + csvs_extrato(raiz)
    arquivos = sorted(arquivos, key=lambda p: (p.name.casefold(), p.name))
    if not arquivos:
        if any(p.is_file() and p.suffix.casefold() == '.csv' for p in raiz.iterdir()):
            from .organization import OrganizacaoError
            raise OrganizacaoError('CSV desconhecido ou sem instituição compatível; não foi tratado como extrato')
        tela.texto('Nenhum arquivo OFX ou CSV bancário compatível encontrado na raiz.', 'aviso')
        return None
    arquivo = arquivos[0] if len(arquivos) == 1 else escolher(arquivos, 'Arquivos de extrato encontrados:', entrada, saida)
    tela.texto('Arquivo selecionado: ' + arquivo.name)
    bancos = instituicoes(raiz)
    if arquivo.suffix.casefold() == '.csv':
        from .csv_formats import identificar_csv, formato_permitido
        formato = identificar_csv(arquivo)
        bancos = [b for b in bancos if formato_permitido(b, formato)]
    if not bancos:
        tela.texto('Nenhuma instituição compatível com o extrato selecionado.', 'aviso')
        return None
    banco = escolher(bancos, 'Selecione a instituição:', entrada, saida)
    tela.texto('Instituição escolhida: ' + banco.name)
    # Relatórios CSV bancários são entradas, não anexos a arquivar.
    disponiveis = [p for p in anexos(raiz) if p != arquivo and
                   (arquivo.suffix.casefold() != '.csv' or p.suffix.casefold() != '.csv')]
    selecionados = disponiveis if len(arquivos) == 1 and len(bancos) == 1 else escolher_anexos(disponiveis, entrada, saida)
    tela.texto(f'Anexos selecionados: {len(selecionados)} - ' + (', '.join(p.name for p in selecionados) or 'nenhum'))
    return banco, arquivo, selecionados
