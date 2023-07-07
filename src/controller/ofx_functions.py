# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 12:03:33 2023

@author: vsil
"""

from ofxtools.Parser import OFXTree
def carregar_ofx(ofx_dir):
    parser = OFXTree()
    with open(ofx_dir, 'rb') as arquivo_ofx:
        parser.parse(arquivo_ofx)
        headers = str(parser.header).replace("\r\n", "\n")

        ofx = parser.convert()
        return headers, ofx
def pegar_dia_insterseccao(ofx, ultimo_dia_ofx_anterior):
    # Pegar o dia de intersecção entre os ofx
    qnt_transacoes = len(ofx.account.statement.transactions)

    for idx in range(qnt_transacoes):
        transacao = ofx.account.statement.transactions[idx]
        data = transacao.date.strftime("%Y-%m-%d")

        if (data == ultimo_dia_ofx_anterior):
            return data

        elif (idx == qnt_transacoes):
            raise FileExistsError("Não há uma intersecção da datas entre esses arquivos para fazer a comparação de transação.")


def pegar_infos_transacoes(ofx, data_interseccao):
    # Passar pelas transações do ofx que pertencem a data de intersecção
    infos_transacoes = []

    for transacao in ofx.account.statement.transactions:
        dia_transacao = transacao.date.strftime("%Y-%m-%d")

        # Verifica se transação é do mesmo dia
        if (data_interseccao == dia_transacao):
            informacoes = [(transacao.memo, transacao.amount), transacao.id]
            infos_transacoes.append(informacoes)
        elif (data_interseccao < dia_transacao):
            break

    return infos_transacoes


def remove_transacao(ofx, identificador):
    for idx in range(len(ofx.account.statement.transactions)):
        transacao = ofx.account.statement.transactions[idx]

        if (transacao.id == identificador):
            ofx.account.statement.transactions.pop(idx)
            return ofx

    raise ValueError(f"Não foi possível encontrar a trasação de id: {identificador}")
