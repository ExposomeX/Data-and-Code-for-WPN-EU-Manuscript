param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$lock = $null
function Show-Notice([string]$message, [int]$icon = 64) {
    if ($Quiet) { Write-Output $message } else { $notice = New-Object -ComObject WScript.Shell; [void]$notice.Popup($message, 0, 'WPN 本地模型平台', $icon) }
}
try {
    . (Join-Path $PSScriptRoot 'launcher-common.ps1')
    [void][IO.Directory]::CreateDirectory($runtimeDir)
    try { $lock = [IO.File]::Open((Join-Path $runtimeDir 'launcher.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw '网站启动或停止正在进行，请稍后再试。' }
    $state = Read-State
    if (-not (Get-OwnedProcess $state)) { $state = Get-LocalStatus $port }
    $owned = Get-OwnedProcess $state
    if ($owned) {
        Stop-Process -Id $owned.ProcessId -ErrorAction Stop
        Show-Notice 'WPN 网站和模型服务已停止。输入和最近成功结果仍保存在当前浏览器中。'
    } else { Show-Notice '本项目网站未运行，或原运行记录已失效。没有结束其他程序。' }
    if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath -Force }
} catch { Show-Notice $_.Exception.Message 48; exit 1 }
finally { if ($lock) { $lock.Dispose() } }
