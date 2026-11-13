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

Um pseudo-terminal Linux real confirmou cores ativas, ausência delas com `NO_COLOR` vazio, menu e cancelamento. Um PyInstaller Linux também passou no inventário com Colorama e no smoke financeiro v1/v2; esses testes não substituem a validação Windows. O smoke Windows remove `PYTHONPATH` e `PYTHONHOME` e restringe `PATH` a System32, além de conferir que os OFX gerados não recebem ANSI.

Como o runner captura saída e não comprova visualmente uma sessão de console, homologue o artefato Nuitka onefile em um Windows Terminal e no console tradicional: coloque o executável numa pasta de testes com uma instituição e OFX sintético; abra-o por duplo clique, confira cores, índices, seleção e cancelamento; repita com `NO_COLOR` presente e confirme apresentação sem cores. Confira o ícone azul e faça a importação em uma pasta descartável. Não são necessários Python ou configuração permanente para executar o candidato.

## Builds e comparação

O [workflow Windows 43512246781](https://github.com/vcsil/compararArquivosOFX/actions/runs/43512246781), commit `df7443e`, aprovou as suítes e os builds PyInstaller onefile, Nuitka standalone e Nuitka onefile. Os três passaram no smoke, na verificação do ícone azul, na auditoria e na verificação de assinatura ausente. O artefato `comparaofx-nuitka-candidate` contém o onefile para testes e fica disponível por sete dias no workflow.

| Candidato | Tamanho do executável | SHA-256 |
|---|---:|---|
| Nuitka onefile | 8.084.992 bytes | `f90f2d7c6bcd183f2ed0f385dfbdb9eccc9286ddc295b14cb9ea4a080093de3f` |
| Nuitka standalone | 12.496.896 bytes | `6f83c7e13baca10a90854857ae1f18b8d097266ac8aa5aedfb62eb741a413bae` |
| PyInstaller onefile | 9.831.801 bytes | `d72e33ac2b0bc8b5256cb414fd1cbc05426cb9e1ebb3b4a0c1eb6622c971e9d7` |

O standalone contém 22 arquivos, totalizando 28.302.696 bytes. O Defender registrou verificações sem detecção associada nos três candidatos, usando a versão de assinaturas `1.463.286.0`; isso não resolve o alerta histórico `Program:Win32/Contebrew.A!ml` nem prova ausência de malware. Os três executáveis são não assinados.

O inventário PyInstaller contém 237 módulos, e os relatórios Nuitka listam 459 cada; incluem os seis módulos Colorama e não incluem `tests/`, scripts próprios, `unittest`, pytest, Pillow ou pefile nos itens examinados. Listas completas, recuperadas das anotações e verificadas por SHA-256: [PyInstaller](inventarios/09-pyinstaller-onefile-windows.json), [Nuitka standalone](inventarios/09-nuitka-standalone-windows.json) e [Nuitka onefile](inventarios/09-nuitka-onefile-windows.json).

Todos os jobs, inclusive a comparação, terminaram com sucesso. Comparação no mesmo runner Windows, CPU AMD EPYC 7763 e Python 3.12.10; a baseline foi reconstruída a partir de `993a0cd`. Os tempos são sequenciais e não isolados de carga. Inicialização: mediana de 15 execuções aquecidas; 100 e 1.000 transações: mediana de três; 10.000: somente uma execução, insuficiente para estimar dispersão.

| Nuitka onefile | Bytes | Início até menu (ms) | 100 transações (ms) | 1.000 transações (ms) | 10.000 transações (ms, n=1) |
|---|---:|---:|---:|---:|---:|
| Baseline recompilada | 8.005.120 | 392,263 | 1.086,773 | 4.561,539 | 38.782,107 |
| Colorama | 8.084.992 | 414,334 | 1.265,301 | 4.540,078 | 38.942,589 |

O candidato cresceu 79.872 bytes; nessa amostra, a mediana de 100 transações subiu aproximadamente 16%, enquanto 1.000 e 10.000 ficaram próximos. As poucas execuções, a ordem sequencial e a variação observada impedem atribuir causalidade ou excluir uma regressão pequena. O hash da baseline recompilada foi `ac6ced82feebc17b889c1aeaadd088b76344c31276c0a2c6d8db39a49abde7bf`; ela não é byte a byte o binário anterior. O workflow contém também as medições dos outros formatos. A baseline é recompilada a partir de `993a0cd` com a mesma versão de Nuitka; não é o mesmo binário anterior byte a byte. Os artefatos são candidatos de teste sem assinatura digital; não são uma release.
