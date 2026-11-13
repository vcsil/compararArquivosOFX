param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$CertThumbprint,
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Assinatura Authenticode requer Windows.' }
$target = (Resolve-Path -LiteralPath $Exe -ErrorAction Stop).Path
$signTool = Get-Command 'signtool.exe' -ErrorAction SilentlyContinue
if (-not $signTool) { throw 'signtool.exe não encontrado. Instale Windows SDK ou configure PATH.' }
$cert = @(Get-ChildItem Cert:\CurrentUser\My,Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
    Where-Object { $_.Thumbprint -eq $CertThumbprint -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) })
if ($cert.Count -ne 1) {
    throw 'Certificado único, válido e com chave privada não encontrado nos repositórios pessoais do Windows.'
}
if (-not ($cert[0].EnhancedKeyUsageList | Where-Object { $_.ObjectId -eq '1.3.6.1.5.5.7.3.3' })) {
    throw 'Certificado não possui finalidade Code Signing (EKU).'
}
$args = @('sign','/sha1',$CertThumbprint,'/fd','SHA256','/tr',$TimestampUrl,'/td','SHA256','/v')
if ($cert[0].PSParentPath -like '*LocalMachine*') { $args += '/sm' }
$args += $target
& $signTool.Source @args
if ($LASTEXITCODE -ne 0) { throw "SignTool falhou ao assinar o executável (código $LASTEXITCODE)." }
& $signTool.Source verify /pa /v $target
if ($LASTEXITCODE -ne 0) { throw 'Verificação Authenticode de política padrão falhou.' }
$signature = Get-AuthenticodeSignature -LiteralPath $target
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $CertThumbprint) {
    throw "Assinatura não válida ou editor divergente: $($signature.Status)"
}
$file = Get-Item -LiteralPath $target
$sha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
Write-Output ("SIGNATURE=VALID FILE={0} PUBLISHER={1} SHA256={2} BYTES={3}" -f $target,$signature.SignerCertificate.Subject,$sha256,$file.Length)
