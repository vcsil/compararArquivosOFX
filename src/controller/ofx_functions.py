# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 12:03:33 2023

@author: vsil
"""


def pegar_dia_insterseccao(ofx, ultimo_dia_ofx_anterior):
    # Pegar o dia de intersecção do ofx atual
    qnt_transacoes_tual = len(ofx.account.statement.transactions)

    for idx in range(qnt_transacoes_tual):
        transacao = ofx.account.statement.transactions[idx]
        data = transacao.date.strftime("%Y-%m-%d")

        if (data == ultimo_dia_ofx_anterior):
            return data

        elif (idx == qnt_transacoes_tual):
            raise FileExistsError("Não há uma intersecção da datas entre esses arquivos para fazer a comparação de transação.")


def pegar_infos_transacoes(ofx, data_interseccao):
    # Passar por todas transações do ofx atual que pertencem a data de intersecção
    infos_transacoes_atual = []

    for transacao in ofx.account.statement.transactions:
        dia_transacao_atual = transacao.date.strftime("%Y-%m-%d")
        # Verifica se transação é do mesmo dia
        if (data_interseccao == dia_transacao_atual):
            infos_transacoes_atual.append((transacao.memo, transacao.amount, transacao.id))
        elif (data_interseccao < dia_transacao_atual):
            break

    return infos_transacoes_atual
