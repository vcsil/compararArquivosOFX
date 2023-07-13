# -*- coding: utf-8 -*-
"""
Created on Thu Apr 13 11:47:17 2023

@author: vsil
"""

from controller.browse_folders import get_name_ofx, get_old_directory
from controller.user_navigation import define_diretorio
from controller.ofx_functions import carregar_ofx
from controller.ofx_functions import pegar_dia_insterseccao
from controller.ofx_functions import pegar_infos_transacoes
from controller.ofx_functions import remove_transacao
from controller.ofx_functions import remove_anteriores
from controller.ofx_functions import salvar_ofx

from colorama import init, Style, Back

init()

# Pega o diretório atual
dir_atual = define_diretorio()  # os.getcwd()

# Identifica o arquivo ofx no diretório atual
ofx_atual = get_name_ofx(dir_atual)

# Vai buscar o arquivo ofx anterior imediado (da ultima data atualiazada)
ofx_anterior = get_old_directory(dir_atual)

# Carrega o arquivo OFX atual e ordena as transações pelo dia, crescente
header_atual, ofx_atual = carregar_ofx(ofx_atual)
ofx_atual.statements[0].transactions.sort(key=lambda x: x.dtposted)

# Carrega o arquivo OFX anterior e ordena as transações pelo dia, crescente
header_anterior, ofx_anterior = carregar_ofx(ofx_anterior)
ofx_anterior.statements[0].transactions.sort(key=lambda x: x.dtposted)

# Pegar o dia na ultima transação do ofx anterior
ultimo_dia_ofx_anterior = ofx_anterior.statements[0].transactions[-1]
ultimo_dia_ofx_anterior = ultimo_dia_ofx_anterior.dtposted.strftime("%Y-%m-%d")

# Pegar o dia de intersecção entre os ofx
data_interseccao = pegar_dia_insterseccao(ofx_atual, ultimo_dia_ofx_anterior)

# Removar transações anteriores ao da data de intersecção
ofx_atual = remove_anteriores(ofx_atual, data_interseccao)

# Pegar transações do ofx atual que pertencem a data de intersecção
inf_transacoes_atual = pegar_infos_transacoes(ofx_atual, data_interseccao)

# Pegar transações do ofx anterior que pertencem a data de intersecção
inf_transacoes_anterior = pegar_infos_transacoes(ofx_anterior, data_interseccao)

# Quantidade de transações a mais
diferenca_transacoes = len(inf_transacoes_atual) - len(inf_transacoes_anterior)

print(f"Quantidade da transações ofx anterior (a ser removida): {len(inf_transacoes_anterior)}")
print(f"Quantidade da transações ofx atual: {len(inf_transacoes_atual)}\n")
print(f"Diferença no total de transações (a ficar): {diferenca_transacoes}\n")

# Passar por todas as transações do ofx anterior na data de intersecção
transacoes_removidas = 0
for transacao_anterior, _ in inf_transacoes_anterior:

    for transacao_nova, identificador in inf_transacoes_atual:
        if (transacao_anterior == transacao_nova):
            # Remove transacao da array auxiliar
            inf_transacoes_atual.remove([transacao_nova, identificador])

            # Remove transacao do ofx
            ofx_atual = remove_transacao(ofx_atual, identificador)
            transacoes_removidas += 1

if (transacoes_removidas == len(inf_transacoes_anterior)):
    print(Back.GREEN + f"Transações removidas do ofx atual: {transacoes_removidas}\n" + Style.RESET_ALL)
else:
    print(Back.RED + f"Transações removidas do ofx atual: {transacoes_removidas}\n" + Style.RESET_ALL)

salvar_ofx(ofx_atual, header_atual, dir_atual)
