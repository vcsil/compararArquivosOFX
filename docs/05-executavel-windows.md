# Executável Windows — Etapa 5

**Retomada com validação nativa no GitHub Actions.** O workspace local é Linux; os executáveis Windows são construídos e executados nos runners nativos. PyInstaller onefile, Nuitka standalone e Nuitka onefile passaram nos testes nativos; a comparação no mesmo runner e os hashes estão registrados ao final deste documento. O executável legado `dist/Compara OFX.exe` permanece intacto. Não foi criada release final.

O workflow `.github/workflows/windows-validation.yml` executa a suíte em `ubuntu-latest` e `windows-latest`; após sucesso, jobs separados tentam construir candidatos temporários PyInstaller 6.11.1 onefile e Nuitka 2.5.9 standalone e onefile, em Python 3.12. O script `scripts/build_windows.ps1` cria ambiente isolado, instala as dependências versionadas, executa testes, compila fora de `dist/`, verifica arquivo e executa `scripts/smoke_exe.py` com OFX sintético em diretório temporário com espaços e acentos, processo iniciado a partir de outro diretório. Ao final imprime tamanho e SHA-256. O workflow oferece artefatos de teste por sete dias; não cria release. Os resultados efetivamente observados estão registrados na seção de retomada abaixo.

Em Windows com Python 3.12 para construção:

```powershell
./scripts/build_windows.ps1 -Tool pyinstaller -OutputDir "$env:TEMP/compara-pyinstaller"
./scripts/build_windows.ps1 -Tool nuitka -OutputDir "$env:TEMP/compara-nuitka"
./scripts/benchmark_windows.ps1 -Exe "$env:TEMP/compara-pyinstaller/ComparaOFX.exe" -Runs 15
Get-FileHash -Algorithm SHA256 "$env:TEMP/compara-pyinstaller/ComparaOFX.exe"
```

O Python é necessário para construir e testar, não para executar um candidato onefile corretamente gerado. O script de benchmark usa dados sintéticos, inicia um processo por medição, lê até a linha completa do menu e cancela pela entrada redirecionada. Relata a primeira amostra, 15 subsequentes, mediana, mínimo, máximo e p95; não controla cache do SO e não prova execução fria. O programa aguarda Enter ao final somente com stdin e stdout interativos, mantendo a janela aberta; com pipes não espera. A experiência real por duplo clique, acentuação e uso sem Python ainda precisam de teste manual no Windows.

A raiz PyInstaller deriva de `sys.executable`, não de `_MEIPASS`; a raiz Nuitka usa `sys.argv[0]` ao detectar `__compiled__`; o smoke verifica a localização efetiva para cada candidato. Não é possível presumir que Nuitka onefile use o mesmo caminho que PyInstaller: uma falha do smoke impede aprová-lo. A recomendação atual está no resultado consolidado; nenhuma variante de cache persistente foi testada. O build Nuitka pode depender do compilador instalado no runner e de downloads autorizados. O arquivo não é assinado: alertas de reputação e políticas de distribuição permanecem possíveis. Arquivos de usuário e históricos não devem ser gravados em cache de extração.

Diagnóstico: execute a suíte e revise os logs do workflow. `COMPARAOFX_DEBUG=1` permite traceback e pode conter dados sensíveis; não compartilhe logs de arquivos reais. Antes de aprovar um executável, confira seu SHA-256, fluxo por duplo clique, integridade em NTFS, recuperação, concorrência e suas limitações em outros sistemas de arquivos.

Os números de versão das ferramentas diretas estão fixados, mas as dependências transitivas e as imagens `windows-latest` não estão fixadas por hash; o processo é reproduzível como receita, não como garantia de binários idênticos. É necessário registrar a imagem, versões efetivas e hashes de cada execução antes de comparar artefatos.

Na sessão anterior, `gh run list` retornou `Forbidden`. Na retomada, a API continuou bloqueada, mas páginas e anotações públicas permitiram confirmar jobs, falhas, artefatos e métricas. Não foi necessário solicitar token ou contornar controles de acesso.

## Revisão 5.1

As execuções [43338267223](https://github.com/vcsil/compararArquivosOFX/actions/runs/43338267223) e [43338215678](https://github.com/vcsil/compararArquivosOFX/actions/runs/43338215678), informadas pelo usuário, falharam em `tests (windows-latest)`; a primeira página pública confirma a falha e mostra anotações na verificação de diretório de `workflow.py`. O usuário informou 49 erros, uma falha e sete falhas esperadas; os builds foram ignorados. A raiz era resolvida para nome longo enquanto caminhos de entrada continuavam com nomes curtos 8.3. A revisão verifica pontos de reparse antes de resolver, usa `samefile` para o pai e reconstrói caminhos normalizados a partir da raiz validada. Bloqueio e recuperação também normalizam a instituição após verificar links. O teste de raiz usa identidade em vez de representação textual. Logs diagnósticos de subprocessos usam escape tolerante; arquivos financeiros continuam com decodificação estrita. Testes novos cobrem caminhos relativos, acentos, hardlinks e links; casos 8.3, maiúsculas e junction exigem runner Windows e podem ser ignorados apenas se o volume ou política não suportar a criação necessária.

O workflow também chama `scripts/benchmark_windows.ps1` para 15 aberturas subsequentes e `scripts/benchmark_exe_processing.py` para importações sintéticas de 100, 1.000 e 10.000 transações. O processamento inclui início do executável e exclui a preparação dos dados; são três amostras para 100/1.000 e uma para 10.000. Resultados só são válidos após a execução real dos jobs; o teste não substitui validação por duplo clique ou em computador sem Python.

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
