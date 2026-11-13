# Desempenho e candidatos — Etapa 5

## Status de Windows

Não existe runner Windows local nesta sessão. O workflow `windows-validation.yml` prepara testes e candidatos, mas nenhuma execução nativa foi confirmada até a criação deste relatório. Tempos de arranque Windows, tamanho/hash de executáveis, uso por duplo clique, compatibilidade com `msvcrt`, PyInstaller, Nuitka e cache persistente estão pendentes. Nenhum empacotador foi escolhido. Resultados Linux não são tempos do executável Windows.

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

Após a publicação da branch, a consulta ao histórico de execuções do GitHub Actions retornou `Forbidden` nesta sessão. Portanto não há identificador de execução, logs ou medições de runner para registrar aqui.

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
