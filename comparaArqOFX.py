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
            return item

    raise FileNotFoundError(f'Ofx não está aqui: {diretorio_atual}')


# Pega o diretório atual
dir_atual = os.getcwd()
list_dir_atual = dir_atual.split("\\")

# Identifica o arquivo ofx no diretório atual
ofx_atual = get_name_ofx(dir_atual)

# Carrega o arquivo OFX atual
with open(dir_atual + "\\" + ofx_atual, 'rb') as arquivo_ofx_atual:
    ofx_atual = OfxParser.parse(arquivo_ofx_atual)

# Vai buscar o arquivo ofx anterior
# 1 - Busca no diretório anterior
dir_superior = "\\".join(list_dir_atual[:-1])
if (len(os.listdir(dir_superior)) > 1):
    diretorio_anterior = os.listdir(dir_superior)[-2]
    diretorio_anterior = dir_superior + "\\" + diretorio_anterior
    ofx_anterior = get_name_ofx(diretorio_anterior)


# Carrega o arquivo OFX antigo
with open('./ofx-example/extratoITAU.ofx', 'rb') as arquivo_ofx_antigo:
    ofx_antigo = OfxParser.parse(arquivo_ofx_antigo)

# Coleta todos os checknum (identificadores) do arquvio antigo
list_checknum_antigo = []
for transacao in ofx_antigo.account.statement.transactions:
    list_checknum_antigo.append(transacao.checknum)

# Passar por todas as transações atuais
todas_transactions_atual = ofx_atual.account.statement.transactions
len_transactions = len(todas_transactions_atual)

for idx in range(len_transactions):
    if (todas_transactions_atual[idx].checknum in list_checknum_antigo):
        todas_transactions_atual.pop(idx)
        idx -= 1
