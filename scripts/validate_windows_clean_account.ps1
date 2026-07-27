[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Archive,

    [Parameter(Mandatory = $true)]
    [string]$Report,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmSeparateAccount,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmInteractiveLaunch
)

$ErrorActionPreference = "Stop"

function Get-InstalledCommandPaths {
    param([string]$Name)

    $commands = @(Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)
    return @(
        $commands |
            ForEach-Object { $_.Source } |
            Where-Object {
                $_ -and
                $_ -notmatch '\\Microsoft\\WindowsApps\\python(?:3)?\.exe$'
            } |
            Sort-Object -Unique
    )
}

$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$reportPath = [System.IO.Path]::GetFullPath($Report)
$pythonPaths = @(Get-InstalledCommandPaths -Name "python.exe")
$uvPaths = @(Get-InstalledCommandPaths -Name "uv.exe")
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "mangacrisp-clean-account-" + [guid]::NewGuid().ToString("N")
)

$smokeReturnCode = $null
$engineHash = $null
$executableHash = $null
$archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()

try {
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    Expand-Archive -LiteralPath $archivePath -DestinationPath $temporaryRoot

    $appDirectory = Join-Path $temporaryRoot "MangaCrisp"
    $executable = Join-Path $appDirectory "MangaCrisp.exe"
    $engine = Join-Path $appDirectory (
        "_internal\engines\realcugan-ncnn-vulkan\realcugan-ncnn-vulkan.exe"
    )
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "The portable ZIP does not contain MangaCrisp.exe."
    }
    if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) {
        throw "The portable ZIP does not contain the Real-CUGAN engine."
    }

    $executableHash = (
        Get-FileHash -LiteralPath $executable -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $engineHash = (
        Get-FileHash -LiteralPath $engine -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    $savedEnvironment = @{
        APPDATA = $env:APPDATA
        LOCALAPPDATA = $env:LOCALAPPDATA
        MANGACRISP_LANGUAGE = $env:MANGACRISP_LANGUAGE
        PATH = $env:PATH
        PYTHONHOME = $env:PYTHONHOME
        PYTHONPATH = $env:PYTHONPATH
        QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM
        USERPROFILE = $env:USERPROFILE
    }
    $profilePath = Join-Path $temporaryRoot "profile"
    try {
        $env:APPDATA = Join-Path $profilePath "AppData\Roaming"
        $env:LOCALAPPDATA = Join-Path $profilePath "AppData\Local"
        $env:MANGACRISP_LANGUAGE = "en"
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:USERPROFILE = $profilePath
        $process = Start-Process `
            -FilePath $executable `
            -ArgumentList "--smoke-test" `
            -WorkingDirectory $appDirectory `
            -PassThru `
            -Wait
        $smokeReturnCode = $process.ExitCode
    }
    finally {
        foreach ($item in $savedEnvironment.GetEnumerator()) {
            if ($null -eq $item.Value) {
                Remove-Item -Path ("Env:" + $item.Key) -ErrorAction SilentlyContinue
            }
            else {
                Set-Item -Path ("Env:" + $item.Key) -Value $item.Value
            }
        }
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

$operatingSystem = Get-CimInstance Win32_OperatingSystem
$passed = (
    $ConfirmSeparateAccount.IsPresent -and
    $ConfirmInteractiveLaunch.IsPresent -and
    $pythonPaths.Count -eq 0 -and
    $uvPaths.Count -eq 0 -and
    $smokeReturnCode -eq 0 -and
    $null -ne $engineHash -and
    $null -ne $executableHash
)
$payload = [ordered]@{
    schema_version = 1
    report_kind = "clean_windows_account"
    validated_on = (Get-Date).ToString("yyyy-MM-dd")
    passed = $passed
    operator_confirmed_separate_account = $ConfirmSeparateAccount.IsPresent
    interactive_launch_confirmed = $ConfirmInteractiveLaunch.IsPresent
    developer_tools = [ordered]@{
        python_installed = $pythonPaths.Count -gt 0
        uv_installed = $uvPaths.Count -gt 0
        windows_store_python_alias_ignored = $true
    }
    windows = [ordered]@{
        caption = $operatingSystem.Caption
        version = $operatingSystem.Version
        build = $operatingSystem.BuildNumber
    }
    archive = [ordered]@{
        filename = [System.IO.Path]::GetFileName($archivePath)
        sha256 = $archiveHash
        executable_sha256 = $executableHash
        engine_sha256 = $engineHash
    }
    smoke_test = [ordered]@{
        returncode = $smokeReturnCode
        sanitized_path = $true
    }
}

$reportDirectory = [System.IO.Path]::GetDirectoryName($reportPath)
if ($reportDirectory) {
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
}
$json = ($payload | ConvertTo-Json -Depth 8) + [Environment]::NewLine
[IO.File]::WriteAllText($reportPath, $json, [Text.UTF8Encoding]::new($false))
Write-Output "report: $reportPath"
Write-Output "passed: $passed"

if (-not $passed) {
    throw "Clean Windows account validation did not pass. See the JSON report."
}
