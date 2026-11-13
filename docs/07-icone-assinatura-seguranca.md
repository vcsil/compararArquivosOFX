# Ícone legado, assinatura Authenticode e alerta do Microsoft Defender

## Estado de segurança

Em 13/11/2026, o Microsoft Defender sinalizou uma execução do candidato Nuitka onefile como `Program:Win32/Contebrew.A!ml`, com gravidade alta. A causa **não foi determinada**. Revisão de código e testes de integridade não comprovam que o executável empacotado esteja livre de malware; é necessário conferir a cadeia de produção, dependências, binários finais e análise da Microsoft.

**Não permitir o arquivo sinalizado nem desativar o antivírus.** Mantenha-o em quarentena e faça verificação completa. Submeta a versão exata do binário para reanálise oficial em https://www.microsoft.com/en-us/wdsi/filesubmission/ e guarde o identificador da submissão e o parecer. Não compartilhe OFX reais com serviços de análise ou scanners públicos.

## Ícone da versão antiga e recurso atual

O repositório conserva `dist/Compara OFX.exe`, sem modificá-lo. A configuração inicial desta branch extraía o ícone diretamente desse EXE. A revisão atual extraiu sua única imagem RGBA e armazenou a versão azul em `assets/comparaofx-2.0-azul.ico`; o build agora fornece esse arquivo a PyInstaller (`--icon`) e Nuitka (`--windows-icon-from-ico`) e verifica os recursos incorporados antes do smoke. O ícone é apenas identidade visual e não altera a segurança do binário.

## Assinatura real

Authenticode requer **certificado legítimo de assinatura de código**, com chave privada controlada exclusivamente pelo titular, ou serviço gerenciado de assinatura. **Não existe certificado ou chave privada incluído neste repositório.** Nenhum executável deve ser descrito como assinado até ser realmente assinado e validado.

A assinatura opcional usa `scripts/sign_windows.ps1`, com um thumbprint SHA-1 do certificado Code Signing na loja pessoal do Windows. Ela executa `signtool sign`, com digest SHA-256 e carimbo de tempo RFC 3161, verifica usando `signtool verify /pa /v` e `Get-AuthenticodeSignature`, e calcula o SHA-256 **após** a assinatura. Exige Windows SDK/SignTool e certificado confiável válido com chave privada acessível ao processo.

Com o certificado instalado num computador de build confiável (exemplo, substitua pelo thumbprint real):

```powershell
./scripts/build_windows.ps1 -Tool nuitka -OutputDir "$env:TEMP/comparaofx-nuitka" -SignThumbprint "0123456789ABCDEF0123456789ABCDEF01234567"
Get-AuthenticodeSignature "$env:TEMP/comparaofx-nuitka/onefile/ComparaOFX.exe" | Format-List Status,SignerCertificate,TimeStamperCertificate
Get-FileHash -Algorithm SHA256 "$env:TEMP/comparaofx-nuitka/onefile/ComparaOFX.exe"
```

Sem `-SignThumbprint` o build permanece **não assinado**, o que deve ser declarado explicitamente. Use secret store/HSM/serviço de assinatura apropriado; não armazene arquivo .pfx, senha, token, chave privada, ou certificado de assinatura com chave privada no Git, em artifacts ou logs. Para assinatura em CI será necessário configurar separadamente a identidade e as permissões do serviço de assinatura, sem exposição de segredos.

**Assinar não corrige código malicioso, não garante que o Defender deixe de alertar e não substitui análise antivírus**. A confiança depende também de identidade do editor, cadeia certificadora, reputação, SmartScreen e políticas do dispositivo.

## Critérios para autorização de release

1. Revisar fontes, dependências, builds, proveniência e permissões de workflows e actions; fixar versões e verificar integridade.
2. Reproduzir builds em Windows e validar ícone nos executáveis PyInstaller e Nuitka.
3. Testar hashes de saída, assinatura Authenticode, carimbo de tempo e identidade real do editor; nenhum resultado pode ser presumido.
4. Fazer análise local do executável final no Defender atualizado sem desativá-lo, e registrar qualquer detecção.
5. Se houver detecção, manter em quarentena e enviar a amostra para análise oficial; **não publicar nem recomendar exceção de antivírus**.
6. Publicar SHA-256 e versão do **arquivo assinado final** (não usar hash anterior ao processo de assinatura).
7. Somente após testes de segurança e autorização explícita do usuário considerar release.

Não modificar o motor de deduplicação, históricos reais, nem permitir escalonamento de privilégios para suprimir alertas.


## Ícone azul e validação

O executável legado contém um único recurso PNG RGBA de 256 × 256. `scripts/recolor_icon.py` lê o recurso PE com `pefile`, preserva geometria, alfa e pixels neutros, e substitui matizes verdes por azul de matiz 221° (referência #2563EB), mantendo variações de brilho e saturação. Para reproduzir com as versões usadas na geração, instale `pefile==2024.8.26` e `Pillow==13.0.0`; execute `venv/bin/python scripts/recolor_icon.py` na raiz. Foram gerados PNG, comparação visual e ICO com 16, 24, 32, 48, 64, 128 e 256 pixels; os tamanhos menores são reamostrados do único original.

As duas cores dominantes do original, `#0EE565` e `#00C67F`, passaram respectivamente a `#356DE5` e `#2457C6`; os cinzas estruturais `#1D2321` e `#363D3B` foram preservados.

A transformação converte RGB para HSV e altera apenas pixels com alfa não nulo, saturação maior que 0,25 e matiz entre 0,27 e 0,49: fixa matiz em 221°, multiplica a saturação por 0,82 e preserva o brilho e o alfa. Os demais pixels permanecem inalterados na imagem de 256 pixels. O Pillow gera as resoluções menores com reamostragem Lanczos.

Ambos empacotadores usam `assets/comparaofx-2.0-azul.ico`. `scripts/verify_icon.py` lê o primeiro grupo de ícones do PE e compara imagens e alfa com cada resolução do ICO, antes do smoke financeiro e da assinatura opcional. O build instala `pefile==2024.8.26` e `Pillow==11.3.0` para essa inspeção. A compilação normal permanece sem certificado e os candidatos são não assinados.

A detecção anterior `Program:Win32/Contebrew.A!ml` não foi esclarecida. Não há Microsoft Defender neste ambiente Linux; a alteração visual não constitui correção de segurança. Os resultados observados do workflow, inspeção PE, hashes e benchmarks estão registrados na seção final deste documento. Caso haja detecção, interrompa a aprovação e submeta o binário à Microsoft para análise oficial, sem dados reais.

O build consulta o estado do Defender no Windows e, quando ativo, tenta atualizar as assinaturas e executar verificação individual antes do smoke. A versão e data das definições são registradas; uma detecção associada ao arquivo bloqueia o build. Se o serviço não estiver disponível, isso é registrado como não verificado. Não são criadas exclusões nem alterada a política do antivírus.

A revisão estática da aplicação não identificou comandos externos, persistência ou comunicação de rede. Os scripts de teste executam candidatos sintéticos; o build invoca Python, pip e os empacotadores; e a assinatura opcional invoca o SignTool. O build instala dependências do PyPI, Nuitka pode baixar ferramentas adicionais, a atualização do Defender acessa suas fontes e a assinatura opcional usa o serviço de carimbo de tempo configurado. `colorama` e `ofxtools` estão fixados; dependências transitivas e imagens de CI não são fixadas por hash. Essa revisão não verifica a integridade de todos os artefatos de terceiros nem prova a segurança dos executáveis.

Sem certificado, o build exige que `Get-AuthenticodeSignature` retorne `NotSigned`; com certificado configurado, o script opcional valida a assinatura.

As actions do GitHub usadas no workflow são referenciadas por tags de versão, não por commits imutáveis. Os pacotes diretos do build têm versões selecionadas; downloads transitivos e ferramentas externas do Nuitka não têm hashes fixados neste repositório. A receita e os hashes finais permitem identificar os resultados, mas não garantem reconstrução binária idêntica nem estabelecem a integridade independente de toda a cadeia.

## Preparação para análise oficial da detecção anterior

A amostra anteriormente sinalizada continua sem diagnóstico. O hash do arquivo efetivamente detectado e a versão das assinaturas usadas naquela detecção não foram fornecidos; não se deve presumir que coincidam com os binários reconstruídos nesta execução. Preserve a amostra em quarentena e obtenha os dados diretamente do histórico de proteção. Não use extratos ou históricos reais como amostras.

Para revisão antes do envio em https://www.microsoft.com/en-us/wdsi/filesubmission/, preencha com o hash da amostra exata, nome `Program:Win32/Contebrew.A!ml`, data/hora e fuso da ocorrência, versão das assinaturas Defender, versão do Windows e contexto de que o alerta ocorreu antes do menu. Texto sugerido: “Solicito análise deste executável; o Microsoft Defender o identificou como Program:Win32/Contebrew.A!ml antes da abertura do menu. A causa ainda não foi determinada. SHA-256: [hash da amostra exata]. Versão das assinaturas: [versão observada].” Anexe somente a amostra solicitada pela Microsoft e registre o identificador e o parecer. Nenhuma submissão foi feita nesta sessão.

Na execução anterior [43404969285](https://github.com/vcsil/compararArquivosOFX/actions/runs/43404969285), com Nuitka 2.5.9 e receita semelhante, o diagnóstico público registrou download do compilador WinLibs pelo repositório `brechtsanders/winlibs_mingw` no GitHub e do Dependency Walker em `dependencywalker.com`. Esses registros são evidência daquela execução; os logs completos da execução atual não estão acessíveis nesta sessão, portanto não se afirma que os mesmos arquivos ou hashes tenham sido usados nela. O executável legado é um arquivo versionado no repositório; sua origem anterior ao repositório e uma cadeia de assinatura confiável não foram estabelecidas.

## Resultado da validação final

A execução [43443405205](https://github.com/vcsil/compararArquivosOFX/actions/runs/43443405205) validou o commit `c7bc33c1df3a7d370ae0399a9e939579348eddf1`. Linux, Windows, PyInstaller, Nuitka e comparação terminaram com sucesso. A suíte local executou 146 testes, com quatro ignorados por plataforma e sete falhas esperadas históricas; nenhuma falha inesperada. Os jobs de teste Linux e Windows também passaram.

Os três candidatos foram executados no Windows com OFX sintético: menu, seleção, datas no Limpo, Geral, cópias byte a byte, deduplicação, conflito de FITID e recuperação v1/v2. `verify_icon.py` leu o primeiro grupo de ícones do PE e comparou cores e alfa nas sete resoluções com o ICO; a abertura real do PE e os smokes também passaram. Sem certificado, `Get-AuthenticodeSignature` retornou `NotSigned` para os três. A confirmação visual em uma instalação do Explorer no computador de destino é independente desse teste de recursos.

O executável legado permaneceu idêntico ao da Etapa 6; seu SHA-256 é `9b50626d748626bd16fffbe0a9582c935cdd5e20675d67633872a3c5c11fa0d3`. O ICO azul tem SHA-256 `a7b9ae57df1bf502830a88484d4eb80454c2e87e74f9e06ab4f404bed1667fc2`. A comparação visual está em `assets/comparacao-icones.png`.

| Candidato | EXE bytes | EXE MiB | Arquivos da distribuição | Distribuição bytes | SHA-256 do EXE |
|---|---:|---:|---:|---:|---|
| PyInstaller onefile | 9807873 | 9.354 | 1 | 9807873 | `279f220e826b1b46402458eba42fda7bbe12c9c54e9f5e1164fee2966c0267ad` |
| Nuitka standalone | 12163072 | 11.600 | 22 | 27968872 | `c01098545aad630d9a7e93542187f3bb9916afea638e42be374c4c7eb77e67f4` |
| Nuitka onefile | 8005120 | 7.634 | 1 | 8005120 | `8b0f1957535eaa738c1282ca670dfd9fe7939fb5bb9bee48ffa813c25b219f25` |

A comparação seguinte foi feita em um único runner AMD EPYC 7763 64-Core Processor, imagem `win25-vs2026/20261103.298.1`, Python 3.12.10. Os hashes dos arquivos baixados para comparação coincidem com os publicados pelos builds.

| Candidato | Primeira (ms) | n subsequentes | Mediana (ms) | Mínimo (ms) | Máximo (ms) | p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| PyInstaller onefile | 539.751 | 15 | 503.4803 | 353.1735 | 618.8071 | 618.8071 |
| Nuitka standalone | 119.5364 | 15 | 56.9775 | 54.8849 | 60.8455 | 60.8455 |
| Nuitka onefile | 399.8199 | 15 | 360.7707 | 281.9193 | 427.2507 | 427.2507 |

Processamento sintético, incluindo abertura do processo e excluindo geração dos dados:

| Candidato | Transações | n | Mediana (ms) | Mínimo (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| PyInstaller onefile | 100 | 3 | 1500.980 | 1428.078 | 1527.215 |
| PyInstaller onefile | 1000 | 3 | 4750.467 | 4748.143 | 4824.563 |
| PyInstaller onefile | 10000 | 1 | 37093.153 | 37093.153 | 37093.153 |
| Nuitka standalone | 100 | 3 | 775.514 | 769.472 | 796.302 |
| Nuitka standalone | 1000 | 3 | 4162.113 | 4105.493 | 4173.691 |
| Nuitka standalone | 10000 | 1 | 39701.028 | 39701.028 | 39701.028 |
| Nuitka onefile | 100 | 3 | 1158.282 | 1152.572 | 1223.876 |
| Nuitka onefile | 1000 | 3 | 4558.272 | 4398.745 | 4589.306 |
| Nuitka onefile | 10000 | 1 | 39363.465 | 39363.465 | 39363.465 |

A primeira medição não garante cache frio; carga, antivírus e cache do SO não foram isolados. Para 10.000 transações há uma única amostra. Os tempos da Etapa 6 foram obtidos em outro runner e, quando em outra CPU, não são comparáveis diretamente. Não houve mudança do motor financeiro.

Defender: três verificações concluídas sem detecção associada aos arquivos ou à distribuição examinados, com assinatura(s) 1.463.281.0; data(s) das assinaturas: 13/11/2026 04:41:16 -0300. O build tentou atualizar as definições antes da análise. A varredura de standalone incluiu sua pasta completa. Esse resultado não prova que a detecção anterior era falsa nem garante o resultado em outro sistema.

Os artefatos de teste estão na [seção Artifacts da execução](https://github.com/vcsil/compararArquivosOFX/actions/runs/43443405205#artifacts): `comparaofx-pyinstaller-candidate`, `comparaofx-nuitka-candidate` e `comparaofx-comparison-results`, com retenção de sete dias. No ZIP Nuitka, o candidato de arquivo único está em `onefile/ComparaOFX.exe`; o outro é a distribuição standalone. O hash do ZIP é diferente do hash do EXE.

Os candidatos estão tecnicamente validados nas condições descritas, mas são não assinados e a ocorrência anterior `Program:Win32/Contebrew.A!ml` ainda precisa de esclarecimento. A análise no computador de destino e a revisão da amostra anteriormente sinalizada permanecem necessárias antes de aprovar uso com dados financeiros. Não houve merge em master, release pública ou substituição do executável legado. Este registro documental usa `[skip ci]`; os executáveis correspondem ao commit de código acima.

## Investigação de desempenho e alterações publicadas

Para investigar possível regressão sem misturar modelos de CPU, foram consultados também os jobs de build da Etapa 6 ([43413157659](https://github.com/vcsil/compararArquivosOFX/actions/runs/43413157659)) e desta revisão, ambos identificados como AMD EPYC 7763 e com a mesma imagem Windows. Em máquinas virtuais diferentes, a mediana de menu PyInstaller passou de 502,0 para 511,0 ms e a de Nuitka onefile de 566,4 para 386,1 ms. Para 10.000 transações, os valores únicos foram 36,80 e 36,97 s para PyInstaller e 38,61 e 38,54 s para Nuitka, respectivamente. Não há indício de aumento expressivo nessa observação; carga e cache não foram controlados, portanto os números não demonstram causalidade nem substituem uma comparação pareada. A tabela principal usa exclusivamente o mesmo runner para os três candidatos atuais.

A branch foi retomada no commit `775f465`. Os commits desta missão são `00523ff` (ícone azul e inspeção PE), `8dbd1ad` e `6434ec5` (verificação Defender, incluindo a distribuição standalone), `4ea677c` (verificação Authenticode) e `c7bc33c` (ícone principal e diagnóstico de ameaça). O commit documental final registra os resultados acima. Foram alterados o workflow Windows, `scripts/build_windows.ps1`, `scripts/recolor_icon.py`, `scripts/verify_icon.py`, `scripts/scan_defender.ps1`, os três arquivos em `assets/` e este relatório. `scripts/sign_windows.ps1`, já existente na branch, foi revisado e preservado. O código da aplicação, dependências de execução e executável legado não foram modificados.

> Atualização: as contagens de 146 acima são históricas dos respectivos commits. O workflow da missão de otimização [43455514175](https://github.com/vcsil/compararArquivosOFX/actions/runs/43455514175) executou 150 testes em Linux e Windows.
