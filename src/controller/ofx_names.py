"""Nomes de saída e compatibilidade explícita dos manifestos de recuperação."""
from datetime import datetime
import re

LEGADO_LIMPO = 'OFX Limpo.ofx'


def validar_nome_limpo(nome):
    if not isinstance(nome, str) or re.fullmatch(r'OFX Limpo-[0-9]{12}\.ofx', nome) is None:
        raise ValueError('Nome do OFX Limpo inválido')
    # Além do formato ASCII exato, rejeitar datas e horários impossíveis.
    datetime.strptime(nome[10:-4], '%d%m%Y%H%M')
    return nome


def nome_limpo_manifesto(manifesto):
    versao = manifesto['versao']
    if type(versao) is not int:
        raise ValueError('Versão de manifesto inválida')
    if versao == 1:
        if manifesto.get('limpo_nome', LEGADO_LIMPO) != LEGADO_LIMPO:
            raise ValueError('Nome incompatível com manifesto legado')
        nome = LEGADO_LIMPO
    elif versao == 2:
        nome = validar_nome_limpo(manifesto['limpo_nome'])
    else:
        raise ValueError('Versão de manifesto não suportada')
    digest = manifesto['limpo_hash']
    if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('SHA-256 do OFX Limpo inválido')
    return nome


def eh_nome_limpo(nome, *, legado=True):
    if legado and nome == LEGADO_LIMPO:
        return True
    try:
        validar_nome_limpo(nome)
    except (ValueError, TypeError):
        return False
    return True
