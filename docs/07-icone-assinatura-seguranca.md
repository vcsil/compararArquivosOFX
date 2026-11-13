# Ícone legado, assinatura Authenticode e alerta do Microsoft Defender

## Estado de segurança

Em 13/11/2026, o Microsoft Defender sinalizou uma execução do candidato Nuitka onefile como `Program:Win32/Contebrew.A!ml`, com gravidade alta. A causa **não foi determinada**. Revisão de código e testes de integridade não comprovam que o executável empacotado esteja livre de malware; é necessário conferir a cadeia de produção, dependências, binários finais e análise da Microsoft.

**Não permitir o arquivo sinalizado nem desativar o antivírus.** Mantenha-o em quarentena e faça verificação completa. Submeta a versão exata do binário para reanálise oficial em https://www.microsoft.com/en-us/wdsi/filesubmission/ e guarde o identificador da submissão e o parecer. Não compartilhe OFX reais com serviços de análise ou scanners públicos.

## Ícone da versão antiga

O repositório conserva `dist/Compara OFX.exe`. Sem alterar esse arquivo, `scripts/build_windows.ps1` configura:

- PyInstaller: `--icon=<caminho do EXE legado>,0` para extrair o primeiro ícone.
- Nuitka standalone/onefile: `--windows-icon-from-exe=<caminho do EXE legado>`.

O build deve validar em Windows que o recurso de ícone foi realmente reproduzido. Se o legado não tiver o recurso de ícone esperado, falhar ou corrigir explicitamente, sem inventar arte visual. **O ícone é apenas identidade visual: não cria confiança nem altera a segurança do binário.**

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

O executável legado contém um único recurso PNG RGBA de 256 × 256. `scripts/recolor_icon.py` lê o recurso PE com `pefile`, preserva geometria, alfa e pixels neutros, e substitui matizes verdes por azul de matiz 221° (referência #2563EB), mantendo variações de brilho e saturação. Requer `pefile` e `Pillow`; execute `venv/bin/python scripts/recolor_icon.py` na raiz. Foram gerados PNG, comparação visual e ICO com 16, 24, 32, 48, 64, 128 e 256 pixels; os tamanhos menores são reamostrados do único original.

Ambos empacotadores usam `assets/comparaofx-2.0-azul.ico`. `scripts/verify_icon.py` lê os recursos PE e compara imagens e alfa com cada resolução do ICO, antes do smoke financeiro e da assinatura opcional. O build instala `pefile==2024.8.26` e `Pillow==11.3.0` para essa inspeção. A compilação normal permanece sem certificado e os candidatos são não assinados.

A detecção anterior `Program:Win32/Contebrew.A!ml` não foi esclarecida. Não há Microsoft Defender neste ambiente Linux; a alteração visual não constitui correção de segurança. Resultados Windows, inspeção PE, hashes e benchmarks dependem da execução do workflow e devem ser confirmados antes de recomendar qualquer candidato. Caso haja detecção, interrompa a aprovação e submeta o binário à Microsoft para análise oficial, sem dados reais.
