# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 12:03:33 2023

@author: vsil
"""

from ofxtools.Parser import OFXTree
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime


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
        elif (data_interseccao < dia_transacao):
            break

    return infos_transacoes


def remove_transacao(ofx, identificador):
    for idx in range(len(ofx.statements[0].transactions)):
        transacao = ofx.statements[0].transactions[idx]

        if (transacao.fitid == identificador):
            ofx.statements[0].transactions.pop(idx)
            return ofx

    raise ValueError(f"Não foi possível encontrar a trasação de id: {identificador}")


def salvar_ofx(ofx, headers, diretorio):
    # Aproxima de XML
    ofx = ofx.to_etree()
    # Converte para bytes
    ofx = ET.tostring(ofx)
    # Converte para string
    ofx = ofx.decode()

    # Analisar o arquivo XML
    ofx = xml.dom.minidom.parseString(ofx)
    # Indentar o XML
    ofx = ofx.toprettyxml(indent="\t")
    # Adiciona Header
    ofx = headers + ofx

    # Salvar o XML indentado em um novo arquivo
    nome_arq = "\\Extrato Limpo-" + datetime.now().strftime("%m%d%Y%H%M") + ".ofx" 
    with open(diretorio+nome_arq, 'w') as file:
        file.write(ofx)
