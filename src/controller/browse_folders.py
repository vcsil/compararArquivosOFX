# -*- coding: utf-8 -*-
"""
Created on Tue Jul  4 17:10:08 2023

@author: vsil
"""

import os


def get_name_ofx(diretorio, nome_arq, verifica_existencia=False):
    list_dir = os.listdir(diretorio)

    if (verifica_existencia):
        if (len(list_dir) >= 3):
            raise FileExistsError(f'Verifique se o arquivo já foi gerado em {diretorio}')

    for item in list_dir:
        if ((".ofx" in item) and (nome_arq in item)):
            return diretorio + "\\" + item

    raise FileNotFoundError(f'Ofx "{nome_arq}" não está aqui: {diretorio}')


def get_old_directory(diretorio_atual, diretorio_anterior="", subiu=False, nivel=-2):
    if (diretorio_anterior == ""):
        split_dir_atual = diretorio_atual.split("\\")
        diretorio_anterior = "\\".join(split_dir_atual[:-1])
        try:
            return get_name_ofx(diretorio_anterior, f"OFXGeral-{split_dir_atual[-2]}")
        except FileNotFoundError:
            pass

    # Analisa os arquivos dentro do diretorio e vê se tem algum ofx
    list_dir_anterior = os.listdir(diretorio_anterior)

    # Verifica se tem mais de um arquivo no diretório, indica ter ofx,
    # se não tiver, sobe até o anterior imediado
    if ((len(list_dir_anterior) == 1) and not subiu):
        att_diretorio_anterior = "\\".join(diretorio_anterior.split("\\")[:-1])
        return get_old_directory(diretorio_atual, att_diretorio_anterior, nivel=-2)

    # Pastas com ofx do dia são nomedas por até 3 dígitos númericos
    # Se tiver mais de 3 dígitos pode ser o diretorio geral do dia, mês ou ano.
    elif (len(list_dir_anterior[nivel]) > 3):
        att_diretorio_anterior = diretorio_anterior + "\\" + list_dir_anterior[nivel]

        # Verifica se tem um arquivo geral com todas as transferencias lidas
        # até o último momento que foi baixado, no diretorio do dia
        if (len(list_dir_anterior[nivel]) == 10):
            for item in os.listdir(att_diretorio_anterior):
                if ((".ofx" in item) and (f"OFXGeral-{list_dir_anterior[nivel]}" in item)):
                    return att_diretorio_anterior + "\\" + item

        # Vai entrar na ultima pasta do novo diretório
        return get_old_directory(diretorio_atual, att_diretorio_anterior, subiu=True, nivel=-1)

    else:
        att_diretorio_anterior = diretorio_anterior + "\\" + list_dir_anterior[nivel]
        return get_name_ofx(att_diretorio_anterior, "Extrato")
