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
