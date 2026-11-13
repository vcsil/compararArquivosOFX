"""Apresentação do terminal, sem cor para callbacks e saídas redirecionadas."""
import builtins
import os
import sys
from colorama import Fore, Style, just_fix_windows_console

_PALETA = {
    'titulo': Style.BRIGHT + Fore.BLUE,
    'cabecalho': Style.BRIGHT + Fore.CYAN,
    'opcao': Fore.YELLOW,
    'sucesso': Fore.GREEN,
    'aviso': Fore.YELLOW,
    'erro': Fore.RED,
    'informacao': Fore.CYAN,
}
_inicializado = False


def formatar(texto, tipo, habilitado=False):
    """Formata sem converter valores financeiros ou modificar a saída."""
    return _PALETA[tipo] + str(texto) + Style.RESET_ALL if habilitado else str(texto)


class Terminal:
    def __init__(self, saida):
        global _inicializado
        self.saida = saida
        self.colorido = (saida is builtins.print and 'NO_COLOR' not in os.environ
                         and 'CI' not in os.environ and os.environ.get('TERM') != 'dumb'
                         and bool(getattr(sys.stdout, 'isatty', lambda: False)()))
        if self.colorido and not _inicializado:
            just_fix_windows_console()
            _inicializado = True

    def texto(self, texto, tipo='informacao'):
        self.saida(formatar(texto, tipo, self.colorido))

    def opcao(self, numero, nome):
        self.saida(formatar(f'{numero:02}', 'opcao', self.colorido) + ' - ' + nome)


def relatorio_financeiro(rel, terminal):
    """Mostra os valores já calculados; não altera nem arredonda Decimals."""
    terminal.texto('Relatório financeiro', 'cabecalho')
    tipo = 'erro' if rel.estado == 'BLOQUEADO' else 'aviso' if rel.estado == 'SEM_NOVIDADES' else 'informacao'
    terminal.texto(f'Estado: {rel.estado}', tipo)
    for nome, valor in (('Transações originais', rel.original.quantidade),
                        ('Transações anteriores', rel.anteriores.quantidade),
                        ('Duplicatas', rel.duplicatas.quantidade),
                        ('Transações novas', rel.novas.quantidade)):
        terminal.saida(f'  {nome:<24}: {valor}')
    for nome, valor in (('Total de créditos', rel.novas.creditos),
                        ('Total de débitos', rel.novas.debitos),
                        ('Líquido das novas', rel.novas.liquido)):
        tipo = 'sucesso' if valor > 0 else 'erro' if valor < 0 else 'informacao'
        terminal.texto(f'  {nome:<24}: {valor}', tipo)
