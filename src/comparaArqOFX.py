# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vinic
"""

from ofxparse import OfxParser
from controller.browse_folders import get_name_ofx, get_old_directory


# Pega o diretório atual
dir_atual = "C:\\Users\\vinic\\Downloads\\repositorios\\compararArquivosOFX\\ofx-example\\Extrato\\Itau\\2023\\04 - Abr 2023\\2023-04-26\\03" # os.getcwd()

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
