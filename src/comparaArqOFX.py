# -*- coding: utf-8 -*-
"""Fluxo de terminal existente com comparação validada antes da gravação."""
import os
import traceback

from colorama import init, Fore, Style
from controller.browse_folders import get_name_ofx, get_old_directory
from controller.user_navigation import define_diretorio
from controller.ofx_functions import carregar_ofx, salvar_ofx, salvar_ofx_geral
from controller.ofx_comparison import analisar

init()

try:
    dir_atual = define_diretorio()
    caminho_atual = get_name_ofx(dir_atual, 'Extrato', True)
    # A busca legada não distingue ausência de histórico de falha de navegação.
    # Falhas são propagadas: não assumir primeira importação de modo inseguro.
    caminho_anterior = get_old_directory(dir_atual)
    header_atual, atual = carregar_ofx(caminho_atual)
    anterior = carregar_ofx(caminho_anterior)[1] if caminho_anterior else None

    # Se o geral do dia já existe, ele precisa ser o histórico comparado;
    # caso contrário a escrita legada poderia acrescentar a outro histórico.
    partes = dir_atual.split('\\')
    if len(partes) < 2:
        raise ValueError('Estrutura de diretório incompatível com OFX Geral')
    pai = '\\'.join(partes[:-1])
    existentes = [nome for nome in os.listdir(pai)
                  if '.ofx' in nome and f'OFXGeral-{partes[-2]}' in nome]
    if len(existentes) > 1:
        raise ValueError('Mais de um OFX Geral encontrado para o dia')
    if existentes:
        alvo = pai + '\\' + existentes[0]
        if not caminho_anterior or not os.path.samefile(alvo, caminho_anterior):
            raise ValueError('O OFX Geral do dia não é o histórico comparado')

    resultado = analisar(atual, anterior)
    rel = resultado.relatorio
    print(f'Situação: {rel.estado}')
    if rel.conta:
        print(f'Conta: {rel.conta.mascarada()}')
    print(f'Referência: {rel.referencia}; original: {rel.original.quantidade}; '
          f'anteriores: {rel.anteriores.quantidade}; duplicatas: {rel.duplicatas.quantidade}; '
          f'novas: {rel.novas.quantidade}')
    print(f'Créditos: {rel.novas.creditos}; débitos: {rel.novas.debitos}; líquido: {rel.novas.liquido}')
    for aviso in rel.divergencias_memo:
        print(aviso)
    if rel.estado == 'BLOQUEADO':
        raise ValueError(rel.motivo)
    if rel.estado != 'SEM_NOVIDADES':
        filtrado = resultado.modelo_filtrado(atual)
        salvar_ofx(filtrado, header_atual, dir_atual)
        salvar_ofx_geral(filtrado, header_atual, dir_atual)
    input(Fore.GREEN + '\nPressione enter para sair.' + Style.RESET_ALL)
except Exception:
    print('\n' + traceback.format_exc())
    input(Fore.RED + '\nPressione enter para sair.' + Style.RESET_ALL)
