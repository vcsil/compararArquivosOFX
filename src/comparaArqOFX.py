# -*- coding: utf-8 -*-
"""ComparaOFX: terminal e seleção, com imports de processamento tardios."""
import sys
import os
from controller.user_navigation import Cancelado, selecionar
from controller.organization import raiz_aplicacao


def main(raiz=None, entrada=None, saida=None):
    entrada = entrada or input
    saida = saida or print
    try:
        raiz = raiz_aplicacao(raiz)
        saida('COMPARAOFX 2.0')
        selecao = selecionar(raiz, entrada, saida)
        if selecao is None:
            return 0
        banco, arquivo, anexos = selecao
        from controller.ofx_functions import carregar_ofx
        from controller.ofx_io import OFXEncodingAmbiguaError
        from controller.workflow import planejar, executar

        def ler(caminho):
            try:
                return carregar_ofx(caminho)
            except OFXEncodingAmbiguaError:
                saida(f'Codificação ambígua em {caminho.name}: declarado Windows-1252, também válido em UTF-8.')
                while True:
                    resposta = entrada('1 - UTF-8; 2 - Windows-1252; 0 - cancelar: ').strip()
                    if resposta == '0':
                        raise Cancelado()
                    if resposta in ('1','2'):
                        return carregar_ofx(caminho, codificacao='utf-8' if resposta == '1' else 'cp1252')
                    saida('Entrada inválida.')

        plano = planejar(raiz, banco, arquivo, anexos, leitor=ler)
        rel = plano.resultado.relatorio
        saida(f'{rel.estado}: originais {rel.original.quantidade}; anteriores {rel.anteriores.quantidade}; duplicatas {rel.duplicatas.quantidade}; novas {rel.novas.quantidade}')
        saida(f'Créditos {rel.novas.creditos}; débitos {rel.novas.debitos}; líquido {rel.novas.liquido}')
        for aviso in rel.divergencias_memo:
            saida(aviso)
        destino = executar(plano)
        saida(f'Arquivos organizados em: {destino}')
        return 0
    except Cancelado:
        saida('Operação cancelada.')
        return 0
    except (OSError, ValueError) as exc:
        if os.environ.get('COMPARAOFX_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        saida(f'Operação interrompida: {exc}')
        return 1
    except Exception:
        if os.environ.get('COMPARAOFX_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        saida('Operação interrompida: falha ao processar o arquivo OFX.')
        return 1

if __name__ == '__main__':
    sys.exit(main())
