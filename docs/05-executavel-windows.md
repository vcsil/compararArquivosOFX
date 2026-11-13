# Executável Windows — Etapa 5

**Validação nativa e escolha final pendentes.** O ambiente de desenvolvimento disponível é Linux; nenhum executável Windows foi construído ou executado nele. Não há candidato validado, tamanho ou SHA-256 a divulgar. Não substitua `dist/Compara OFX.exe`, não distribua como release e não use a aplicação para dados reais antes de passar os testes no Windows.

O workflow `.github/workflows/windows-validation.yml` executa a suíte em `ubuntu-latest` e `windows-latest`; após sucesso, jobs separados tentam construir candidatos temporários PyInstaller 6.11.1 onefile e Nuitka 2.5.9 standalone e onefile, em Python 3.12. O script `scripts/build_windows.ps1` cria ambiente isolado, instala as dependências versionadas, executa testes, compila fora de `dist/`, verifica arquivo e executa `scripts/smoke_exe.py` com OFX sintético em diretório temporário com espaços e acentos, processo iniciado a partir de outro diretório. Ao final imprime tamanho e SHA-256. O workflow oferece artefatos de teste por sete dias; não cria release. Os scripts e workflow ainda precisam ser executados e avaliados no Windows.

Em Windows com Python 3.12 para construção:

```powershell
./scripts/build_windows.ps1 -Tool pyinstaller -OutputDir "$env:TEMP/compara-pyinstaller"
./scripts/build_windows.ps1 -Tool nuitka -OutputDir "$env:TEMP/compara-nuitka"
./scripts/benchmark_windows.ps1 -Exe "$env:TEMP/compara-pyinstaller/ComparaOFX.exe" -Runs 15
Get-FileHash -Algorithm SHA256 "$env:TEMP/compara-pyinstaller/ComparaOFX.exe"
```

O Python é necessário para construir e testar, não para executar um candidato onefile corretamente gerado. O script de benchmark usa dados sintéticos, inicia um processo por medição, lê até a linha completa do menu e cancela pela entrada redirecionada. Relata a primeira amostra, 15 subsequentes, mediana, mínimo, máximo e p95; não controla cache do SO e não prova execução fria. O programa aguarda Enter ao final somente com stdin e stdout interativos, mantendo a janela aberta; com pipes não espera. A experiência real por duplo clique, acentuação e uso sem Python ainda precisam de teste manual no Windows.

A raiz em modo congelado deriva de `sys.executable`, não de `_MEIPASS`; o smoke verifica a localização efetiva para cada candidato. Não é possível presumir que Nuitka onefile use o mesmo caminho que PyInstaller: uma falha do smoke impede aprová-lo. Não foi selecionado empacotador e nenhuma variante de cache persistente foi testada. O build Nuitka pode depender do compilador instalado no runner e de downloads autorizados. O arquivo não é assinado: alertas de reputação e políticas de distribuição permanecem possíveis. Arquivos de usuário e históricos não devem ser gravados em cache de extração.

Diagnóstico: execute a suíte e revise os logs do workflow. `COMPARAOFX_DEBUG=1` permite traceback e pode conter dados sensíveis; não compartilhe logs de arquivos reais. Antes de aprovar um executável, confira seu SHA-256, fluxo por duplo clique, integridade em NTFS, recuperação, concorrência e suas limitações em outros sistemas de arquivos.

Os números de versão das ferramentas diretas estão fixados, mas as dependências transitivas e as imagens `windows-latest` não estão fixadas por hash; o processo é reproduzível como receita, não como garantia de binários idênticos. É necessário registrar a imagem, versões efetivas e hashes de cada execução antes de comparar artefatos.

O workflow foi publicado na branch `codex/comparaofx-2.0-etapa5`, mas nesta sessão a consulta `gh run list` ao endpoint de Actions retornou `Forbidden`. Assim, não foi possível confirmar se um runner foi iniciado, os resultados dos jobs ou a existência de artefatos. Consulte ou execute manualmente o workflow na aba Actions do repositório e confira os logs de cada job; a publicação da branch, por si só, não valida o executável.

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
