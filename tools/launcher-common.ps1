$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$serverPath = Join-Path $projectRoot 'api\server.py'
$legacyServerPath = Join-Path $PSScriptRoot 'serve.mjs'
$runtimeDir = Join-Path $projectRoot '.runtime'
$statePath = Join-Path $runtimeDir 'server.pid.json'
$config = @{ name = 'WPN 模型平台'; port = 4174; home = '/' }
$configPath = Join-Path $projectRoot '项目配置.json'
if (Test-Path -LiteralPath $configPath) {
    $saved = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($key in @('name', 'port', 'home')) { if ($null -ne $saved.$key) { $config[$key] = $saved.$key } }
}
$port = 0
if (-not [int]::TryParse([string]$config.port, [ref]$port) -or $port -lt 1024 -or $port -gt 65535) { throw '项目配置.json 的 port 必须为 1024–65535 的整数。' }
if ([string]$config.home -notmatch '^/(?!/)[^\r\n\\]*$') { throw '项目配置.json 的 home 必须是以单个 / 开头的本地路径。' }
$url = "http://127.0.0.1:$port$($config.home)"
function Get-LocalStatus([int]$localPort) {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$localPort/__local/status" -TimeoutSec 2 } catch { return $null }
}
function Get-OwnedProcess($state) {
    if (-not $state -or -not $state.pid -or $state.projectRoot -ine $projectRoot) { return $null }
    $expectedName = if ($state.serverPath -ieq $serverPath) { 'python.exe' } elseif ($state.serverPath -ieq $legacyServerPath) { 'node.exe' } else { return $null }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$state.pid)" -ErrorAction SilentlyContinue
    if (-not $proc -or $proc.Name -ine $expectedName) { return $null }
    $pattern = '(?i)(?:^|\s)"?' + [regex]::Escape([string]$state.serverPath) + '"?(?=\s|$)'
    if (-not $proc.CommandLine -or ($proc.CommandLine.Replace('/', '\') -notmatch $pattern)) { return $null }
    if (-not $state.startedAt) { return $null }
    try {
        $recorded = [DateTimeOffset]::Parse([string]$state.startedAt).UtcDateTime
        if ([Math]::Abs(($proc.CreationDate.ToUniversalTime() - $recorded).TotalSeconds) -gt 10) { return $null }
    } catch { return $null }
    return $proc
}
function Read-State {
    if (Test-Path -LiteralPath $statePath) {
        try { return Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
    }
    return $null
}
