> Para o release candidate com a nomenclatura restaurada e manifestos v2, consulte [Validação final — Etapa 6](06-validacao-final.md). Os hashes e medições da Etapa 5 abaixo são históricos e não identificam o executável corrigido.

# Desempenho e candidatos — Etapa 5

## Status de Windows

O workspace local é Linux; a retomada usa runners Windows nativos do GitHub Actions. Resultados Windows observados, hashes e comparação são registrados ao final deste documento. As medições Linux históricas abaixo permanecem como referência do motor Python e não representam desempenho dos executáveis Windows. Validação manual por duplo clique e em uma máquina limpa sem Python permanece separada da automação.

## Perfil Linux sintético

Linux x86-64, Python 3.12.14, AMD EPYC 9V74 com 5 CPUs visíveis. `PYTHONPATH=src venv/bin/python scripts/profile_etapa5.py`; uma execução por tamanho, sem entrada interativa e com geração de dados fora das medições. Os tempos parciais são medições separadas; não somar como se fossem uma única execução. O fluxo integral inclui leitura, comparação, cópias, validação e publicação; sem controle de cache ou carga.

Linux-6.18.57-x86_64-with-glibc2.41 3.12.14
transações: 100
leitura bytes: 0.015 ms
hash SHA256: 0.024 ms
leitura e conversão inicial: 73.135 ms
análise primeira importação: 0.366 ms
construção modelo filtrado: 79.594 ms
serialização: 9.867 ms
conversão da saída: 67.303 ms
fluxo íntegro planejamento e execução: 261.129 ms
transações: 1000
leitura bytes: 0.024 ms
hash SHA256: 0.064 ms
leitura e conversão inicial: 695.960 ms
análise primeira importação: 1.715 ms
construção modelo filtrado: 745.176 ms
serialização: 83.938 ms
conversão da saída: 621.322 ms
fluxo íntegro planejamento e execução: 2205.406 ms
transações: 10000
leitura bytes: 0.433 ms
hash SHA256: 0.629 ms
leitura e conversão inicial: 7010.223 ms
análise primeira importação: 18.327 ms
construção modelo filtrado: 7452.091 ms
serialização: 889.620 ms
conversão da saída: 6551.674 ms
fluxo íntegro planejamento e execução: 22512.564 ms

A conversão do `ofxtools` é dominante: em 10.000 transações, leitura/conversão inicial aproximadamente 7,0 s, reconstrução do modelo 7,5 s, e releitura da saída 6,6 s. O perfil mostra as etapas antes do fluxo integral, que as repete. Não se substituiu o parser nem se suprimiu qualquer conferência financeira.

## Otimização verificada em Linux

Quando os bytes e a assinatura esperada do Geral são idênticos aos do Limpo já relido, o fluxo ainda lê e confere o hash de cada arquivo preparado, mas evita converter o mesmo conteúdo duas vezes. Se diferirem, ambos são convertidos e validados separadamente. O teste sintético verifica a quantidade de conversões e outro verifica rejeição de Geral temporário corrompido.

`PYTHONPATH=src venv/bin/python tests/benchmark_etapa4.py`, dez execuções independentes por tamanho, mediana/mínimo/máximo em ms:

Linux-6.18.57-x86_64-with-glibc2.41 3.12.14
100 lock mediana=0.283 min=0.145 max=0.467 ms n=10
100 hash mediana=0.499 min=0.441 max=0.580 ms n=10
100 temporarios mediana=6.097 min=4.630 max=8.454 ms n=10
100 validacao_ofx mediana=70.052 min=64.748 max=83.342 ms n=10
100 publicar_pasta mediana=0.977 min=0.774 max=1.928 ms n=10
100 publicar_geral mediana=0.393 min=0.221 max=0.452 ms n=10
100 finalizacao mediana=0.347 min=0.256 max=0.473 ms n=10
100 total mediana=250.628 min=236.225 max=272.913 ms n=10
1000 lock mediana=0.300 min=0.156 max=0.394 ms n=10
1000 hash mediana=1.408 min=1.365 max=1.530 ms n=10
1000 temporarios mediana=6.392 min=5.953 max=7.528 ms n=10
1000 validacao_ofx mediana=656.837 min=636.273 max=695.206 ms n=10
1000 publicar_pasta mediana=0.709 min=0.565 max=0.982 ms n=10
1000 publicar_geral mediana=0.289 min=0.209 max=0.609 ms n=10
1000 finalizacao mediana=0.266 min=0.210 max=0.535 ms n=10
1000 total mediana=2201.288 min=2139.884 max=2262.953 ms n=10

Na Etapa 4, nas mesmas categorias de primeira importação e em outra execução, as medianas foram 309,286 ms (100) e 2.939,943 ms (1.000); após a otimização, 250,628 ms e 2.201,288 ms. As condições de carga e cache não são controladas. Para 10.000, o perfil de execução única passou de 28.754,548 ms para 22.512,564 ms; não é uma mediana nem medição Windows. Uma recuperação sintética após publicação teve mediana 2,275 ms, mínimo 2,022 e máximo 2,788 em dez execuções, sem incluir a preparação nem a aquisição do bloqueio (`PYTHONPATH=src venv/bin/python scripts/benchmark_recuperacao.py`).

A Etapa 4 documenta separadamente hashes, sincronização e publicação. Não há medições de inicialização do empacotador, de candidatos Windows, de processamento Windows em duplicatas ou de cache; elas não foram estimadas. `scripts/benchmark_windows.ps1` fornece a coleta do menu para candidatos onefile depois de construídos. A primeira amostra não garante cache frio. Medidas detalhadas restantes e comparação de empacotadores dependem da validação nativa.

Na sessão anterior, a consulta ao histórico via API retornou `Forbidden`. A retomada mantém essa limitação da API, mas consulta páginas e anotações públicas autorizadas para registrar os resultados nativos abaixo.

## Revisão 5.1

As execuções Windows anteriores falharam e os jobs de build foram ignorados; consulte `05-executavel-windows.md`. A revisão acrescenta coleta no workflow para os dois onefile após build: menu completo com 15 amostras subsequentes, e processamento sintético de 100, 1.000 e 10.000 transações. Não há resultados Windows novos confirmados neste relatório. O tempo de processamento medido pelo script inclui arranque do processo e usa três amostras para 100/1.000, uma para 10.000; não deve ser confundido com o tempo isolado do motor ou com teste frio.

## Retomada da Etapa 5 — correções dos empacotadores

Workspace retomado diretamente da branch `codex/comparaofx-2.0-etapa5`, HEAD `1f0ef1a04a8af13100c41f538d47577241928dbe`, sem alterações preexistentes rastreadas. Não foi possível recuperar alterações locais do ambiente anterior; foram reconstruídas somente as correções ainda ausentes.

A página pública da execução [43340149477](https://github.com/vcsil/compararArquivosOFX/actions/runs/43340149477) confirma os erros: PyInstaller tentou calcular caminho relativo entre D: e C: (`ValueError: path is on mount`); Nuitka concluiu standalone, mas o smoke enviou `str` ao subprocesso binário (`TypeError: a bytes-like object is required`). O scratch do build agora fica em diretório exclusivo no volume do repositório, mantendo spec/entrada no mesmo volume, trabalho isolado e saída fora do `dist/` legado. Os scripts de smoke e processamento agora enviam `b'1\n'`; a leitura de dados financeiros permanece estrita e inalterada.

Validação local: Python 3.12.14/Linux, suíte completa com 124 testes, quatro ignorados por plataforma e sete falhas esperadas da baseline; nenhuma falha inesperada. Não há PowerShell ou Windows nativo neste ambiente. Resultados e métricas de executáveis Windows dependem da nova execução do workflow; não foram estimados. As proteções financeiras e o executável legado não foram modificados.

O commit de correção é `e2f86df`; a execução [43404969285](https://github.com/vcsil/compararArquivosOFX/actions/runs/43404969285) confirmou os testes Linux e Windows. Em seguida foi acrescentada regressão para a entrada binária dos dois scripts, usando subprocesso real (125 testes locais, quatro ignorados e sete falhas esperadas). O workflow publica tamanho, SHA-256, imagem do runner e benchmarks em resumo e anotação pública somente após sucesso do smoke e dos benchmarks, permitindo avaliar resultados mesmo quando a API autenticada retorna `Forbidden`.

Os dois scripts foram exercitados em Linux com um lançador temporário da aplicação Python, sem simular um executável congelado: smoke aprovado e processamento aprovado com 100/1.000/10.000 transações. Isso valida os scripts, mas não substitui a execução dos candidatos Windows e não entra na comparação de desempenho dos empacotadores.

### Raiz Nuitka e distribuição standalone

A documentação oficial incluída no pacote Nuitka 2.5.9 (`README.rst`, seções “Detecting Nuitka at run time” e “Onefile: Finding files”) confirma que Nuitka não define `sys.frozen`. A detecção passa a usar `__compiled__.containing_dir`, válido para standalone e onefile, antes da detecção PyInstaller existente. O teste cobre raiz externa à extração, diretório de trabalho diferente e prioridade da raiz explicitamente fornecida. Não altera planejamento, deduplicação ou publicação financeira.

Os benchmarks também copiam a distribuição completa quando o candidato está em `.dist`, preservando bibliotecas auxiliares. O workflow mede standalone e onefile separadamente e disponibiliza ambos como artefatos de teste, sem release. O conjunto local passou com 126 testes, quatro ignorados por plataforma e sete falhas esperadas.

Validação adicional: YAML carregado e todos os scripts/blocos PowerShell analisados pelo parser real PowerShell 7.4.6 em Linux, obtido da distribuição oficial com SHA-256 verificado. Essa análise verifica sintaxe, não substitui a execução nativa Windows.

### Smoke financeiro dos candidatos

O smoke foi ampliado para reimportar extrato sobreposto: o segundo Limpo deve conter apenas o novo FITID, o Geral deve conter dois FITIDs sem duplicação e os dois originais devem permanecer byte a byte idênticos. Em seguida, um valor conflitante sob FITID existente deve falhar, preservar a entrada e manter o Geral byte a byte inalterado. São dados exclusivamente sintéticos. O teste passou com o lançador Python local; a validação congelada é feita no workflow.

A execução `43404969285` confirmou compilação, smoke e benchmarks PyInstaller; Nuitka standalone compilou, mas falhou na verificação da pasta do executável. Isso confirma o problema de raiz tratado em `c2c981e`. A execução `43405255669`, de `64b92e8`, também aprovou PyInstaller, registrando 9.828.612 bytes (9,3733 MiB), SHA-256 `a968536d4a5804d9d6efb2d341301e668381ef562b669e7da1898b7992235917`. Sua anotação de tempos mostrou `System.Object[]`; a montagem da lista foi corrigida na revisão seguinte. Não interpretar o hash do ZIP do artefato como hash do executável.

### Ajuste da raiz standalone após evidência nativa

A execução [43405640308](https://github.com/vcsil/compararArquivosOFX/actions/runs/43405640308), commit `c2c981e`, ainda falhou no smoke standalone após compilar. A primeira interpretação de `containing_dir` estava incompleta: no código oficial de Nuitka 2.5.9, `CodeTemplatesConstants.py` aplica `STRIP_DIRNAME` no modo standalone, apontando para o pai de `.dist`. Portanto não atende ao requisito específico de procurar bancos dentro da pasta do executável standalone. A correção final detecta `__compiled__` e usa `Path(sys.argv[0]).resolve(strict=True).parent`. `MainProgram.c` normaliza `argv[0]` para o caminho absoluto do binário original, inclusive no onefile, como documentado no README da versão. O teste agora simula explicitamente `containing_dir` acima de `.dist` e a extração fora da raiz.

### Comparação no mesmo runner

As primeiras execuções usaram CPUs diferentes (EPYC 7763 e 9V74), e os tempos variaram mesmo sem mudanças no motor. O job `comparison`, dependente dos dois builds, baixa os três candidatos da mesma execução e repete smoke, 15 aberturas subsequentes e processamento de 100/1.000/10.000 transações sequencialmente no mesmo runner. Registra CPU, imagem, Python, bytes e SHA-256 dos artefatos baixados. Esses resultados têm prioridade para a recomendação; os tempos dos jobs de build ficam como diagnóstico. Cache do sistema operacional e carga do host não são controlados, e uma amostra de 10.000 transações não caracteriza distribuição de latência.

## Resultado consolidado da retomada

Execução [43407448255](https://github.com/vcsil/compararArquivosOFX/actions/runs/43407448255), commit `e41d639d7096473faa0c961853ee1a4198a65318`. Os jobs de testes Linux, testes Windows, PyInstaller, Nuitka e comparação terminaram com sucesso. As medidas abaixo vêm exclusivamente do job `comparison`, que baixou e revalidou os três artefatos no mesmo runner. Os hashes coincidem com os publicados pelos jobs de build.

Ambiente de comparação: AMD EPYC 9V74 80-Core Processor, imagem `win25-vs2026/20261103.298.1`, Python 3.12.10. Ferramentas de build: PyInstaller 6.11.1 e Nuitka 2.5.9. Os runners de build e comparação são instâncias diferentes; nenhum resultado depende de manter seus processos vivos.

Todos os candidatos passaram no menu, pasta do executável com espaços/acentos, início a partir de outro diretório, leitura e saída OFX sintética, original byte a byte preservado, reimportação com deduplicação e rejeição de conflito de FITID mantendo entrada e Geral intactos. A suíte local executou 126 testes: 115 aprovados, quatro ignorados por plataforma e sete falhas esperadas da baseline; os dois jobs nativos da suíte também foram aprovados. Os totais de skips Windows não foram extraídos de logs autenticados.

| Candidato | EXE bytes | EXE MiB | Arquivos da distribuição | Distribuição bytes |
|---|---:|---:|---:|---:|
| PyInstaller onefile | 9828704 | 9.373 | 1 | 9828704 |
| Nuitka standalone | 12111872 | 11.551 | 22 | 27917672 |
| Nuitka onefile | 7929344 | 7.562 | 1 | 7929344 |

| Candidato | SHA-256 do EXE |
|---|---|
| PyInstaller onefile | `5c14d78e30295b6134552bef3d6846f71772cdfee14ea0e48bd7360c42a9654c` |
| Nuitka standalone | `6454ccf1bad1b542b9df5febf5cb139492f9ba2f2b59da1b4c619da863750fa5` |
| Nuitka onefile | `2d2f7f87395ac70f09ffeff3bdf23aa74f9d84c8c170c43b5ac8ac91e5dbf307` |

Tempos até o menu completo, em milissegundos. Primeira abertura observada, seguida de 15 execuções; p95 por posto mais próximo.

| Candidato | Primeira | n subsequentes | Mediana | Mínimo | Máximo | p95 |
|---|---:|---:|---:|---:|---:|---:|
| PyInstaller onefile | 757.109 | 15 | 862.8712 | 351.083 | 1198.9808 | 1198.9808 |
| Nuitka standalone | 245.5577 | 15 | 44.7825 | 43.7629 | 48.8047 | 48.8047 |
| Nuitka onefile | 688.7537 | 15 | 742.0144 | 435.0168 | 1130.9713 | 1130.9713 |

Processamento em milissegundos, incluindo inicialização do processo e excluindo geração do OFX sintético.

| Candidato | Transações | n | Mediana | Mínimo | Máximo |
|---|---:|---:|---:|---:|---:|
| PyInstaller onefile | 100 | 3 | 1526.595 | 1327.500 | 1803.910 |
| PyInstaller onefile | 1000 | 3 | 3778.572 | 3603.678 | 4293.146 |
| PyInstaller onefile | 10000 | 1 | 26523.106 | 26523.106 | 26523.106 |
| Nuitka standalone | 100 | 3 | 741.976 | 638.254 | 889.322 |
| Nuitka standalone | 1000 | 3 | 3209.044 | 3177.715 | 3359.127 |
| Nuitka standalone | 10000 | 1 | 30100.942 | 30100.942 | 30100.942 |
| Nuitka onefile | 100 | 3 | 1728.166 | 1331.843 | 1915.392 |
| Nuitka onefile | 1000 | 3 | 4118.128 | 4045.323 | 4226.398 |
| Nuitka onefile | 10000 | 1 | 28299.472 | 28299.472 | 28299.472 |

A primeira abertura não representa cache frio garantido. Não foi configurado cache persistente de extração. Os onefile precisam extrair seu runtime; o standalone precisa manter todos os arquivos auxiliares. Cache do SO, antivírus e carga do host não foram isolados. A amostra única de 10.000 transações verifica viabilidade, sem estimar p95 de processamento.

Artefatos de teste, retidos por sete dias na página da execução: `comparaofx-pyinstaller-candidate`, `comparaofx-nuitka-candidate` (standalone completo e onefile) e `comparaofx-comparison-results` (relatório). O SHA-256 do ZIP exibido na lista de artefatos é diferente do SHA-256 do EXE acima. Nenhum binário substituiu o legado; nenhuma release ou merge em master foi realizado.

### Recomendação e limites finais

Recomendação para o requisito de arquivo único portátil: **Nuitka onefile**. Nessa medição no mesmo runner, foi aproximadamente 19% menor e teve mediana até o menu aproximadamente 14% menor que PyInstaller. Ambos passaram nos mesmos testes; não foi demonstrada diferença de confiabilidade. O PyInstaller teve processamento numericamente menor nas três cargas, sendo alternativa válida quando esse tempo pesar mais que abertura e tamanho. O standalone abriu mais rápido (44,8 ms de mediana), mas exige os 22 arquivos da distribuição e não atende à preferência por arquivo único. A meta de um segundo foi atingida na mediana dos dois onefile, mas não no p95; não é uma garantia em outro computador.

A validação automatizada da Etapa 5 está aprovada. A conclusão integral permanece pendente de homologação em um Windows de destino sem Python instalado e da interação por duplo clique: os runners usados possuem Python para construir e executar os scripts de teste. O smoke move os executáveis para pastas isoladas, mas isso não comprova ausência de Python na máquina. Não foi testado cache persistente nem durabilidade após falta de energia; permanecem os limites documentados na Etapa 4.

Para essa homologação, baixe `comparaofx-nuitka-candidate` na execução acima e separe `onefile/ComparaOFX.exe`. Em uma pasta de teste com espaços/acentos, coloque o EXE, uma cópia de `tests/fixtures/windows-manual/Entrada.ofx` e uma pasta vazia `Banco Sintetico`. Use somente esse extrato sintético. Confira o SHA-256 do EXE da tabela. Abra primeiro por duplo clique e cancele com `0`; depois inicie a partir de outro diretório e selecione `1`. Confirme que o Limpo e o Geral contêm o crédito de BRL 20 com FITID `SYNTH-1`, e que a cópia arquivada tem o mesmo SHA-256 da entrada sintética, registrada antes da execução. O terminal deve continuar visível após o processamento interativo. Registre versão do Windows, resultados e qualquer alerta de execução. Nenhuma instalação de Python deve ser necessária nesse computador.

Commits de implementação publicados diretamente em `codex/comparaofx-2.0-etapa5`: `e2f86df` (volumes e stdin), `64b92e8` (regressão e métricas), `c2c981e` (primeira detecção Nuitka e standalone), `0d3af87` (smoke financeiro), `350b737` (raiz Nuitka corrigida após evidência nativa) e `e41d639` (comparação no mesmo runner). O commit documental final usa `[skip ci]` para não reconstruir binários cuja fonte não mudou; os resultados acima se referem explicitamente a `e41d639`. A Etapa 6 não foi iniciada.

## Release candidate corrigido — Etapa 6

A execução [43413157659](https://github.com/vcsil/compararArquivosOFX/actions/runs/43413157659), commit `116b6e7`, aprovou testes Linux/Windows, os três builds e a comparação no mesmo runner. O smoke exige `OFX Limpo-DDMMAAAAHHMM.ofx`, horário local da geração e recuperação de manifestos v1 e v2 sem alteração de nomes ou bytes já publicados. O formato anterior da Etapa 5 não foi reutilizado como se contivesse a correção.

| Candidato | EXE bytes | EXE MiB | Mediana até o menu (ms) | SHA-256 do EXE |
|---|---:|---:|---:|---|
| PyInstaller onefile | 9830401 | 9.375 | 405.969 | `86d35fc456b6e192b3f066be64aedb1d20051c644c8ef30d183b974a1b5881bf` |
| Nuitka standalone | 12125696 | 11.564 | 35.862 | `32269290dfe96d41180b2f6501b4c70ca6926eeda6c2953bf4723194c9d01c12` |
| Nuitka onefile | 7933952 | 7.566 | 356.584 | `97a187562f231e839313b50a8a83af946cac2c2b34617ee64ef974ccdf28d1ee` |

Nuitka onefile é o candidato principal para homologação; PyInstaller permanece alternativa. A distribuição standalone completa exige 22 arquivos (27.931.496 bytes). Valores de build separados não foram misturados à comparação: a tabela usa o mesmo runner EPYC 9V45, Python 3.12.10 e imagem `win25-vs2026/20261103.298.1`, com 15 aberturas subsequentes. Primeira abertura, mínimo, máximo, p95, processamento de 100/1.000/10.000 transações, auditoria, compatibilidade e procedimento de homologação estão em [06-validacao-final.md](06-validacao-final.md).

A homologação do EXE novo em Windows sem Python e por duplo clique continua pendente; o usuário confirmou apenas o executável anterior. Nenhuma release definitiva, merge em master ou alteração no executável legado foi realizada.
