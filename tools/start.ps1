param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$lock = $null
try {
    . (Join-Path $PSScriptRoot 'launcher-common.ps1')
    [void][IO.Directory]::CreateDirectory($runtimeDir)
    try { $lock = [IO.File]::Open((Join-Path $runtimeDir 'launcher.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw '网站启动或停止正在进行，请稍后再试。' }
    $status = Get-LocalStatus $port
    if ((Get-OwnedProcess $status) -and $status.serverPath -ieq $serverPath) {
        if ($Quiet) { Write-Output "网站已运行：$url" } else { Start-Process -FilePath $url }
        exit 0
    }
    # Upgrade only this project's verified legacy server, never an unrelated listener.
    $state = if (Get-OwnedProcess $status) { $status } else { Read-State }
    if (Get-OwnedProcess $state) {
        if ($state.serverPath -ieq $legacyServerPath) {
            Stop-Process -Id ([int]$state.pid) -ErrorAction Stop
            for ($attempt = 0; $attempt -lt 20; $attempt++) {
                if (-not (Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue)) { break }
                Start-Sleep -Milliseconds 250
            }
        } else { throw '本项目模型服务仍在运行但网页尚未就绪。请稍后刷新；如需重新启动，请先双击“停止网站.vbs”。' }
    }
    if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath -Force }
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        $occupied = $connect.AsyncWaitHandle.WaitOne(600) -and $client.Connected
    } finally { $client.Dispose() }
    if ($occupied) { throw "端口 $port 被其他程序占用，启动器未结束它。请先关闭占用该端口的程序。" }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dist\index.html'))) { throw '没有找到 dist/index.html。请先双击“重建网站.vbs”。' }
    if (-not (Test-Path -LiteralPath $serverPath)) { throw '没有找到 api/server.py，请检查模型服务文件。' }
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先安装 Python 3.12（64位），然后双击本文件夹中的“安装运行环境.bat”。首次安装需要联网，完成后可离线运行。' }
    $outLog = Join-Path $runtimeDir 'server.log'
    $errLog = Join-Path $runtimeDir 'server-error.log'
    $process = Start-Process -FilePath $pythonPath -ArgumentList ('-X utf8 -u "' + $serverPath + '" --port ' + $port) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        $status = Get-LocalStatus $port
        $owned = Get-OwnedProcess $status
        # Windows venv python.exe can redirect to a child interpreter. Verify
        # ownership and the direct parent instead of mistaking it for a failure.
        if ($owned -and ($owned.ProcessId -eq $process.Id -or $owned.ParentProcessId -eq $process.Id) -and $status.serverPath -ieq $serverPath) { $ready = $true; break }
        $process.Refresh()
        if ($process.HasExited) { break }
    }
    if (-not $ready) {
        $details = if (Test-Path -LiteralPath $errLog) { ([string](Get-Content -LiteralPath $errLog -Raw -Encoding UTF8)).Trim() } else { '' }
        if (-not $details) { $details = '请查看本项目 .runtime 文件夹内的运行记录。' }
        throw "网站尚未成功启动。`n$details"
    }
    # The page is available while the saved CPU model initializes in the background.
    if ($Quiet) { Write-Output "网站已启动：$url；模型状态见 WPN 页面。" } else { Start-Process -FilePath $url }
} catch {
    if ($Quiet) { Write-Output $_.Exception.Message } else {
        $notice = New-Object -ComObject WScript.Shell
        [void]$notice.Popup($_.Exception.Message, 0, 'WPN 本地模型平台', 48)
    }
    exit 1
} finally { if ($lock) { $lock.Dispose() } }
