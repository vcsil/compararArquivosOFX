# ComparaOFX 2.1 candidata — compatibilidade de exportadores e históricos

Esta revisão mantém a comparação por FITID/Decimal e a publicação transacional.
Os adaptadores atuam em memória, sem modificar OFX, CSV ou anexos de entrada.
A release estável 2.0.0 não é substituída. O terminal identifica explicitamente
`COMPARAOFX 2.1 (CANDIDATA)`.

## Metadados OFX

- `FI.ORG` com mais de 32 caracteres: nome textual representado por `ORG:` mais
  os primeiros 28 dígitos hexadecimais do SHA-256 do nome completo em UTF-8.
  É determinístico, não confunde dois nomes com o mesmo prefixo e não trunca
  BANKID, FID, ACCTID, FITID ou qualquer identificador financeiro. Novos arquivos
  e históricos usam a mesma regra. Originais permitem auditar o texto integral.
- `DTSERVER` composto exclusivamente de zeros: substituído por uma referência
  válida do demonstrativo (maior DTASOF válido; na ausência, maior DTEND válido).
  Não usa o relógio. Sem referência verificável, bloqueia.
- `LEDGERBAL.DTASOF` exclusivamente zerado: associado explicitamente ao DTEND
  válido do **mesmo** demonstrativo. Essa é uma data de fechamento derivada do
  período informado, não a recuperação de um horário original desconhecido.
  BALAMT e todas as datas/horários DTPOSTED permanecem intactos. A adaptação é
  sinalizada no terminal. Datas inválidas não zeradas não são adivinhadas.
- Cabeçalho SGML VERSION:100: interpretado pela sintaxe compatível 1.02 da
  biblioteca, mantendo validação do restante do cabeçalho.
- Agregados SIGNON e TRNUID fora de ordem: reposicionados para a ordem do modelo.
  Não há criação de TRNUID nem alteração de seu valor.
- BANKACCTFROM externo ao demonstrativo: só é realocado quando há exatamente
  uma conta externa, um demonstrativo bancário e nenhuma conta interna. Qualquer
  ambiguidade bloqueia. Não se inventa tipo de conta; `CC` não é interpretado
  automaticamente como CHECKING ou conta de cartão.
- Tipos não padronizados `IN`/`OUT`: traduzidos para CREDIT/DEBIT somente quando
  o sinal de TRNAMT é coerente e não zero. Não altera valores ou identificadores.
  Sinal incompatível bloqueia. Saldos ausentes/inválidos não são reconstruídos
  por soma de transações nem preenchidos com zero.

A saída é XML OFX 2.03 e é relida/conferida antes da publicação. Erros de parsing
são apresentados sem conteúdo financeiro; avisos da biblioteca são sinalizados
sem despejar seus valores privados no terminal. COMPARAOFX_DEBUG permite detalhes
locais de exceções; não publique esses logs com documentos reais.

## Históricos anteriores

O índice de leitura aceita exclusivamente as convenções verificadas:

- `AAAA/MM - Mmm AAAA/AAAA-MM-DD/001` (atual).
- `MM - Mmm AAAA/AAAA-MM-DD/01` (sem nível de ano).
- `AAAA/MM - NomeCompleto/AAAA-MM-DD/01` (meses portugueses por extenso).
- Numeração de importação com dois ou três dígitos, positiva.
- Geral `OFXGeral-AAAA-MM-DD.ofx` e a convenção antiga
  `Bradesco Geral - AAAA-MM-DD.ofx`, com a data igual à da pasta diária.

Não há migração nem renomeação. Mês/ano/data inconsistentes, nomes desconhecidos,
dois Gerais para a mesma data, Geral ausente e links continuam bloqueados.
Se existir um histórico legado na própria data de destino, bloqueia antes de
criar outro Geral em uma hierarquia diferente. É necessária conciliação manual.
A permissão de leitura de referências antigas também é verificada na recuperação
v1/v2; os destinos novos continuam usando a hierarquia atual estrita.
A extensão OFX é reconhecida sem distinção de maiúsculas.

A simples leitura bem-sucedida não prova continuidade: bancos tradicionais
continuam exigindo a última data e cobertura da referência. Exporte um período
que inclua a referência anterior quando esse requisito não for satisfeito.
A política de lotes Rede permanece separada.

## Anexos

XLS, XLSX, PDF, HTML/HTM e demais extensões documentadas são arquivos opacos.
Não são executados nem abertos como páginas. São copiados, conferidos por hash
e só removidos após a publicação segura. Executáveis não são anexos aceitos.

Com um extrato e uma única instituição, anexos elegíveis continuam associados
à importação. Com várias instituições ou vários extratos, o menu exige seleção
explícita dos anexos: proximidade física não prova associação bancária.
CSV reconhecido como Rede continua sendo extrato, nunca anexo de outro banco.

## Armazenamento local, Drive e concorrência

O Windows verifica operações reais antes da importação, sem exigir DRIVE_FIXED,
NTFS/ReFS ou rejeitar o nome do provedor. Isso permite avaliar pastas locais,
espelhadas e unidades virtuais pelo mesmo critério. O teste cobre escrita exclusiva,
flush, releitura, SHA-256, renomeação exclusiva de arquivo/pasta, recusa de destino
ocupado, substituição autorizada e atualização de manifesto. Uma falha indica a
operação exata. Ver [diagnóstico e limites](13-armazenamento-drive.md).

O bloqueio Windows usa mutex global do kernel, independente do armazenamento virtual;
no Linux continua com flock. Ambos são **locais à máquina**, sem exclusão distribuída.
Não execute importações simultâneas em computadores distintos. Hashes detectam
alterações nos pontos de revalidação, mas não eliminam a corrida entre uma verificação
e uma alteração remota. Aguarde a sincronização terminar antes de importar.

Hardlinks reais continuam bloqueados. Contagem zero só é aceita quando as capacidades
Windows declaram que o volume não suporta hardlinks. Capacidade desconhecida ou
contagem ausente em volume que suporta hardlinks gera erro específico. Symlinks,
junctions e tags reparse desconhecidas continuam recusados; placeholders CLOUD sem
redirecionamento de nomes são aceitos e lidos integralmente para cálculo de hash.

Não há homologação de Google Drive/OneDrive real neste ambiente Linux. O diagnóstico
usa somente dados sintéticos em subpasta temporária no volume escolhido:

```powershell
python scripts/probe_storage.py "G:\PastaDeTesteDoDrive"
```

## Auditoria privada de documentos

`scripts/audit_private_zip.py` recebe um ZIP **fora do checkout** e um destino
privado de relatório também fora dele. Verifica travessia, caminhos absolutos,
colisões de nomes, links, tamanho, taxa de compressão e CRC antes da extração.
Usa uma pasta temporária isolada, não executa arquivos do ZIP, testa roundtrip,
planejamento, publicação e recuperação em cópias, confere hashes e remove as
cópias ao terminar. O ZIP e a referência original não são modificados.

```bash
python scripts/audit_private_zip.py /caminho/privado/arquivo.zip --report /caminho/privado/relatorio.json
```

`--codificacao utf-8` ou `--codificacao cp1252` testa uma escolha explícita somente
nos arquivos declarados 1252 e realmente ambíguos. A ferramenta não escolhe a
codificação pelo banco. O aplicativo continua solicitando a escolha ao usuário.
O relatório não contém contas, transações, valores, cartões ou caminhos dos
arquivos reais. Ele distingue publicação validada, decisão pendente e bloqueio.
ZIP, documentos, relatórios e logs privados nunca devem ser enviados ao GitHub,
ao CI, a comentários do PR ou a fixtures. No CI só entram dados inventados.

## Verificação e homologação

Os testes sintéticos cobrem metadados, preservação financeira, roundtrip,
conflitos em históricos legados, recuperação com referências antigas, anexos
XLS/HTML (falhas na cópia e remoção), exclusão entre processos, lock preexistente,
hardlink real, metadados ausentes e pastas identificadas como OneDrive sem veto por nome.
As sete falhas históricas esperadas permanecem.

Os três candidatos Windows executam o smoke financeiro, CSV e recuperação v1/v2,
além de smoke sintético combinado com nome institucional longo, datas de
metadados zeradas, anexo XLS e histórico sem nível de ano. A baseline 2.0 mantém
somente os contratos compartilhados, sem exigir adaptadores novos.
Resultados de cada execução e hashes devem ser conferidos no HEAD do PR.
Nenhum build usa o ZIP privado.

Para homologar, use o onefile do HEAD aprovado em pasta nova local, crie uma
instituição e use apenas a fixture sintética. Confira importação, anexo, Geral,
Limpo, reimportação sem duplicação e conflito preservando as saídas anteriores.
Repita o diagnóstico de armazenamento no Windows de destino. Um documento
bloqueado por saldo, identidade ou histórico inconsistente precisa de exportação
corrigida ou conciliação; não apague históricos/manifestos para forçar sucesso.
