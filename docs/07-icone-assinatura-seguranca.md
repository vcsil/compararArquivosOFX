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

Ambos empacotadores usam `assets/comparaofx-2.0-azul.ico`. `scripts/verify_icon.py` lê o primeiro grupo de ícones do PE e compara imagens e alfa com cada resolução do ICO, antes do smoke financeiro e da assinatura opcional. O build instala `pefile==2024.8.26` e `Pillow==11.3.0` para essa inspeção. A compilação normal permanece sem certificado e os candidatos são não assinados.

A detecção anterior `Program:Win32/Contebrew.A!ml` não foi esclarecida. Não há Microsoft Defender neste ambiente Linux; a alteração visual não constitui correção de segurança. Resultados Windows, inspeção PE, hashes e benchmarks dependem da execução do workflow e devem ser confirmados antes de recomendar qualquer candidato. Caso haja detecção, interrompa a aprovação e submeta o binário à Microsoft para análise oficial, sem dados reais.

O build consulta o estado do Defender no Windows e, quando ativo, tenta atualizar as assinaturas e executar verificação individual antes do smoke. A versão e data das definições são registradas; uma detecção associada ao arquivo bloqueia o build. Se o serviço não estiver disponível, isso é registrado como não verificado. Não são criadas exclusões nem alterada a política do antivírus.

A revisão estática da aplicação não identificou comandos externos, persistência ou comunicação de rede. Os subprocessos encontrados executam candidatos sintéticos nos scripts de teste; a compilação instala dependências do PyPI e Nuitka pode baixar ferramentas adicionais. `colorama` e `ofxtools` estão fixados; dependências transitivas e imagens de CI não são fixadas por hash. Essa revisão não verifica a integridade de todos os artefatos de terceiros nem prova a segurança dos executáveis.

Sem certificado, o build exige que `Get-AuthenticodeSignature` retorne `NotSigned`; com certificado configurado, o script opcional valida a assinatura.

As actions do GitHub usadas no workflow são referenciadas por tags de versão, não por commits imutáveis. Os pacotes diretos do build têm versões selecionadas; downloads transitivos e ferramentas externas do Nuitka não têm hashes fixados neste repositório. A receita e os hashes finais permitem identificar os resultados, mas não garantem reconstrução binária idêntica nem estabelecem a integridade independente de toda a cadeia.

## Preparação para análise oficial da detecção anterior

A amostra anteriormente sinalizada continua sem diagnóstico. O hash do arquivo efetivamente detectado e a versão das assinaturas usadas naquela detecção não foram fornecidos; não se deve presumir que coincidam com os binários reconstruídos nesta execução. Preserve a amostra em quarentena e obtenha os dados diretamente do histórico de proteção. Não use extratos ou históricos reais como amostras.

Para revisão antes do envio em https://www.microsoft.com/en-us/wdsi/filesubmission/, preencha com o hash da amostra exata, nome `Program:Win32/Contebrew.A!ml`, data/hora e fuso da ocorrência, versão das assinaturas Defender, versão do Windows e contexto de que o alerta ocorreu antes do menu. Texto sugerido: “Solicito análise deste executável; o Microsoft Defender o identificou como Program:Win32/Contebrew.A!ml antes da abertura do menu. A causa ainda não foi determinada. SHA-256: [hash da amostra exata]. Versão das assinaturas: [versão observada].” Anexe somente a amostra solicitada pela Microsoft e registre o identificador e o parecer. Nenhuma submissão foi feita nesta sessão.
