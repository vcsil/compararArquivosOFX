# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 12:03:33 2023

@author: vsil
"""

from ofxtools.Parser import OFXTree
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime
import os


def carregar_ofx(ofx_dir):
    parser = OFXTree()
    with open(ofx_dir, 'rb') as arquivo_ofx:
        parser.parse(arquivo_ofx)
        headers = str(parser.header).replace("\r\n", "\n")

        ofx = parser.convert()
        return headers, ofx


def pegar_dia_insterseccao(ofx, ultimo_dia_ofx_anterior):
    # Pegar o dia de intersecção entre os ofx
    qnt_transacoes = len(ofx.statements[0].transactions)

    for idx in range(qnt_transacoes):
        transacao = ofx.statements[0].transactions[idx]
        data = transacao.dtposted.strftime("%Y-%m-%d")

        if (data == ultimo_dia_ofx_anterior):
            return data

        elif (idx == (qnt_transacoes-1)):
            raise FileExistsError("Não há uma intersecção da datas entre esses arquivos para fazer a comparação de transação.")


def pegar_infos_transacoes(ofx, data_interseccao):
    # Passar pelas transações do ofx que pertencem a data de intersecção
    infos_transacoes = []

    for transacao in ofx.statements[0].transactions:
        dia_transacao = transacao.dtposted.strftime("%Y-%m-%d")

        # Verifica se transação é do mesmo dia
        if (data_interseccao == dia_transacao):
            informacoes = [(transacao.memo, transacao.trnamt), transacao.fitid]
            infos_transacoes.append(informacoes)

    return infos_transacoes


def remove_transacao(ofx, identificador):
    for idx in range(len(ofx.statements[0].transactions)):
        transacao = ofx.statements[0].transactions[idx]

        if (transacao.fitid == identificador):
            ofx.statements[0].transactions.pop(idx)
            return ofx

    raise ValueError(f"Não foi possível encontrar a trasação de id: {identificador}")


def remove_anteriores(ofx, data_interseccao):
    # Pega esse formato para comparar se é antes ou depois
    data_interseccao = datetime.strptime(data_interseccao, "%Y-%m-%d")

    lista_anteriores = []

    # Passa pelas transições anteriores e salva informações
    for transacao in ofx.statements[0].transactions:
        data_transacao = transacao.dtposted.strftime("%Y-%m-%d")
        data_transacao = datetime.strptime(data_transacao, "%Y-%m-%d")

        if (data_transacao < data_interseccao):
            lista_anteriores.append([transacao.checknum, transacao.memo])

        elif (data_transacao == data_interseccao):
            print(f'\n{len(lista_anteriores)} transações de dia anteriores removidas\n')
            break

    # Remove as transações de dias anteriores do OFX
    for transacao_checknum, transacao_memo in lista_anteriores:
        for idx in range(len(ofx.statements[0].transactions)):
            transacao = ofx.statements[0].transactions[idx]
            mesmo_checknum = transacao_checknum == transacao.checknum
            mesmo_memo = transacao_memo == transacao.memo

            if (mesmo_checknum and mesmo_memo):
                ofx.statements[0].transactions.pop(idx)
                break

    return ofx


def salvar_ofx(ofx, headers, diretorio, nome=""):
    # Aproxima de XML
    ofx = ofx.to_etree()
    # Converte para bytes
    ofx = ET.tostring(ofx)
    # Converte para string
    ofx = ofx.decode()

    # Analisar o arquivo XML
    ofx = xml.dom.minidom.parseString(ofx)
    # Indentar o XML
    ofx = ofx.toprettyxml(indent="\t")[23:]
    # Adiciona Header
    ofx = headers + ofx

    # Salvar o XML indentado em um novo arquivo
    if (nome == ""):
        nome_arq = "\\OFX Limpo-" + datetime.now().strftime("%d%m%Y%H%M") + ".ofx"
    else:
        nome_arq = "\\" + nome

    with open(diretorio+nome_arq, 'w') as file:
        file.write(ofx)

    return diretorio+nome_arq


def salvar_ofx_geral(ofx, header, diretorio_atual):
    split_dir_atual = diretorio_atual.split("\\")
    diretorio_anterior = "\\".join(split_dir_atual[:-1])

    for item in os.listdir(diretorio_anterior):
        # Procura o arquivo OFX geral com todas as transações do dia
        if ((".ofx" in item) and (f"OFXGeral-{split_dir_atual[-2]}" in item)):
            diretorio_arq_ofx = diretorio_anterior + "\\" + item
            header_geral, ofx_geral = carregar_ofx(diretorio_arq_ofx)

            # Adiciona as novas transaçoes ao arquivo geral de transações
            ofx_geral = junta_transacoes(ofx_geral, ofx)

            # Salva arquivo atualizado
            return salvar_ofx(ofx_geral, header_geral, diretorio_anterior, item)

    # Caso não tenho o OFX geral vai criar.
    return salvar_ofx(ofx, header, diretorio_anterior, f"OFXGeral-{split_dir_atual[-2]}.ofx")


def junta_transacoes(ofx_geral, ofx_dia):
    for transacao_nova in ofx_dia.statements[0].transactions:
        ofx_geral.statements[0].transactions.append(transacao_nova)

    return ofx_geral
