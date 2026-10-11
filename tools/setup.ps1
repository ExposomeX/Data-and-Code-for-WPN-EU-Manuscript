param([string]$Python, [switch]$Quiet)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$environmentDir = Join-Path $projectRoot '.venv'
$environmentPython = Join-Path $environmentDir 'Scripts\python.exe'
$runtimeDir = Join-Path $projectRoot '.runtime'
$lock = $null

function Confirm-Python([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        $result = & $Path -I -c 'import struct,sys; print(''WPN_OK'' if sys.version_info[:2] == (3,12) and struct.calcsize(''P'') == 8 else ''WPN_UNSUPPORTED'')' 2>$null
        return $LASTEXITCODE -eq 0 -and $result -contains 'WPN_OK'
    } catch { return $false }
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'WPN requires 64-bit Windows.' }
    [void][IO.Directory]::CreateDirectory($runtimeDir)
    $lock = [IO.File]::Open((Join-Path $runtimeDir 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if (-not $Python) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            try {
                $candidate = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate) { $Python = [string]($candidate | Select-Object -Last 1) }
            } catch {}
        }
        if (-not (Confirm-Python $Python)) {
            $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($candidate -and $candidate.Source -notmatch 'WindowsApps') { $Python = $candidate.Source }
        }
    }
    if (-not (Confirm-Python $Python)) {
        throw 'Install Python 3.12 (64-bit) with the Python launcher, then run this setup again. https://www.python.org/downloads/release/python-31210/ . Advanced: tools/setup.ps1 -Python "C:\path\to\python.exe"'
    }
    Write-Host 'WPN first-time setup: Python 3.12, CPU inference. Internet access is needed for installation.'
    if (Test-Path -LiteralPath $environmentDir) {
        if (-not (Confirm-Python $environmentPython)) { throw 'The existing .venv is not usable here. Delete only the .venv folder in this WPN directory, then run setup again. Virtual environments must not be copied between computers.' }
    } else {
        & $Python -m venv $environmentDir
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    }
    & $environmentPython -m pip install --disable-pip-version-check 'torch==2.11.0+cpu' --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed. Check your internet connection and run setup again.' }
    & $environmentPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'local_code\requirements-tested.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the message above and run setup again.' }
    & $environmentPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Installed dependencies are inconsistent.' }
    & $environmentPython -I -c 'import torch,tabpfn,numpy,pandas,sklearn,openpyxl; assert torch.version.cuda is None; print(''CPU dependencies ready.'')'
    if ($LASTEXITCODE -ne 0) { throw 'The CPU environment could not be loaded. For missing DLL / WinError 126 or 1114, install Microsoft Visual C++ v14 Redistributable (x64), then retry: https://aka.ms/vc14/vc_redist.x64.exe' }
    $state = @{ projectRoot = $projectRoot; python = $environmentPython; device = 'cpu'; installedAt = [DateTimeOffset]::UtcNow.ToString('o') }
    [IO.File]::WriteAllText((Join-Path $runtimeDir 'environment.json'), ($state | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Setup complete. Double-click the website start shortcut. Future calculations work offline; Node.js and an NVIDIA GPU are not required.'
    exit 0
} catch {
    Write-Host ('WPN setup failed: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'If the error mentions a missing DLL (WinError 126/1114), see README for the Microsoft Visual C++ x64 runtime installer.'
    exit 1
} finally { if ($lock) { $lock.Dispose() } }
