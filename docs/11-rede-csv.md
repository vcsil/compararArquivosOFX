# Importação CSV da Rede — ComparaOFX 2.1 (candidata)

## Objetivo

Uma pasta de instituição com nome **`Rede`** (sem prefixos ou sufixos; comparação sem distinção de maiúsculas) habilita o recebimento de relatórios **`.csv`** da Rede diretamente na raiz do executável. Não é necessário abrir o notebook nem salvar um OFX intermediário.

O restante do motor financeiro segue trabalhando com o modelo OFX já conhecido. A conversão ocorre em memória, antes de `planejar()` decidir sobre duplicatas e conflitos. O arquivo CSV original é arquivado **sem qualquer mudança nos bytes**, pela mesma transação de publicação e recuperação já usada para OFX. `OFX Limpo` e `OFXGeral` continuam em formato OFX.

CSV de outras instituições **não é aceito como extrato**. A importação de OFX segue funcionando nos demais bancos. Um CSV que não seja escolhido como entrada não será arquivado automaticamente como anexo numa importação CSV da Rede.

## Como usar

1. Coloque `ComparaOFX.exe` numa pasta dedicada e crie a subpasta `Rede`.
2. Copie o relatório da Rede, com extensão `.csv`, para a pasta do executável.
3. Execute o programa, escolha o arquivo CSV se houver mais de um extrato e selecione `Rede`.
4. Verifique o relatório e a importação. Na pasta `Rede/AAAA/MM - Mmm AAAA/AAAA-MM-DD/NNN` estarão o CSV original e o `OFX Limpo`; o `OFXGeral` fica na pasta do dia.

## Colunas e mapeamento (notebook original)

O CSV deve conter os seguintes cabeçalhos, normalizados apenas para comparação de acentos, maiúsculas e espaços:

- `Status da venda`, `Data da venda`, `Hora da venda`
- `Valor líquido`, `NSU/CV`, `Código da maquininha`
- `Meio de pagamento`, `Bandeira`, `Modalidade`, `Tipo`
- `Número de parcelas`
- Opcional: `Pré-autorizado`

Apenas registros com status **Aprovado** ou **Aprovada** entram no OFX.

| Saída OFX | Origem Rede |
|---|---|
| `FITID` | `NSU/CV - Hora da venda` (grafia textual preservada) |
| `TRNAMT` | Valor líquido convertido em Decimal |
| `DTPOSTED` | Data e hora da venda |
| `NAME` | Código da maquininha + meio de pagamento |
| `MEMO` | Bandeira + modalidade + tipo (com Pre-Auto, se indicado) + parcelas |
| `TRNTYPE` | CREDIT, para vendas aprovadas |
| `BANKID`, `ACCTID`, `CURDEF` | Identidade sintética fixa `000`, `VENDAS_REDE`, `BRL` |

O formato suporta CSV delimitado por ponto e vírgula, vírgula ou tabulação, em UTF-8 ou CP1252; o valor financeiro segue padrão brasileiro (vírgula decimal), e datas aceitam `DD/MM/AAAA` ou `AAAA-MM-DD`.

O código usa deslocamento fixo **UTC−03:00** para os horários de venda do relatório, que não informa fuso. Essa é uma premissa de negócio para os relatórios da Rede usados no Brasil, **não uma informação fornecida pelo CSV**. As operações `FITID` mantêm o formato do notebook legado, inclusive a representação original da hora.

O `LEDGERBAL` sintetizado é a soma líquida das vendas importadas, conforme o conversor anterior, **não um saldo contábil verdadeiro da conta**; não confunda o campo com o total efetivamente recebido ou a receber.

## Regras de segurança

- Colunas inválidas ou duplicadas, linhas com colunas ausentes, valores monetários inválidos e FITIDs repetidos bloqueiam a importação.
- Não inventar FITID, não alterar a data da venda, não descartar linhas aprovadas problemáticas silenciosamente.
- A entrada e o histórico são verificados por SHA-256. O arquivo CSV original é arquivado byte a byte.
- O arquivo original não é removido antes da validação das saídas, publicação e verificações.
- O processamento de CSV está limitado à instituição `Rede`; as verificações de manifesto na recuperação respeitam a mesma restrição.
- O algoritmo de deduplicação e as sete falhas históricas esperadas permanecem inalterados.
- O formato atual do notebook não garante identificador globalmente único para NSU/CV + hora em dias diferentes; conflitos são **bloqueados** em vez de juntar movimentos ambíguos.

## Validação antes do merge

Executar `python -m unittest discover -s tests -v` em Linux e Windows; recompilar PyInstaller e Nuitka, auditar módulos empacotados, verificar ícone e Colorama, rodar smoke financeiro e o smoke com CSV da Rede. Homologar um CSV sintético e um CSV real **com dados sensíveis removidos** no Windows. Não substituir `v2.0.0` nem fazer merge automático.
