# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vinic
"""

from ofxparse import OfxParser


# Carrega o arquivo OFX antigo
with open('./ofx-example/extratoITAU.ofx', 'rb') as arquivo_ofx_antigo:
    ofx_antigo = OfxParser.parse(arquivo_ofx_antigo)

# Carrega o arquivo OFX atual
with open('./ofx-example/extratoBB.ofx', 'rb') as arquivo_ofx_atual:
    ofx_atual = OfxParser.parse(arquivo_ofx_atual)

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
        idx -= 1;