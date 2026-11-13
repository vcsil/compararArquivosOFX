param([Parameter(Mandatory=$true)][string]$Exe, [int]$Runs=10, [int]$TimeoutSeconds=30)
# Mede até a primeira saída do console; use somente dados temporários e executável confiável.
$values = @()
for ($i=0; $i -lt $Runs; $i++) {
    $pinfo = [System.Diagnostics.ProcessStartInfo]::new()
    $pinfo.FileName = (Resolve-Path $Exe).Path
    $pinfo.WorkingDirectory = (Get-Location).Path
    $pinfo.UseShellExecute = $false
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardInput = $true
    $p = [System.Diagnostics.Process]::new(); $p.StartInfo = $pinfo
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $p.Start()) { throw 'Processo não iniciou' }
        $buf = [char[]]::new(1)
        $read = $p.StandardOutput.ReadAsync($buf,0,1)
        if (-not $read.Wait($TimeoutSeconds * 1000)) { throw 'Tempo esgotado aguardando primeira saída' }
        if ($read.Result -eq 0) { throw 'Processo encerrou sem saída' }
        $timer.Stop(); $values += $timer.Elapsed.TotalMilliseconds
    } finally { if (-not $p.HasExited) { $p.Kill(); $p.WaitForExit() }; $p.Dispose() }
}
$sorted = @($values | Sort-Object)
$mid = [int][Math]::Floor($sorted.Count / 2)
$median = if ($sorted.Count % 2) { $sorted[$mid] } else { ($sorted[$mid-1] + $sorted[$mid])/2 }
"n=$($sorted.Count) mediana_ms=$median min_ms=$($sorted[0]) max_ms=$($sorted[-1])"
