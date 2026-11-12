# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 12:03:33 2023

@author: vsil
"""

from .ofx_io import preparar_ofx, interpretar_ofx, serializar_ofx
from datetime import datetime
import os


def carregar_ofx(ofx_dir, *, codificacao=None):
    with open(ofx_dir, 'rb') as arquivo_ofx:
        formato, headers, corpo = preparar_ofx(arquivo_ofx.read(), codificacao=codificacao)
    ofx = interpretar_ofx(formato, corpo)
    ofx._caminho_origem = os.path.abspath(ofx_dir)
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


def salvar_ofx(ofx, headers, diretorio, nome="", *, _permitir_atualizar_historico=False):
    # A saída usa OFX 2.03/UTF-8 independentemente do cabeçalho de entrada.
    conteudo = serializar_ofx(ofx)
    if nome == "":
        nome = "OFX Limpo-" + datetime.now().strftime("%d%m%Y%H%M") + ".ofx"
    caminho = os.path.join(diretorio, nome)
    origem = getattr(ofx, '_caminho_origem', None)
    if origem and not _permitir_atualizar_historico:
        igual = os.path.realpath(origem) == os.path.realpath(caminho)
        if not igual and os.path.exists(caminho):
            igual = os.path.samefile(origem, caminho)
        if igual:
            raise ValueError('O arquivo de origem não pode ser sobrescrito')
    if not _permitir_atualizar_historico and os.path.exists(caminho):
        raise FileExistsError('O arquivo de destino já existe')
    modo = 'wb' if _permitir_atualizar_historico else 'xb'
    with open(caminho, modo) as file:
        file.write(conteudo)
    return caminho


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
            return salvar_ofx(ofx_geral, header_geral, diretorio_anterior, item, _permitir_atualizar_historico=True)

    # Caso não tenho o OFX geral vai criar.
    return salvar_ofx(ofx, header, diretorio_anterior, f"OFXGeral-{split_dir_atual[-2]}.ofx")


def junta_transacoes(ofx_geral, ofx_dia):
    for transacao_nova in ofx_dia.statements[0].transactions:
        ofx_geral.statements[0].transactions.append(transacao_nova)

    return ofx_geral
