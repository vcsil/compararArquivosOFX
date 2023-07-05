# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vinic
"""

from controller.browse_folders import get_name_ofx, get_old_directory
from controller.user_navigation import escolher_instituicao_finan
from ofxparse import OfxParser


# Pega o diretório atual
dir_atual = escolher_instituicao_finan()  # os.getcwd()

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
