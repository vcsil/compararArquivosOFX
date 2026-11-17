# Importação CSV da Rede — ComparaOFX 2.1 (candidata, PR #2)

## Uso e escopo

Crie uma pasta dedicada para o executável e uma subpasta chamada exatamente
`Rede` (também aceita `REDE` ou `rede`). Coloque o CSV ao lado do executável.
Selecione o arquivo e a instituição no menu dinâmico. `Banco Rede`,
`Rede Empresa 2` e outros bancos não habilitam CSV como extrato.

```text
Aplicação/
├── ComparaOFX.exe
├── vendas.csv
└── Rede/
    └── 2026/11 - Nov 2026/2026-11-16/
        ├── OFXGeral-2026-11-16.ofx
        └── 001/
            ├── vendas.csv
            └── OFX Limpo-161120261030.ofx
```

A data das pastas é a data de importação; a data das transações é a data da venda.
Outros bancos continuam aceitando OFX pelo motor 2.0. Um CSV reconhecido como
relatório Rede não é oferecido nem aceito como anexo de outro extrato, mesmo
sem pasta Rede. Outros relatórios CSV não são anexados a uma importação CSV.

## Colunas e parsing

Cabeçalhos obrigatórios: `Status da venda`, `Data da venda`, `Hora da venda`,
`Valor líquido`, `NSU/CV`, `Código da maquininha`, `Meio de pagamento`,
`Bandeira`, `Modalidade`, `Tipo`, `Número de parcelas`.
Opcionais: `Pré-autorizado` e `Número do estabelecimento`.
A ordem é livre; acentos, espaços e maiúsculas dos cabeçalhos são normalizados.
Cabeçalhos duplicados ou ausentes bloqueiam o arquivo inteiro.

Aceita UTF-8 com/sem BOM e Windows-1252; delimitadores `;`, `,` ou tabulação;
aspas CSV, delimitadores internos e campos com quebras de linha reais.
CSV com aspas malformadas, colunas extras/ausentes ou caracteres de controle
inválidos é rejeitado. Nenhuma linha aprovada com erro é descartada.
Status vazio é erro; apenas status normalizado começando com `aprovad` entra
no modelo. Status não aprovado é ignorado, como no notebook.

Valores usam exclusivamente `Decimal`, com vírgula decimal brasileira e ponto
para milhares (`R$ 1.234,56`). Exige valor positivo e no máximo dois decimais.
Datas: `DD/MM/AAAA` ou `AAAA-MM-DD`; horas: `HH:MM[:SS]`.
Campos obrigatórios das aprovadas não podem ficar vazios. Parcelas devem ser
inteiro positivo. FITID duplicado dentro do CSV bloqueia mesmo com valor igual.
Os limites dos campos OFX também são impostos pelo ofxtools.

## Compatibilidade com o notebook anexado

| Campo | Regra preservada |
|---|---|
| TRNAMT | Valor líquido |
| FITID | `NSU/CV - hora da venda`, preservando o texto da hora |
| DTPOSTED | Apenas a data da venda |
| TRNTYPE | CREDIT |
| NAME | Código da maquininha + meio de pagamento formatado |
| MEMO | Bandeira + modalidade + tipo + parcelas; acrescenta Pre-Auto quando indicado |
| Identidade | BANKID=000, BRANCHID=0000, ACCTID=VENDAS_REDE, CHECKING, BRL; FI=REDE |

Não "corrigir" automaticamente o texto de tipo que já contenha pre-auto:
a formatação e eventual repetição de Pre-Auto reproduzem o notebook.
A grafia da hora no FITID também é legado: `12:01` e `12:01:00` são diferentes.

A implementação inicial acrescentava hora e `[-3:BRT]` ao DTPOSTED.
A auditoria voltou à data sem fuso explícito do notebook: ofxtools interpreta
`AAAAMMDD` como meia-noite UTC e serializa com fuso explícito, mantendo a mesma
data civil. Há teste de igualdade com OFX SGML gerado pelo notebook, roundtrip
XML e reimportação CSV sobre histórico legado. Históricos já existentes não
são regravados para normalizar datas/fusos. A comparação Rede de FITIDs usa a
data civil, compatível também com a candidata anterior com horário UTC−03:00.
O motor de comparação dos demais bancos não foi flexibilizado.

Diferenças intencionais: parsing mais estrito; rejeição de status vazio,
valores zero/negativos/com frações de centavo e parcelas inválidas, em vez dos
comportamentos permissivos do notebook. Conversão ocorre em memória e passa
pelas verificações de publicação/recuperação do aplicativo, sem OFX intermediário.

A fixture versionada `tests/fixtures/rede_sintetico.csv` tem três vendas fictícias,
duas aprovadas: 10,50 + 20,25 = **30,75**. O golden `rede_notebook.ofx` foi produzido
pelas funções do notebook anexado, sem executar a célula de conversão automática.
O notebook e o CSV anexados não foram incorporados ao Git.

**O anexo chamado Exemplo_Rede.csv não corresponde à descrição de três vendas:**
contém 48 linhas, 42 aprovadas e total líquido 11.119,95. Foi comparado localmente
com as funções originais do notebook: FITID, data, valor, tipo, NAME e MEMO de
todas as aprovadas foram equivalentes, inclusive após serialização/releitura.
Como contém identificadores de estabelecimento e cartões mascarados, seu conteúdo
não foi versionado nem usado no CI. Nenhuma alegação de anonimização foi feita.

## Identidade de estabelecimento

A identidade genérica antiga não distingue empresas. Se o CSV trouxer
`Número do estabelecimento`, todas as linhas devem trazer o mesmo número real
(não vazio, somente dígitos, até 22 caracteres). Ele é preservado em `ACCTKEY`,
sem mudar a identidade genérica BANKID/ACCTID. A primeira importação o registra
automaticamente; importações posteriores de outro estabelecimento ou sem esse
campo são bloqueadas. Não há prompt adicional nesse fluxo.

Um histórico legado sem ACCTKEY não prova a qual estabelecimento pertence.
Para vinculá-lo a um CSV identificado, confira manualmente sua procedência e
crie `Rede/.rede.json` com o número real em texto. Exemplo **fictício**:

```json
{"estabelecimento": "12345678"}
```

A configuração é opcional para a primeira importação e obrigatória somente
para essa vinculação explícita ou quando desejado restringir o estabelecimento.
CSV incompatível com ela bloqueia. A configuração não é um extrato nem uma
pendência de recuperação e não deve ser editada durante uma operação.
Relatórios sem coluna de estabelecimento mantêm compatibilidade genérica entre
si: **não permitem demonstrar separação entre estabelecimentos**. Nunca misture
empresas nesse modo. Para vários estabelecimentos use diretórios completos da
aplicação separados, cada um com sua pasta exatamente `Rede` e identificação.
Não invente números de banco, conta, agência ou estabelecimento.

## Lotes e continuidade

O CSV é um lote independente de vendas, não um extrato bancário de cobertura
contínua. A política Rede compara contra todos os snapshots Gerais anteriores
válidos da instituição, consolidados apenas em memória:

- Primeira importação aceita todas as aprovadas válidas.
- FITID existente, mesma data civil/valor/tipo/cheque: duplicata, nunca nova venda.
- FITID existente com data/valor/tipo/cheque diferente: conflito, bloqueia tudo.
- Nova venda na data de referência ou posterior: adicionada, mesmo sem sobreposição.
- Venda inédita anterior à última data do histórico: bloqueio para conciliação manual.
- Datas fora de ordem são ordenadas; nenhuma venda inédita é descartada por corte.
- Reimportação gera Limpo vazio e mantém todas as vendas do acumulador.

A ausência de sobreposição **não comprova continuidade ou completude do período**.
A política preserva a integridade dos lotes fornecidos, mas não prova que o usuário
entregou todos os relatórios. É necessário conciliar lotes faltantes na origem.
NSU + hora não garante unicidade global; colisão em outro dia bloqueia, sem mudar
o FITID automaticamente. Descrições divergentes são avisadas, conforme o legado.

O Geral novo acumula todas as transações conhecidas, inclusive ao mudar o dia de
importação. Snapshots históricos de dias anteriores permanecem intactos; hashes
são verificados durante publicação e recuperação. Um Geral do dia pode ser
atualizado transacionalmente. Conflitos entre snapshots também bloqueiam.
LEDGERBAL é total derivado de vendas líquidas, **não saldo bancário real**: no
modelo de entrada, soma do lote; no Geral consolidado, soma das vendas acumuladas.
O Limpo conserva metadados do lote conforme o motor de filtragem existente.

## Originais, publicação e recuperação

CSV é o original e nunca um anexo da própria importação. Seus bytes, codificação,
quebras de linha e delimitadores não são regravados. O arquivo é copiado/verificado
por SHA-256 e só removido da raiz depois da publicação e validação das saídas.
A assinatura de releitura agora confere também NAME e ACCTKEY, além dos campos
financeiros já verificados.

Manifestos v1/v2 continuam aceitos sem migração destrutiva. Novos manifestos CSV
podem incluir `referencias_rede`, com hashes de snapshots e configuração usados.
Essas referências são opcionais para manifestos anteriores e têm caminhos,
hierarquia, links, identidade da pasta e hashes verificados na recuperação.
CSV recuperado fora da instituição exatamente Rede é bloqueado.

Interrupções antes da publicação podem limpar a preparação verificável para
nova tentativa. Após confirmação do Geral, a recuperação verifica saídas/cópias
antes de remover originais, inclusive se a remoção anterior foi parcial.
Interrupção após publicação da pasta mas antes do Geral requer inspeção manual:
preserve `.comparaofx`, o CSV e as saídas; não apague manifestos para forçar uso.
Hash alterado ou dados insuficientes também bloqueiam. Nunca force recuperação
nem altere arquivos de controle durante a operação.

## Validação e pendências de Windows

Nesta auditoria, a suíte Linux executou **184 testes**: 173 passaram, sete
falhas esperadas do legado e quatro ignorados por exigirem Windows.
O PyInstaller 6.19.0 em Linux gerou um onefile que passou no smoke financeiro,
na recuperação v1/v2 e no smoke CSV completo com PATH vazio e sem PYTHONPATH.
O inventário confirmou 238 módulos, incluindo Colorama, ofxtools e rede_csv,
sem módulos próprios de testes/ferramentas. Isso não substitui builds Windows.
Os testes incluem golden do notebook, formatos/codificações, campos inválidos,
500 e 3.000 registros, lotes sem sobreposição, históricos antigos, conflitos,
restrição de instituição, preservação de bytes e interrupções de cópia,
publicação, remoção e recuperação. As sete falhas esperadas do legado permanecem.

A causa local confirmada dos smokes Windows anteriores foi `\\n` literal tanto
no stdin quanto nas linhas do CSV; corrigido para LF real. O smoke agora executa
importação, reimportação sem duplicação e bloqueio de conflito CSV. Um teste
regressivo percorre todas as oito chamadas do harness com subprocessos reais.
A baseline 2.0 mantém `--skip-rede-csv`, preservando os smokes financeiros comuns.
A auditoria dos candidatos 2.1 exige explicitamente `controller.rede_csv`.

**Ainda não homologado para release:** os três builds Windows (PyInstaller onefile,
Nuitka standalone e Nuitka onefile), seus smokes, ícone e Microsoft Defender
precisam de execução confirmada no HEAD corrigido. Esta máquina é Linux.
O API do GitHub está bloqueado por egress (CONNECT 403); foi salvo no rascunho
um acréscimo de `api.github.com` à rede, sem alterar os presets existentes.
O acesso Git funciona; isso não prova acesso autenticado ao API/logs/artefatos.
Não há SHA-256, tamanho ou link de artefato Nuitka Windows validado desta revisão.
O alerta histórico `Program:Win32/Contebrew.A!ml` segue sem diagnóstico conclusivo;
não desative Defender nem crie exclusões.

Para homologação manual após CI aprovado: use uma pasta nova no Windows, crie
Rede, copie somente a fixture sintética, execute e confira duas vendas e 30,75.
Confira o CSV arquivado byte a byte; reimporte uma cópia e confira que o Geral
não duplica e o Limpo fica vazio. Altere o valor de um FITID na cópia e confirme
bloqueio preservando original e Geral. Só depois use relatórios reais com backup.
Mantenha PR #2 em draft até concluir Windows; não fazer merge, tag ou release.

O workflow do PR faz uma execução por atualização: a branch 2.1 não dispara
também o evento push, evitando builds duplicados com pull_request synchronize.

## Correção das falhas Windows do commit 4b3377d

A execução [43893190183](https://github.com/vcsil/compararArquivosOFX/actions/runs/43893190183)
identificou três problemas de portabilidade, sem necessidade de alterar o motor
financeiro:

1. `referencias_rede` era serializado com `str(Path)`, gerando barras invertidas
   no Windows, corretamente rejeitadas pelo validador. Agora usa `as_posix()`.
   A validação de segurança permanece intacta: caminhos absolutos, `..`, drives
   indevidos e barras invertidas continuam bloqueados. Um teste captura o
   manifesto persistido, confere o snapshot e seu SHA-256 e executa recuperação.
2. Fixtures UTF-8 eram lidas e, em um caso, regravadas sem encoding explícito.
   Todas as leituras/escritas textuais dessas fixtures agora declaram UTF-8,
   incluindo a configuração sintética. O leitor de relatórios reais continua
   testando UTF-8 e Windows-1252 normalmente.
3. Os mocks de `Path.unlink` comparavam representações de caminhos. Agora usam
   `samefile()` enquanto ambos existem. No caso pós-remoção a identidade é
   capturada antes do `unlink`. Os testes exigem exatamente uma injeção no
   original, conferem se ele deve existir e validam cópia byte a byte e recuperação.

Validação local após essas correções: **186 testes Linux**, sendo 175 aprovados,
sete falhas esperadas e quatro ignorados por exigirem Windows. O acréscimo de dois
casos cobre o formato do manifesto e a rejeição de referências inseguras.
A contagem de 184 acima corresponde à auditoria anterior, não à revisão atual.
Resultados Windows, builds e hashes desta revisão só serão registrados depois de
confirmados no novo HEAD. Não reutilizar resultados nem hashes da execução antiga.
Os executáveis continuam candidatos sem assinatura digital; a situação do alerta
histórico do Defender permanece a descrita acima.
