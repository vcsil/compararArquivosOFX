param([Parameter(Mandatory=$true)][string]$Exe)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $Exe).Path
$parent = Split-Path -Parent $target
$scanTarget = if ((Split-Path -Leaf $parent).EndsWith('.dist')) { $parent } else { $target }
if (-not (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue)) {
    Write-Output '::notice title=Microsoft Defender::Indisponivel: modulo Defender nao encontrado; verificacao nao realizada.'
    return
}
try { $status = Get-MpComputerStatus -ErrorAction Stop } catch {
    Write-Output '::notice title=Microsoft Defender::Estado indisponivel no runner; verificacao nao realizada.'
    return
}
if (-not $status.AntivirusEnabled -or -not $status.AMServiceEnabled) {
    Write-Output '::notice title=Microsoft Defender::Antivirus ou servico indisponivel no runner; verificacao nao realizada.'
    return
}
try { Update-MpSignature -ErrorAction Stop | Out-Null } catch {
    Write-Output '::warning title=Microsoft Defender::Nao foi possivel atualizar assinaturas; confira a data registrada.'
}
$status = Get-MpComputerStatus -ErrorAction Stop
Write-Output ("Defender signature version={0}; updated={1:o}; file={2}" -f $status.AntivirusSignatureVersion,$status.AntivirusSignatureLastUpdated,$scanTarget)
Start-MpScan -ScanType CustomScan -ScanPath $scanTarget -ErrorAction Stop
$detections = @(Get-MpThreatDetection -ErrorAction Stop | Where-Object {
    @($_.Resources | Where-Object { $_ -and $_.IndexOf($scanTarget,[StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count -gt 0
})
if ($detections.Count) {
    $detections | Format-List * | Out-String | Write-Output
    throw 'Defender registrou deteccao no candidato; suspender aprovacao e analisar o resultado.'
}
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'Candidato ausente apos verificacao Defender.' }
Write-Output ("::notice title=Microsoft Defender::Verificacao concluida sem deteccao associada; versao={0}; atualizacao={1:o}" -f $status.AntivirusSignatureVersion,$status.AntivirusSignatureLastUpdated)
