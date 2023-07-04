# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vinic
"""

import os
from ofxparse import OfxParser


def get_name_ofx(diretorio_atual):
    for item in os.listdir(diretorio_atual):
        if (".ofx" in item):
            return diretorio_atual + "\\" + item

    raise FileNotFoundError(f'Ofx não está aqui: {diretorio_atual}')


def get_old_directory(diretorio_atual, diretorio_anterior="", nivel=-2):
    if (diretorio_anterior == ""):
        split_dir_atual = dir_atual.split("\\")
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


# Pega o diretório atual
dir_atual = os.getcwd()

# Identifica o arquivo ofx no diretório atual
ofx_atual = get_name_ofx(dir_atual)

# Vai buscar o arquivo ofx anterior imediado (da ultima data atualiazada)
ofx_anterior = get_old_directory(dir_atual)

# Carrega o arquivo OFX atual
with open(ofx_atual, 'rb') as arquivo_ofx_atual:
    ofx_atual = OfxParser.parse(arquivo_ofx_atual)

# Carrega o arquivo OFX anterior
with open(ofx_anterior, 'rb') as arquivo_ofx_anterior:
    ofx_anterior = OfxParser.parse(arquivo_ofx_anterior)

# Coleta todos os checknum (identificadores) do arquvio anterior
list_checknum_anterior = []
for transacao in ofx_anterior.account.statement.transactions:
    list_checknum_anterior.append(transacao.checknum)

# Passar por todas as transações atuais
todas_transactions_atual = ofx_atual.account.statement.transactions
len_transactions = len(todas_transactions_atual)

for idx in range(len_transactions):
    if (todas_transactions_atual[idx].checknum in list_checknum_anterior):
        todas_transactions_atual.pop(idx)
        idx -= 1
