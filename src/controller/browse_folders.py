# -*- coding: utf-8 -*-
"""
Created on Tue Jul  4 17:10:08 2023

@author: vinic
"""

import os


def get_name_ofx(diretorio_atual):
    for item in os.listdir(diretorio_atual):
        if (".ofx" in item):
            return diretorio_atual + "\\" + item

    raise FileNotFoundError(f'Ofx não está aqui: {diretorio_atual}')


def get_old_directory(diretorio_atual, diretorio_anterior="", nivel=-2):
    if (diretorio_anterior == ""):
        split_dir_atual = diretorio_atual.split("\\")
        diretorio_anterior = "\\".join(split_dir_atual[:-1])

    list_dir_anterior = os.listdir(diretorio_anterior)

    # Verifica se tem mais de um arquivo no diretório, indica ter ofx,
    # se não tiver, sobe até o anterior imediado
    if (len(list_dir_anterior) == 1):
        att_diretorio_anterior = "\\".join(diretorio_anterior.split("\\")[:-1])
        return get_old_directory(diretorio_atual, att_diretorio_anterior, -2)
    # Pastas que contém ofx são nomedas por até 3 dígitos númericos
    elif (len(list_dir_anterior[nivel]) > 3):
        att_diretorio_anterior = diretorio_anterior + "\\" + list_dir_anterior[nivel]
        return get_old_directory(diretorio_atual, att_diretorio_anterior, -1)

    else:
        att_diretorio_anterior = diretorio_anterior + "\\" + list_dir_anterior[nivel]
        return get_name_ofx(att_diretorio_anterior)
