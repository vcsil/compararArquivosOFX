# -*- coding: utf-8 -*-
"""
Created on Tue Jul  4 17:29:53 2023

@author: vsil
"""

from datetime import datetime, timezone, timedelta
import os
from colorama import init, Fore, Style, Back

init()

timezone_offset = -3.0  # UTC (-3) Brasil
tzinfo = timezone(timedelta(hours=timezone_offset))

dict_inst_financeira = {1: "Banco do Brasil",
                        2: "Itau",
                        3: "PagSeguro"}

dict_mes = {'01': "Jan",
            '02': "Fev",
            '03': "Mar",
            '04': "Abr",
            '05': "Mai",
            '06': "Jun",
            '07': "Jul",
            '08': "Ago",
            '09': "Set",
            '10': "Out",
            '11': "Nov",
            '12': "Dez"}


def define_diretorio():
    pergunta = "Diretório atual [0] ou diretorio central [1]: "
    lugar = pergunta_para_usuario(pergunta, [1, 0])

    if (lugar):
        return define_diretorio_central()
    else:
        print("Usado quando o script está em um unico arquivo python.")
        return os.getcwd()


def pergunta_para_usuario(pergunta, resp_esperada):
    # Tratar a o input do usuario
    resposta = ''
    while (resposta not in resp_esperada):
        try:
            resposta = input(pergunta)
            resposta = int(resposta)

            if (resposta not in resp_esperada):
                raise ValueError

        except ValueError:
            print(Back.RED + "Entrada errada\n" + Style.RESET_ALL)
        else:
            return resposta
            break


def define_diretorio_central():
    print(Style.BRIGHT + "Informe a instituição financeira:\n")
    print(Fore.YELLOW + "01 - Banco do Brasil")
    print(Fore.RED + "02 - Itaú")
    print(Fore.GREEN + "03 - PagSeguro")
    print(Style.RESET_ALL + "04 - Informe outro")
    print("-"*36 + "\n")

    inst_finan = pergunta_para_usuario('', [1, 2, 3, 4])

    if (inst_finan == 4):
        diretorio = input("Digite o diretório: ")
        print("\n")
        return diretorio
    else:
        diretorio = retorna_diretorio_hoje(dict_inst_financeira[inst_finan])
        print("")

    return diretorio


def retorna_diretorio_hoje(inst_financeira):
    data_agora = datetime.now(tzinfo)
    ano = data_agora.today().strftime("%Y")
    mes = data_agora.today().strftime("%m")
    dia = data_agora.today().strftime("%d")

    diretorio = "..\\" + inst_financeira + "\\" + ano + "\\"
    diretorio += mes + " - " + dict_mes[mes] + " " + ano + "\\"
    diretorio += ano + "-" + mes + "-" + dia

    ultima_pasta = os.listdir(diretorio)[-1]
    diretorio += '\\' + ultima_pasta

    return diretorio
