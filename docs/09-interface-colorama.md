# Interface Colorama do ComparaOFX 2.0

A interface antiga usava Colorama para menus e resultados, mas misturava cores com instituições fixas e a lógica financeira. A versão 2.0 retoma destaques sem recuperar o processamento antigo nem fixar bancos: instituições e arquivos continuam descobertos e ordenados dinamicamente.

`controller.terminal_style` concentra a paleta e a detecção de saída. Títulos são azul brilhante; cabeçalhos ciano brilhante; números de opções e avisos amarelos; conclusão e valores positivos verdes; erros, bloqueios e valores negativos vermelhos. Valores neutros e nomes mantêm a cor padrão. O relatório usa os `Decimal` já calculados, sem arredondamento, e chama o líquido de **líquido das novas**, não saldo bancário. Sucesso de publicação só aparece após `executar()` retornar.

Exemplo sem cores (o terminal interativo apresenta os destaques correspondentes):

```text
COMPARAOFX 2.0
----------------------------
Arquivo selecionado: extrato.ofx
Selecione a instituição:
01 - Banco A
02 - Banco B
00 - Cancelar
Instituição escolhida: Banco A
Anexos selecionados: 0 - nenhum
Relatório financeiro
Estado: PRIMEIRA_IMPORTACAO
  Transações originais    : 1
  Transações anteriores   : 0
  Duplicatas              : 0
  Transações novas        : 1
  Total de créditos       : 20.00
  Total de débitos        : 0
  Líquido das novas       : 20.00
```

As cores só são produzidas quando o destino é o `print` padrão, `stdout` é terminal, `TERM` não é `dumb`, e `NO_COLOR` e `CI` não estão presentes. A mera presença de `NO_COLOR`, inclusive vazio, desativa cores. Callbacks, listas, arquivos, pipes, testes e CI não recebem ANSI. A inicialização única usa `colorama.just_fix_windows_console()` apenas quando a cor é permitida, sem configuração permanente no Windows. Em consoles antigos Colorama pode adaptar a saída conforme seu suporte; é necessária uma sessão real para verificar as cores visualmente.

## Testes e homologação

A suíte local Linux executou 158 testes: quatro ignorados por plataforma e sete falhas históricas esperadas, sem falhas inesperadas. Testes cobrem cores, callbacks, `NO_COLOR`, redirecionamento, inicialização, navegação, cancelamento, entrada inválida, Decimal exato e bloqueio sem mensagem de sucesso. O smoke do executável verifica também cabeçalho e menu sem ANSI em pipe; o smoke financeiro continua verificando preservação byte a byte, deduplicação, conflitos e recuperação v1/v2. A auditoria exige que Colorama esteja no pacote e continua bloqueando testes e ferramentas próprios.

Como o runner captura saída e não comprova visualmente uma sessão de console, homologue o artefato Nuitka onefile em um Windows Terminal e no console tradicional: coloque o executável numa pasta de testes com uma instituição e OFX sintético; abra-o por duplo clique, confira cores, índices, seleção e cancelamento; repita com `NO_COLOR` presente e confirme apresentação sem cores. Confira o ícone azul e faça a importação em uma pasta descartável. Não são necessários Python ou configuração permanente para executar o candidato.

## Builds e comparação

Os resultados do workflow Windows, hashes, tamanhos e comparação no mesmo runner serão registrados após sua conclusão. A baseline é recompilada a partir de `993a0cd` com a mesma versão de Nuitka; não é o mesmo binário anterior byte a byte. Os artefatos são candidatos de teste sem assinatura digital; não são uma release.
