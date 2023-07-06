# -*- coding: utf-8 -*-
"""
Created on Tue Jul  4 17:29:53 2023

@author: vsil
"""

from datetime import datetime, timezone, timedelta
import os
from colorama import init, Fore, Style

init()

timezone_offset = -3.0  # UTC (-3) Brasil
tzinfo = timezone(timedelta(hours=timezone_offset))

dict_inst_financeira = {"1": "Banco do Brasil",
                        "2": "Itau",
                        "3": "PagSeguro"}

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


def escolher_instituicao_finan():
    print(Style.BRIGHT + "Informe a instituição financeira:\n")
    print(Fore.YELLOW + "01 - Banco do Brasil")
    print(Fore.RED + "02 - Itaú")
    print(Fore.GREEN + "03 - PagSeguro")
    print(Style.RESET_ALL + "04 - Informe outro")
    print("-"*36 + "\n")

    inst_finan = input()

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
