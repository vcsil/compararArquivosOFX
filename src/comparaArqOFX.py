# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vsil
"""

from controller.browse_folders import get_name_ofx, get_old_directory
from controller.user_navigation import escolher_instituicao_finan
from controller.ofx_functions import pegar_dia_insterseccao
from controller.ofx_functions import pegar_infos_transacoes

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

# Pegar o dia na ultima transação do ofx anterior
ultimo_dia_ofx_anterior = ofx_anterior.account.statement.transactions[-1]
ultimo_dia_ofx_anterior = ultimo_dia_ofx_anterior.date.strftime("%Y-%m-%d")

# Pegar o dia de intersecção do ofx atual
data_interseccao = pegar_dia_insterseccao(ofx_atual, ultimo_dia_ofx_anterior)

# Passar por todas transações do ofx atual que pertencem a data de intersecção
infos_transacoes_atual = pegar_infos_transacoes(ofx_atual, data_interseccao)

for idx in range(len_transactions):
    if (todas_transactions_atual[idx].checknum in list_checknum_anterior):
        todas_transactions_atual.pop(idx)
        idx -= 1
