param(
    [ValidateSet('pyinstaller','nuitka')][string]$Tool='pyinstaller',
    [string]$OutputDir = (Join-Path $env:TEMP 'comparaofx-build-output'),
    [ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$SignThumbprint = ''
)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'O build de executáveis Windows requer Windows nativo.' }
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$legacy = [IO.Path]::GetFullPath((Join-Path $Repo 'dist'))
$Icon = Join-Path $Repo 'assets/comparaofx-2.0-azul.ico'
if (-not (Test-Path -LiteralPath $Icon -PathType Leaf)) { throw 'Ícone azul ausente.' }
if ($OutputDir.Equals($legacy,[StringComparison]::OrdinalIgnoreCase) -or $OutputDir.StartsWith($legacy+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'O destino não pode ser dist/ legado.' }
# Keep the spec and entry point on the same volume, even when TEMP is on C: and the repo on D:.
$Scratch = Join-Path $Repo ('comparaofx-build-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Scratch,$OutputDir -Force | Out-Null
function Invoke-Checked { param([string]$Exe,[string[]]$Arguments) & $Exe @Arguments; if ($LASTEXITCODE -ne 0) { throw "Comando falhou: $Exe (código $LASTEXITCODE)" } }
function Sign-IfRequested { param([string]$Executable)
    if ($SignThumbprint) {
        & (Join-Path $PSScriptRoot 'sign_windows.ps1') -Exe $Executable -CertThumbprint $SignThumbprint
        if (-not $?) { throw 'Assinatura Authenticode falhou.' }
    } else { Write-Output 'UNSIGNED CANDIDATE: certificado Code Signing nao configurado.' }
}
try {
    Set-Location $Repo
    Invoke-Checked 'python' @('-m','venv',(Join-Path $Scratch 'venv'))
    $Py=Join-Path $Scratch 'venv/Scripts/python.exe'
    Invoke-Checked $Py @('-m','pip','install','-r','requirements.txt')
    Invoke-Checked $Py @('-m','pip','install','pefile==2024.8.26','Pillow==11.3.0')
    Invoke-Checked $Py @('-m','unittest','discover','-s','tests','-v')
    if ($Tool -eq 'pyinstaller') {
        Invoke-Checked $Py @('-m','pip','install','pyinstaller==6.11.1')
        Invoke-Checked $Py @('-m','PyInstaller','--noconfirm','--clean','--onefile','--console','--name','ComparaOFX','--distpath',$OutputDir,'--workpath',(Join-Path $Scratch 'work'),'--specpath',$Scratch,('--icon=' + $Icon),'src/comparaArqOFX.py')
        $Exe=Join-Path $OutputDir 'ComparaOFX.exe'
        if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'Executável PyInstaller ausente.' }
        Invoke-Checked $Py @('scripts/verify_icon.py',$Exe,$Icon)
        Invoke-Checked $Py @('scripts/smoke_exe.py',$Exe)
        Sign-IfRequested $Exe
        Get-FileHash -Algorithm SHA256 -LiteralPath $Exe | Format-List
        Get-Item -LiteralPath $Exe | Select-Object FullName,Length | Format-List
    } else {
        Invoke-Checked $Py @('-m','pip','install','Nuitka==2.5.9','ordered-set==4.1.0','zstandard==0.23.0')
        $Standalone=Join-Path $OutputDir 'standalone'; $Onefile=Join-Path $OutputDir 'onefile'
        New-Item -ItemType Directory -Path $Standalone,$Onefile -Force | Out-Null
        Invoke-Checked $Py @('-m','nuitka','--standalone','--assume-yes-for-downloads',"--output-dir=$Standalone",("--windows-icon-from-ico=" + $Icon),'src/comparaArqOFX.py')
        $StandaloneExe=Join-Path $Standalone 'comparaArqOFX.dist/comparaArqOFX.exe'
        if (-not (Test-Path -LiteralPath $StandaloneExe -PathType Leaf)) { throw 'Executável standalone ausente.' }
        Invoke-Checked $Py @('scripts/verify_icon.py',$StandaloneExe,$Icon)
        Invoke-Checked $Py @('scripts/smoke_exe.py',$StandaloneExe)
        Sign-IfRequested $StandaloneExe
        Invoke-Checked $Py @('-m','nuitka','--onefile','--assume-yes-for-downloads',"--output-dir=$Onefile",'--output-filename=ComparaOFX.exe',('--windows-icon-from-ico=' + $Icon),'src/comparaArqOFX.py')
        $Exe=Join-Path $Onefile 'ComparaOFX.exe'
        if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'Executável Nuitka ausente.' }
        Invoke-Checked $Py @('scripts/verify_icon.py',$Exe,$Icon)
        Invoke-Checked $Py @('scripts/smoke_exe.py',$Exe)
        Sign-IfRequested $Exe
        Get-FileHash -Algorithm SHA256 -LiteralPath $Exe | Format-List
        Get-Item -LiteralPath $Exe | Select-Object FullName,Length | Format-List
    }
} finally {
    Set-Location $Repo
    Remove-Item -LiteralPath $Scratch -Recurse -Force -ErrorAction SilentlyContinue
}
