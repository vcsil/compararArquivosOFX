# -*- coding: utf-8 -*-
"""ComparaOFX: terminal e seleção, com imports de processamento tardios."""
import sys
import os
from controller.user_navigation import Cancelado, selecionar
from controller.organization import raiz_aplicacao, instituicoes
from controller.terminal_style import Terminal, relatorio_financeiro


def main(raiz=None, entrada=None, saida=None):
    entrada = entrada or input
    saida = saida or print
    tela = Terminal(saida)
    try:
        raiz = raiz_aplicacao(raiz)
        tela.texto('COMPARAOFX 2.0', 'titulo')
        tela.texto('----------------------------', 'cabecalho')
        from controller.safe_storage import pendencias, bloquear, recuperar_concluida
        from controller.organization import OrganizacaoError
        pendencias_nao_resolvidas = False
        for banco_pendente in instituicoes(raiz):
            if pendencias(banco_pendente):
                try:
                    with bloquear(banco_pendente):
                        recuperar_concluida(banco_pendente)
                    tela.texto('Registro concluído recuperado: ' + banco_pendente.name, 'sucesso')
                except OrganizacaoError:
                    pendencias_nao_resolvidas = True
                    tela.texto('Operação pendente exige inspeção: ' + banco_pendente.name, 'aviso')
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
                tela.texto(f'Codificação ambígua em {caminho.name}: declarado Windows-1252, também válido em UTF-8.', 'aviso')
                while True:
                    resposta = entrada('1 - UTF-8; 2 - Windows-1252; 0 - cancelar: ').strip()
                    if resposta == '0':
                        raise Cancelado()
                    if resposta in ('1','2'):
                        return carregar_ofx(caminho, codificacao='utf-8' if resposta == '1' else 'cp1252')
                    tela.texto('Entrada inválida.', 'aviso')

        from controller.safe_storage import bloquear, exigir_sem_pendencias, recuperar_concluida
        with bloquear(banco) as token:
            recuperar_concluida(banco)
            exigir_sem_pendencias(banco)
            plano = planejar(raiz, banco, arquivo, anexos, leitor=ler)
            rel = plano.resultado.relatorio
            relatorio_financeiro(rel, tela)
            for aviso in rel.divergencias_memo:
                tela.texto(aviso, 'aviso')
            destino = executar(plano, bloqueio=token)
        tela.texto(f'Arquivos organizados em: {destino}', 'sucesso')
        return 0
    except Cancelado:
        tela.texto('Operação cancelada.', 'aviso')
        return 0
    except (OSError, ValueError) as exc:
        if os.environ.get('COMPARAOFX_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        tela.texto(f'Operação interrompida: {exc}', 'erro')
        return 1
    except Exception:
        if os.environ.get('COMPARAOFX_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        tela.texto('Operação interrompida: falha ao processar o arquivo OFX.', 'erro')
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
