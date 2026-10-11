$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimeDir = Join-Path $projectRoot '.runtime'
$logPath = Join-Path $runtimeDir 'build.log'
$utf8 = New-Object Text.UTF8Encoding($false)
$lock = $null
$resultCode = 1
$started = Get-Date

function Show-Notice([string]$message, [int]$icon = 64) {
    $shell = New-Object -ComObject WScript.Shell
    [void]$shell.Popup($message, 0, '重建本地网站', $icon)
}

try {
    [void][IO.Directory]::CreateDirectory($runtimeDir)
    try { $lock = [IO.File]::Open((Join-Path $runtimeDir 'rebuild.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw '网站正在重建，请等待完成提示，不必重复点击。' }
    [IO.File]::WriteAllText($logPath, "开始重建：$($started.ToString('yyyy-MM-dd HH:mm:ss'))`r`n项目：$projectRoot`r`n", $utf8)
    $buildScript = Join-Path $PSScriptRoot 'build.mjs'
    if (-not (Test-Path -LiteralPath $buildScript)) { throw '没有找到 tools/build.mjs，请联系网站维护者检查项目文件。' }
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) { throw '重新构建需要 Node.js 24。请安装后在项目目录执行 npm ci；正常使用网站不需要 Node.js。' }
    $nodePath = $node.Source
    $outLog = Join-Path $runtimeDir 'build-output.log'
    $errLog = Join-Path $runtimeDir 'build-error.log'
    $process = Start-Process -FilePath $nodePath -ArgumentList ('"' + $buildScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -Wait -PassThru
    $resultCode = $process.ExitCode
    $output = if (Test-Path -LiteralPath $outLog) { [IO.File]::ReadAllText($outLog, $utf8) } else { '' }
    $errors = if (Test-Path -LiteralPath $errLog) { [IO.File]::ReadAllText($errLog, $utf8) } else { '' }
    $finished = Get-Date
    $report = "`r`n构建输出：`r`n$output`r`n构建错误与警告：`r`n$errors`r`n结束：$($finished.ToString('yyyy-MM-dd HH:mm:ss'))`r`n退出码：$resultCode`r`n"
    [IO.File]::AppendAllText($logPath, $report, $utf8)
    if ($resultCode -ne 0) { throw "网站重建失败（退出码 $resultCode）。请把下面的日志发给网站维护者：`n$logPath" }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dist\index.html'))) {
        $resultCode = 1
        throw "构建结束，但没有找到 dist/index.html，请把下面的日志发给网站维护者：`n$logPath"
    }
    Show-Notice "网站重建完成。`n`n网站正在打开时，请刷新浏览器；尚未启动时，请双击“启动网站.vbs”。`n`n构建日志：$logPath"
    exit 0
} catch {
    if ($lock -and (Test-Path -LiteralPath $runtimeDir)) {
        [IO.File]::AppendAllText($logPath, "`r`n提示：$($_.Exception.Message)`r`n", $utf8)
    }
    Show-Notice $_.Exception.Message 48
    if (-not $resultCode) { $resultCode = 1 }
    exit $resultCode
} finally {
    if ($lock) { $lock.Dispose() }
}
