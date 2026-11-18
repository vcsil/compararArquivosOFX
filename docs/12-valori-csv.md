# CSV Valori — candidata 2.1

O aplicativo reconhece o layout Valori pelo cabeçalho e oferece somente a
instituição chamada exatamente `Valori`, sem distinguir maiúsculas e minúsculas.
`Valori - Banking` mantém o fluxo OFX existente e não habilita CSV. A conversão
acontece em memória dentro do aplicativo, com o mesmo armazenamento transacional.

## Layout aceito

UTF-8 com ou sem BOM ou Windows-1252; delimitador `;`, vírgula ou tabulação quando
o cabeçalho completo identificar inequivocamente um único delimitador. CSVs sem
layout reconhecido não são extratos. Cabeçalhos duplicados, campos faltantes,
linhas incompletas e identificações simultâneas Rede/Valori bloqueiam a entrada.
Os 21 campos são obrigatórios no cabeçalho, inclusive os opcionais por registro:

| Colunas | Interpretação |
|---|---|
| Autorização | Referência opcional de cartão; não é FITID |
| Loja | Identidade textual exata do estabelecimento; obrigatória |
| POS | Terminal opcional; preservado no original e na prova de origem |
| Data de transação | Venda em `dd/mm/aaaa HH:MM:SS`; preservada no MEMO |
| Data de pagamento | Liquidação em `dd/mm/aaaa`; determina DTPOSTED |
| Bandeira | Informação obrigatória da modalidade |
| Cod. acquirer | Informação opcional do adquirente |
| Tipo compra | Crédito à Vista, Débito ou Pix |
| Parcelas | `1` para vendas simples; `2` a `99` para Parcelamento sem Juros, com parcelas individualizadas por valor líquido e prova de origem |
| Valor total bruto, Valor parcela bruto | Positivos; iguais em vendas simples. Em parcelamento, bruto total é maior que bruto por parcela |
| Valor líquido | Fonte exclusiva de TRNAMT, positivo e não superior ao bruto |
| Taxa Adm | Decimal com vírgula, informativo; unidade não inferida |
| Valor tarifa, Valor split | Explicitamente zero neste contrato |
| Status | Pago ou Pendente. Pendente aparece no OFX, mas não integra o saldo confirmado |
| NSU operação | Obrigatório; único em venda simples, compartilhado somente entre parcelas da mesma venda |
| CPF/CNPJ ecomm., Nome ecomm, Nº Pedido | Opcionais, retidos no CSV; não copiados para OFX |
| Id do Pix | Obrigatório e único no Pix; vazio em cartão |

Valores monetários usam `Decimal`, vírgula decimal e até duas casas; pontos só
como agrupadores de milhar válidos. Valores negativos, zero líquido, precisão
insuficiente para somas exatas, relações entre valores não homologadas e datas
inválidas bloqueiam o arquivo inteiro.

## Regra financeira e evidências

A finalidade é registrar **recebimentos liquidados do estabelecimento**.
`TRNAMT = Valor líquido`, `TRNTYPE = CREDIT`, inclusive para vendas na modalidade
Débito. `DTPOSTED` recebe a data civil do pagamento, sem inventar horário ou usar
a data atual. A data/hora da venda permanece no MEMO. Data de pagamento anterior
à venda bloqueia o arquivo.

Na auditoria privada, os 22 registros foram conferidos individualmente:
16 Crédito à Vista, 2 Débito, 4 Pix, todos Pago e positivos. A transação em comum
com o histórico confirmou valor líquido, sinal positivo e data de pagamento,
diferente da data da venda. Os totais do CSV, modelo e serialização foram
conservados. A evidência de equivalência histórica abrange essa correspondência;
não prova uma vinculação completa da conta nem a composição de todas as taxas.

As hipóteses de Taxa Adm como porcentagem ou valor monetário não explicam de
forma uniforme os registros. O programa utiliza o líquido explicitamente
informado, sem descontar taxas novamente ou criar lançamentos de taxa.
Tarifa/split não zero exigem contrato confirmado e bloqueiam a importação.
Cancelado, estornado, vazio e qualquer status diferente de Pago ou Pendente
bloqueiam **todo** o arquivo. Pendente é lançamento previsto e não aumenta BALAMT até a transição para Pago. Não se descartam linhas silenciosamente.

## Identificadores e estabelecimento

Cartão simples usa NSU como FITID. Parcelamento sem Juros usa `NSU:PARC:` + hash determinístico da identidade e do valor líquido da parcela; parcelas idênticas sem identificador diferenciador continuam bloqueadas. Pix usa `PIX:` + Id do Pix. NSUs iniciados com `PIX:`
são reservados e rejeitados. NSUs duplicados em vendas simples, IDs Pix duplicados, ausência de ID e colisões entre modalidades bloqueiam a operação. Duas parcelas não podem ter FITID igual; alterações no líquido da parcela modificam sua identidade e exigem conciliação. FITIDs não
contêm posição da linha, data de processamento ou identificador aleatório.
Reordenar as linhas conserva os identificadores e os bytes do modelo convertido.

Uma entrada só pode conter uma Loja. A identidade usa o texto aparado em Unicode
NFC, sem remover acentos ou mudar caixa. A conta do **livro de liquidações CSV**
é `VLR` + 19 caracteres hexadecimais do SHA-256 da Loja, BANKID `000`, moeda BRL,
FI VALORI e tipo OFX CHECKING. Isso representa um livro virtual, não uma conta
bancária comprovada nem uma conversão do tipo CC. O SHA-256 completo da Loja é
conferido nos metadados entre lotes; contas não são compartilhadas entre lojas.
Renomear a Loja exige conciliação, não associação automática.

Históricos legados usam `VALORI:1 `. O novo MEMO `VALORI:2 ` inclui status, quantidade de parcelas e chave de parcela, além das evidências de origem. O MEMO `VALORI:1 ` contém uma lista compacta com SHA-256 completo da Loja,
SHA-256 do NSU, SHA-256 dos metadados normalizados de origem, data/hora da venda e
modalidade (`C`, `D`, `P`). O campo ocupa 237 caracteres, abaixo do limite OFX de
255. A prova de origem abrange modalidade, datas, bruto, autorização, bandeira,
terminal, adquirente, parcelas e informações de taxa/split. Dados completos
continuam disponíveis no CSV original arquivado. O NAME informa a modalidade.

## Históricos, lotes e recuperação

Os três históricos privados têm bytes idênticos e `ACCTTYPE=CC`. Embora uma
transação confirme a equivalência de recebimento, o CSV não fornece BANKID,
BRANCHID e ACCTID que comprovem a identidade da conta desses históricos. O nome
de Loja também não fornece o identificador numérico presente nas descrições
históricas. A origem do gerador e a semântica de CC não puderam ser comprovadas.

Por isso, a atualização do Geral nesse caso permanece **bloqueada** com diagnóstico
específico. Não há CC → CHECKING automático, exclusão de histórico, primeira
importação forçada ou alteração do leitor financeiro global. Não mova nem
renomeie históricos para contornar o bloqueio. Uma futura migração depende de
vinculação documentada entre loja/conta e conciliação de todo o histórico.

Históricos produzidos pelo próprio fluxo CSV, com identidade e prova de origem
consistentes, são consolidados em memória a partir de todos os snapshots válidos.
FITID já conhecido precisa ter mesma data, valor, tipo e metadados de origem. A transição de Pendente para Pago substitui o registro anterior e passa a integrar o saldo confirmado; regressão para Pendente bloqueia.
Reimportação gera Limpo vazio e mantém o Geral. Mudanças sob o mesmo identificador,
identidades secundárias conflitantes, saldo derivado ou período incoerente
bloqueiam a operação. O saldo é a **soma dos recebimentos importados**, não um
saldo bancário ou prova de cobertura do período.

Lotes independentes, inclusive recebimentos antigos ainda não registrados,
podem acrescentar IDs inéditos ao livro da mesma Loja. Não se afirma continuidade
bancária entre lotes. Nenhuma transação anterior é removida e snapshots antigos
não são reescritos. O Geral do dia pode ser atualizado pelo protocolo existente.

SHA-256, lock, validação financeira após serialização, detecção de alterações
externas, rejeição de links/caminhos inseguros e publicação sem sobrescrita
continuam ativos. Manifestos novos usam versão 2 com `formato_csv=valori` e
`referencias_csv`. A recuperação verifica instituição, cabeçalho, descritor e
hashes das referências. Manifestos v1/v2 OFX e Rede anteriores permanecem
compatíveis; Valori exige descritor explícito. Não apague `.comparaofx` manualmente.

## Uso e homologação Windows

1. Faça uma cópia isolada do ambiente, incluindo todos os históricos; preserve
   um backup antes de executar a candidata Nuitka onefile sem assinatura.
2. Coloque o EXE na pasta de trabalho, crie a instituição `Valori` e coloque o
   CSV na mesma pasta do executável. Rede e Valori - Banking podem coexistir.
3. Com múltiplas entradas, selecione explicitamente o CSV Valori e a instituição.
   Selecione o XLSX/PDF/HTML desejado quando o menu pedir anexos. CSVs bancários
   reconhecidos são entradas e nunca anexos de outra instituição.
4. Em ambiente com histórico CSV canônico compatível, confira cada valor/data
   do Limpo e Geral, o total e os bytes do original arquivado. Reimporte uma cópia
   do mesmo CSV e confirme ausência de duplicatas. Não edite o arquivo de produção
   para simular conflitos; use somente exemplos sintéticos descartáveis.
5. Na cópia dos históricos privados CC existentes, espere o bloqueio de identidade.
   Confira que o CSV, anexos e históricos continuam intactos. Esse bloqueio é o
   resultado esperado, não uma importação financeira aprovada.

O leitor OFX tradicional e os comportamentos de Itaú, Itaú CNPJ, Rede e
Valori - Banking continuam cobertos pela suíte de regressão. Asaas, Bradesco e
PagSeguro permanecem fora desta alteração.

## Harness privado e CI

Somente no ambiente privado, com o ZIP fora do checkout:

```bash
python scripts/audit_valori_zip.py /caminho/privado/Valori.zip
```

O harness valida estrutura/CRC/links/limites do ZIP, extrai em diretório temporário
privado e trabalha sobre cópia descartável. Confere cada movimentação e totais,
roundtrip OFX, históricos equivalentes, planejamento e hashes. Publica somente
se o plano for aprovado. Não executa anexos. Saída contém contagens e códigos,
sem nomes de loja, IDs, valores ou caminhos privados. Retorno 0 significa
publicação aprovada; 2 significa conversão válida com publicação bloqueada;
1 significa auditoria/conversão não comprovada. Preservação é verificada também
no bloqueio. Os arquivos privados nunca entram no Git ou no GitHub Actions.

CI usa somente fixtures sintéticas: Linux/Windows, PyInstaller, Nuitka standalone,
Nuitka onefile, baseline e comparação no mesmo runner. Smokes testam Rede e Valori
juntas, OFX, XLSX, preservação, reimportação, conflito e recuperação. O inventário
exige Colorama, conversores e despachante, recusa testes/ferramentas do projeto,
e os builds verificam o ícone azul e Defender sem desativar proteções.


## Apresentação legível OFX (V3)

A geração nova usa `NAME` para o identificador/razão social e `MEMO` para a
descrição da venda, calculados exclusivamente do CSV, sem publicar dados
privados nos testes sintéticos:

- `NAME`: prefixo de seis dígitos extraído de `POS` com o layout
  `NNNNNNNN` (`NNNNNN` é a identificação do estabelecimento), seguido
  de ` - ` e a `Loja`. Sem prefixo inequívoco, usa somente o texto da loja.
  O campo OFX NAME permite **32 caracteres**; valores mais longos são
  truncados apenas para exibição. Para a loja do pacote privado, a forma
  solicitada `639224 - RENATA WIST ACESSORIOS LTDA` tem 36 caracteres;
  o NAME OFX compatível é
  `639224 - RENATA WIST ACESSORIOS`.
- `MEMO`: `Parcel 1/1 - Crédito à Vista - VISA - PHYSICAL`,
  com `Parcel` + quantidade de parcelas, `Tipo compra`, `Bandeira`
  e canal. Só é possível atribuir `1/1` quando `Parcelas=1`.
  **O CSV não possui o ordinal das parcelas de uma venda em 2x**:
  escrevemos `Parcel ?/2`, sem inventar 1ª/2ª parcela ou associá-las
  por ordem de linha ou valor líquido.
- `PHYSICAL` é uma **classificação operacional derivada**, não um campo
  explícito do CSV: emitida quando há POS e os três campos
  `CPF/CNPJ ecomm.`, `Nome ecomm` e `Nº Pedido` estão vazios.
  Havendo dados de ecommerce, emite `ECOMMERCE`; sem dados para
  classificar, `UNKNOWN`. O método não constitui prova independente
  do canal de venda.
- Pendências permanecem identificadas no MEMO pelo sufixo ` - PENDENTE`,
  sem integrar o saldo liquidado, até a mudança para Pago.
- `REFNUM` contém um marcador compacto `V3`, status, canal e digests
  da origem/NSU. A prova de origem detalhada permanece no CSV original
  arquivado. O histórico V1/V2 continua legível e comparável:
  não há reescrita retroativa de snapshots existentes.

A formatação é independente de deduplicação (FITID), data de pagamento
(DTPOSTED), valor líquido (TRNAMT) e tipo de recebimento (CREDIT).
