param([Parameter(Mandatory=$true)][string]$Exe, [int]$Runs=15, [int]$TimeoutSeconds=30)
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $Exe).Path
$root=Join-Path $env:TEMP ('compara-benchmark-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $candidate=Join-Path $root ([IO.Path]::GetFileName($resolved))
    Copy-Item -LiteralPath $resolved -Destination $candidate
    New-Item -ItemType Directory -Path (Join-Path $root 'Banco Sintetico') | Out-Null
    Set-Content -LiteralPath (Join-Path $root 'entrada.ofx') -Value 'sintetico: somente menu' -Encoding Ascii
    $samples=@(); $exits=@()
    for($i=0;$i -le $Runs;$i++) {
        $info=[Diagnostics.ProcessStartInfo]::new(); $info.FileName=$candidate; $info.WorkingDirectory=$env:TEMP
        $info.UseShellExecute=$false; $info.RedirectStandardOutput=$true; $info.RedirectStandardInput=$true; $info.RedirectStandardError=$true
        $proc=[Diagnostics.Process]::new(); $proc.StartInfo=$info; $clock=[Diagnostics.Stopwatch]::StartNew()
        try {
            if(-not $proc.Start()) { throw 'Processo não iniciado' }
            $line=''; $ready=$false
            while(-not $ready) {
                $read=$proc.StandardOutput.ReadLineAsync()
                if(-not $read.Wait($TimeoutSeconds*1000)) { throw 'Tempo esgotado antes do menu' }
                $line=$read.Result
                if($null -eq $line) { throw 'Processo encerrou antes do menu' }
                if($line.Trim() -eq '00 - Cancelar') { $ready=$true }
            }
            $clock.Stop(); $samples+=$clock.Elapsed.TotalMilliseconds
            $exitClock=[Diagnostics.Stopwatch]::StartNew()
            $proc.StandardInput.WriteLine('0'); $proc.StandardInput.Flush()
            if(-not $proc.WaitForExit($TimeoutSeconds*1000)) { throw 'Processo não encerrou' }
            if($proc.ExitCode -ne 0) { throw "Candidato terminou com código $($proc.ExitCode)" }
            $exitClock.Stop(); $exits += $exitClock.Elapsed.TotalMilliseconds
        } finally {
            if(-not $proc.HasExited) { $proc.Kill(); $proc.WaitForExit() }; $proc.Dispose()
        }
    }
    $first=$samples[0]; $sorted=@($samples[1..$Runs] | Sort-Object); $mid=[int][Math]::Floor($sorted.Count/2)
    $median=if($sorted.Count%2){$sorted[$mid]}else{($sorted[$mid-1]+$sorted[$mid])/2}
    $p95=$sorted[[int][Math]::Ceiling($sorted.Count*0.95)-1]
    "primeira_ms=$first n_aquecidas=$($sorted.Count) mediana_ms=$median min_ms=$($sorted[0]) max_ms=$($sorted[-1]) p95_ms=$p95"
    $exitSorted=@($exits[1..$Runs] | Sort-Object)
    "encerramento_apos_cancelar_mediana_ms=$($exitSorted[$mid])"
} finally { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
