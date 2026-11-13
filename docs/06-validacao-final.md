# Validação final e release candidate — Etapa 6

A Etapa 6 parte de `f6751e5104dd3b28bbc554716cdd0ff6d74368c2`, HEAD final da Etapa 5. Branch: `codex/comparaofx-2.0-etapa6`. O checkout inicial estava limpo; todo o histórico foi preservado. O usuário informou que o executável anterior funcionou no Windows. A confirmação anterior não substitui a homologação do candidato recompilado desta missão.

As Etapas 0–5 estabeleceram baseline, leitura/serialização, deduplicação financeira, organização, escrita segura/recuperação e candidatos Windows. Esta missão restaura a convenção do nome do Limpo e audita esses contratos, sem trocar o motor financeiro, parser, formato de exportação ou executável legado.

## Nome, organização e recuperação

O nome de novas saídas é **`OFX Limpo-DDMMAAAAHHMM.ofx`**, por exemplo `OFX Limpo-131120260740.ofx`. O horário local é capturado uma única vez no início do planejamento; não vem de transações. `Plano.limpo_nome` permanece o mesmo até o fim da operação. `planejar(..., relogio=...)` permite fixar o relógio nos testes. A execução valida e captura novamente o nome como dado do plano, sem consultar outro relógio. Não há segundos ou separadores novos.

Data das pastas, nomes dos bancos, numeração, Geral, originais e anexos não mudam. Importações no mesmo minuto são isoladas por `001`, `002` etc. Colisões dentro da pasta são recusadas antes da preparação, inclusive com capitalização diferente. Originais e anexos não são sobrescritos.

Novos manifestos usam versão 2, com `limpo_nome` obrigatório e SHA-256 `limpo_hash` obrigatório. A validação exige prefixo e extensão exatos, 12 dígitos ASCII e data/hora válidas; não aceita caminhos, controles, outras versões, valores ausentes ou tipos ambíguos. A recuperação v1 continua usando implicitamente `OFX Limpo.ofx`, sem renomear arquivos antigos. Hashes, bloqueios, publicação exclusiva, releitura e verificações anteriores à remoção continuam obrigatórios. Consulte [o protocolo](04-integridade-recuperacao.md) e seus limites.

## Auditoria das sete falhas esperadas

Os sete testes históricos foram mantidos. Eles caracterizam funções legadas que continuam inseguras para esses usos; não representam falhas esperadas permitidas no fluxo moderno. Não se alterou a política financeira para fazê-los passar.

| Baseline | Defeito legado | Cobertura moderna / decisão |
|---|---|---|
| 08 | Memo e valor confundem FITIDs distintos | `test_memo_alterado_e_id_diferente`, testes de interseção e auditoria do terminal preservam movimentos legítimos iguais com IDs distintos |
| 09 | Mudança de memo impede correspondência pelo FITID | O motor prioriza FITID, evita duplicação e registra divergência de memo |
| 10 | Mesmo FITID com valor diferente é tratado apenas como tupla diferente | O comportamento correto moderno é **bloquear o conflito**, não simplesmente igualar as transações; `test_conflitos_valor_tipo_data` |
| 13 | Acumulador concatena duplicatas ao reprocessar | `test_reprocessamento`, organização, Geral sem novidades e smoke financeiro garantem idempotência |
| 16 | União de contas diferentes sem validação | `test_conta_banco_moeda_diferentes` e auditoria do terminal bloqueiam conta/banco/moeda/tipo incompatíveis |
| 17 | Descoberta depende da ordem de `listdir` | Navegação moderna usa hierarquia validada e histórico cronológico; `test_historico_cronologico` |
| 18 | Escrita direta pode truncar histórico após falha | Testes de disco cheio, falha parcial, publicação e recuperação exercitam `safe_storage`, não o escritor legado |

`test_legacy_audit.py` substitui as funções antigas de comparação, navegação e gravação por exceções e executa o terminal com primeira/segunda importação e conta divergente. Ele falha se a produção voltar a chamá-las. A API moderna usa `carregar_ofx` de `ofx_functions`, o motor `ofx_comparison`, `organization`, `workflow` e `safe_storage`. A existência das funções antigas não autoriza seu uso direto para atualizar históricos financeiros; consumidores externos dessa API legada não foram migrados nesta missão.

## Garantias e compatibilidade OFX

A suíte mantém identificação da conta, FITID prioritário, movimentos legítimos com valores/memos iguais, bloqueio por FITID conflitante, conservação de quantidade/créditos/débitos/líquido, preservação byte a byte dos originais, atualização segura do Geral, interrupções reais com `os._exit`, remoção parcial, bloqueios entre processos e ambiguidade de codificação. Nenhuma verificação foi removida para aprovar a nomenclatura.

O formato de saída continua **OFX XML 2.03 em UTF-8**, com releitura pelo ofxtools e comparação dos campos financeiros, períodos, saldos e fusos aplicáveis. O novo teste de nomes confere declaração XML/versão/encoding, FITID e valor; a suíte de leitura e o protocolo mantêm as verificações detalhadas. Aplicativos externos limitados a OFX 1.x podem rejeitar essa saída. Não foi introduzido outro formato de exportação, nem se afirma compatibilidade com um importador bancário externo não testado.

## Testes e builds

Validação local em Linux, Python 3.12.14: **146 testes**, 135 aprovados, quatro ignorados por plataforma e sete falhas esperadas históricas. Nenhuma falha inesperada. Sintaxe/importações Python, YAML e blocos PowerShell foram verificados. O smoke local com lançador Python passou com nome novo, horário local, deduplicação, conflito de FITID e recuperação v1/v2; isso valida o teste, não substitui os candidatos Windows.

A execução nativa desta revisão é [43413157659](https://github.com/vcsil/compararArquivosOFX/actions/runs/43413157659), commit `116b6e7`. Os resultados finais, tamanhos e hashes estão registrados na seção de resultados nativos abaixo; os cinco jobs terminaram aprovados. O workflow compila novos PyInstaller onefile, Nuitka standalone e Nuitka onefile, testa todos e mede os três no mesmo runner. Não reutiliza os binários da Etapa 5. Os artefatos são candidatos temporários, não uma release definitiva.

## Executar e atualizar

Para usar um onefile, extraia o artefato, confira o SHA-256 e coloque apenas o EXE na raiz de trabalho, ao lado das pastas de bancos. O standalone exige a distribuição inteira. Inicie o EXE, selecione banco/OFX/anexos e confira o relatório. Outros OFX não selecionados permanecem na raiz. O runtime deve estar incluído; a homologação em computador sem Python confirma essa condição no destino.

Antes de atualizar: feche todas as instâncias e faça backup consistente das instituições, OFX/anexos na raiz e registros `.comparaofx`. Preserve o EXE anterior separadamente. Troque somente o executável (ou a distribuição completa no standalone); não apague, mova ou renomeie históricos e manifestos para instalar a versão. O candidato novo recupera registros v1 existentes. Não volte ao executável antigo enquanto houver manifesto v2 pendente. Não execute versões diferentes simultaneamente.

Desenvolvimento: `python3 -m venv venv`, `venv/bin/python -m pip install -r requirements.txt`, `venv/bin/python -m unittest discover -s tests -v`. Em Windows, use `venv\Scripts\python.exe`; `scripts/build_windows.ps1 -Tool nuitka` recompila e testa standalone/onefile fora do `dist/` legado. A execução Python é `venv/bin/python src/comparaArqOFX.py` a partir do checkout; não é necessária para o usuário final do EXE.

## Homologação manual do candidato corrigido

Use uma pasta nova, com espaço/acentos, em Windows de destino **sem Python instalado**. Somente dados sintéticos. Registre versão do Windows, SHA-256 do EXE, horário local e cada resultado; não use o histórico real para ensaiar interrupções.

1. Baixe o artefato desta revisão, extraia e confira o hash registrado abaixo. Copie `tests/fixtures/windows-manual/Entrada.ofx` para a raiz do EXE e crie `Banco Sintetico` vazio ao lado. Registre o SHA-256 da entrada com `Get-FileHash`.
2. Abra por duplo clique, confira o menu e cancele com `0`. Depois execute de outro diretório de trabalho e selecione `1`. Confirme `001/OFX Limpo-DDMMAAAAHHMM.ofx`, data/hora local do processamento, `OFXGeral-AAAA-MM-DD.ofx`, crédito BRL 20 / FITID `SYNTH-1` e original arquivado com o hash inicial. A janela interativa deve continuar visível ao final.
3. Copie novamente a mesma entrada sintética para a raiz. Importe no mesmo dia: deve criar `002`, Limpo vazio válido e manter o Geral sem duplicação. O nome pode coincidir com o da primeira importação se ambas ocorrerem no mesmo minuto; as pastas isolam os arquivos.
4. Para uma segunda importação com novidades, use outro extrato sintético com a transação anterior e um novo FITID, e confira que só a novidade entra no Limpo. Compare quantidade e valores do Geral e preserve os dois originais.
5. Para recuperação controlada, prepare o pacote numa máquina de desenvolvimento com Python: `python scripts/prepare_recovery_smoke.py CAMINHO_NOVO`. O destino deve ser inexistente; o gerador recusa sobrescritas. Ele cria `v1-preparado`, `v1-geral`, `v1-parcial`, `v2-preparado`, `v2-geral` e `v2-parcial`, contendo somente OFX/PDF sintéticos, manifestos e instruções. Transfira as seis pastas completas para o Windows sem Python, incluindo `.comparaofx`. Copie o EXE corrigido para dentro de cada pasta de cenário e abra-o. No cenário `preparado`, a preparação deve ser limpa e o arquivo da raiz deve ser importado ao selecionar `1`; nos demais, a recuperação deve concluir sem duplicar o histórico. `LEIA-ME.txt` informa o hash do original e o nome preparado. Nos cenários v2 interrompidos, o horário registrado pertence à geração na máquina de preparo e não deve ser recalculado no destino. Após publicação, o Limpo v1 deve manter o nome antigo e o v2 o nome registrado. Não use esse gerador em diretório com dados reais, não mate um processamento real e não altere hashes para forçar sucesso. Uma interrupção manual em ponto desconhecido pode produzir um registro parcial não verificável; nesse caso, a recusa de recuperação exige inspeção.

O smoke nativo automatiza a criação de cenários interrompidos após publicação do Geral e exige que o EXE recuperado preserve nome, bytes, original e histórico em v1/v2. A suíte também cobre falha antes da publicação e depois de remoção parcial. A homologação manual deve ser registrada separadamente; o sucesso informado pelo usuário para o EXE da Etapa 5 não aprova automaticamente este novo protocolo.

## Checklist para liberação

- [x] Convenção legada de data/hora restaurada, com relógio único e injetável.
- [x] Recuperação v1/v2, colisões, nomes maliciosos e hashes cobertos em Linux.
- [x] Sete falhas esperadas auditadas e isolamento do código legado testado.
- [x] Garantias financeiras e saída OFX XML 2.03/UTF-8 preservadas.
- [x] Testes e builds Windows desta revisão concluídos e conferidos.
- [x] SHA-256 e tamanho dos novos candidatos publicados neste documento.
- [ ] Homologação manual do novo EXE em Windows sem Python e por duplo clique.
- [ ] Revisão dos resultados e aprovação explícita do usuário para liberação definitiva.

Não foi feito merge em master, release pública, substituição do legado ou migração automática. A recomendação é preparar o candidato e manter a liberação definitiva condicionada à revisão e homologação acima.

## Diagnóstico da validação Windows

As execuções [43412183869](https://github.com/vcsil/compararArquivosOFX/actions/runs/43412183869), [43412543775](https://github.com/vcsil/compararArquivosOFX/actions/runs/43412543775) e [43412771464](https://github.com/vcsil/compararArquivosOFX/actions/runs/43412771464) falharam na suíte Windows; os builds foram corretamente ignorados. O traceback público da última mostrou `AssertionError: OSError not raised` em `test_recuperacao_apos_remocao_parcial_v2`: o teste novo comparava caminhos textuais e não reconhecia o original quando o Windows normalizava seu alias 8.3. O ponto de interrupção agora usa identidade por `samefile`, como os testes anteriores; não foi removida a asserção nem alterado o protocolo para acomodar a falha. Os diagnósticos de CI preservam o código de saída e publicam um trecho limitado do traceback sintético, pois a API de logs permanece indisponível nesta sessão. A nova execução aprovou as suítes Linux e Windows antes de iniciar os builds.

Commits desta missão até os builds: `5d77aa8` (nomenclatura e manifestos), `28d4fdf` (regressões, auditoria e smoke), `38d63a1` e `7504d5a` (diagnóstico sintético do CI), `116b6e7` (identidade Windows, recuperação v1 parcial e pacote de homologação). O motor financeiro, o parser e `dist/Compara OFX.exe` não foram modificados.

## Arquivos alterados

- Produção: `src/controller/workflow.py`, `src/controller/safe_storage.py` e o novo `src/controller/ofx_names.py`. `ofx_functions.py` foi auditado e mantém a convenção legada existente; o fluxo moderno usa o plano e a escrita segura.
- Regressão e auditoria: `tests/test_output_names.py`, `tests/test_legacy_audit.py`, `tests/test_manual_recovery_fixture.py`, `tests/test_baseline.py`, `tests/test_comparison.py`, `tests/test_organization.py` e `tests/test_safe_storage.py`.
- Validação e medição: `scripts/smoke_exe.py`, `scripts/benchmark_exe_processing.py`, `tests/benchmark_etapa4.py`, o novo `scripts/prepare_recovery_smoke.py` e `.github/workflows/windows-validation.yml`.
- Documentação: `docs/03-navegacao-organizacao.md`, `docs/04-integridade-recuperacao.md`, `docs/05-executavel-windows.md`, `docs/05-benchmark.md` e este documento.

## Resultados nativos do release candidate

Execução [43413157659](https://github.com/vcsil/compararArquivosOFX/actions/runs/43413157659), commit `116b6e7dbd0918ab0b2b2da416ebdfff10828a72`. Os jobs de testes Linux, testes Windows, PyInstaller, Nuitka e comparação terminaram com sucesso. As medidas abaixo vêm exclusivamente do job `comparison`, que baixou e revalidou os três artefatos no mesmo runner. Os hashes coincidem com os publicados pelos jobs de build.

Ambiente de comparação: AMD EPYC 9V45 96-Core Processor, imagem `win25-vs2026/20261103.298.1`, Python 3.12.10. Ferramentas de build: PyInstaller 6.11.1 e Nuitka 2.5.9. Os runners de build e comparação são instâncias diferentes; nenhum resultado depende de manter seus processos vivos.

Todos os candidatos passaram no nome com horário local, recuperação de manifestos v1/v2, menu, pasta do executável com espaços/acentos, início a partir de outro diretório, leitura e saída OFX sintética, original byte a byte preservado, reimportação com deduplicação e rejeição de conflito de FITID mantendo entrada e Geral intactos. A suíte local executou 146 testes: 135 aprovados, quatro ignorados por plataforma e sete falhas esperadas da baseline; os dois jobs nativos da suíte também foram aprovados. Os totais de skips Windows não foram extraídos de logs autenticados.

| Candidato | EXE bytes | EXE MiB | Arquivos da distribuição | Distribuição bytes |
|---|---:|---:|---:|---:|
| PyInstaller onefile | 9830401 | 9.375 | 1 | 9830401 |
| Nuitka standalone | 12125696 | 11.564 | 22 | 27931496 |
| Nuitka onefile | 7933952 | 7.566 | 1 | 7933952 |

| Candidato | SHA-256 do EXE |
|---|---|
| PyInstaller onefile | `86d35fc456b6e192b3f066be64aedb1d20051c644c8ef30d183b974a1b5881bf` |
| Nuitka standalone | `32269290dfe96d41180b2f6501b4c70ca6926eeda6c2953bf4723194c9d01c12` |
| Nuitka onefile | `97a187562f231e839313b50a8a83af946cac2c2b34617ee64ef974ccdf28d1ee` |

Tempos até o menu completo, em milissegundos. Primeira abertura observada, seguida de 15 execuções; p95 por posto mais próximo.

| Candidato | Primeira | n subsequentes | Mediana | Mínimo | Máximo | p95 |
|---|---:|---:|---:|---:|---:|---:|
| PyInstaller onefile | 502.622 | 15 | 405.9689 | 352.9245 | 534.6485 | 534.6485 |
| Nuitka standalone | 169.8893 | 15 | 35.8618 | 34.0022 | 40.8305 | 40.8305 |
| Nuitka onefile | 419.0054 | 15 | 356.5837 | 318.0174 | 382.8757 | 382.8757 |

Processamento em milissegundos, incluindo inicialização do processo e excluindo geração do OFX sintético.

| Candidato | Transações | n | Mediana | Mínimo | Máximo |
|---|---:|---:|---:|---:|---:|
| PyInstaller onefile | 100 | 3 | 1238.705 | 1180.043 | 1291.293 |
| PyInstaller onefile | 1000 | 3 | 2914.504 | 2860.000 | 2972.737 |
| PyInstaller onefile | 10000 | 1 | 18762.244 | 18762.244 | 18762.244 |
| Nuitka standalone | 100 | 3 | 526.978 | 468.512 | 543.068 |
| Nuitka standalone | 1000 | 3 | 2204.116 | 2171.523 | 2225.680 |
| Nuitka standalone | 10000 | 1 | 18782.783 | 18782.783 | 18782.783 |
| Nuitka onefile | 100 | 3 | 902.482 | 755.724 | 905.402 |
| Nuitka onefile | 1000 | 3 | 2535.835 | 2470.726 | 2538.231 |
| Nuitka onefile | 10000 | 1 | 19540.040 | 19540.040 | 19540.040 |

A primeira abertura não representa cache frio garantido. Não foi configurado cache persistente de extração. Os onefile precisam extrair seu runtime; o standalone precisa manter todos os arquivos auxiliares. Cache do SO, antivírus e carga do host não foram isolados. A amostra única de 10.000 transações verifica viabilidade, sem estimar p95 de processamento.

Artefatos de teste, retidos por sete dias na página da execução: `comparaofx-pyinstaller-candidate`, `comparaofx-nuitka-candidate` (standalone completo e onefile) e `comparaofx-comparison-results` (relatório). O SHA-256 do ZIP exibido na lista de artefatos é diferente do SHA-256 do EXE acima. Nenhum binário substituiu o legado; nenhuma release ou merge em master foi realizado.

## Recomendação e limitações finais

**Nuitka onefile é o candidato principal para homologação**: 7.933.952 bytes (7,566 MiB), aproximadamente 19% menor que PyInstaller e mediana até o menu de 356,6 ms contra 406,0 ms no mesmo runner. O p95 observado foi 382,9 ms contra 534,6 ms. A meta de um segundo foi atendida nessas amostras, sem garantia em outro computador. Não foi demonstrada diferença de confiabilidade: ambos passaram no mesmo protocolo financeiro e de recuperação. O standalone abriu mais rápido, mas exige 22 arquivos. PyInstaller permanece alternativa válida; na amostra única de 10.000 transações teve tempo de processamento menor (18,76 s contra 19,54 s), insuficiente para caracterizar uma diferença estável de desempenho.

A correção, a auditoria e a validação automatizada do release candidate estão concluídas. O executável corrigido está pronto para **homologação e revisão**, não para publicação definitiva automática. Permanecem pendentes a confirmação do novo EXE por duplo clique e em Windows sem Python, a homologação sintética de interrupções no destino e a aprovação do usuário. O sucesso informado para o executável anterior não foi usado como prova dessa homologação nova.

Limites mantidos: os runners têm Python para construir e executar o harness, portanto a ausência de Python no computador final ainda precisa ser confirmada; assinaturas/reputação do Windows e importadores OFX externos não foram homologados; não há garantia de durabilidade após falta de energia ou de concorrência com programas externos não cooperativos. OFX 1.x exclusivo pode rejeitar a saída XML 2.03. Não se afirma equivalência de cache frio nem ganho sobre a Etapa 5, cujas execuções usaram outros runners.

Artefato principal: [comparaofx-nuitka-candidate, seção Artifacts](https://github.com/vcsil/compararArquivosOFX/actions/runs/43413157659#artifacts), arquivo interno `onefile/ComparaOFX.exe`. O mesmo artefato contém a distribuição standalone; PyInstaller e o relatório de comparação têm artefatos separados na mesma execução. São arquivos de teste retidos por sete dias, sem release pública. O SHA-256 acima identifica o EXE, não o ZIP do GitHub.

O commit documental final usa `[skip ci]`: contém somente os documentos desta missão, sem alterar as fontes validadas em `116b6e7`. Não foi feito merge em master, tag de release, remoção de branches, migração de históricos ou substituição de `dist/Compara OFX.exe`. A liberação definitiva deve aguardar a revisão dos resultados e a aprovação explícita do usuário.
