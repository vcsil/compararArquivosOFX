# -*- coding: utf-8 -*-
"""ComparaOFX: terminal e seleção, com imports de processamento tardios."""
import sys
import os
from controller.user_navigation import Cancelado, selecionar
from controller.organization import raiz_aplicacao, instituicoes


def main(raiz=None, entrada=None, saida=None):
    entrada = entrada or input
    saida = saida or print
    try:
        raiz = raiz_aplicacao(raiz)
        saida('COMPARAOFX 2.0')
        from controller.safe_storage import pendencias, bloquear, recuperar_concluida
        from controller.organization import OrganizacaoError
        pendencias_nao_resolvidas = False
        for banco_pendente in instituicoes(raiz):
            if pendencias(banco_pendente):
                try:
                    with bloquear(banco_pendente):
                        recuperar_concluida(banco_pendente)
                    saida('Registro concluído recuperado: ' + banco_pendente.name)
                except OrganizacaoError:
                    pendencias_nao_resolvidas = True
                    saida('Operação pendente exige inspeção: ' + banco_pendente.name)
        selecao = selecionar(raiz, entrada, saida)
        if selecao is None:
            return 1 if pendencias_nao_resolvidas else 0
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

        from controller.safe_storage import bloquear, exigir_sem_pendencias, recuperar_concluida
        with bloquear(banco) as token:
            recuperar_concluida(banco)
            exigir_sem_pendencias(banco)
            plano = planejar(raiz, banco, arquivo, anexos, leitor=ler)
            rel = plano.resultado.relatorio
            saida(f'{rel.estado}: originais {rel.original.quantidade}; anteriores {rel.anteriores.quantidade}; duplicatas {rel.duplicatas.quantidade}; novas {rel.novas.quantidade}')
            saida(f'Créditos {rel.novas.creditos}; débitos {rel.novas.debitos}; líquido {rel.novas.liquido}')
            for aviso in rel.divergencias_memo:
                saida(aviso)
            destino = executar(plano, bloqueio=token)
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
    resultado = main()
    # Em console interativo a janela aberta por duplo clique deve permanecer
    # visível; pipes e testes automatizados nunca ficam aguardando esta pausa.
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            input('Pressione Enter para sair.')
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(resultado)
