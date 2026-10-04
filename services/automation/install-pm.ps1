# Installs a current-user hidden PM loop only after a real metadata preflight.
# Never copies credentials, logs in, changes execution policy, or enables automation.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$PMEntryPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$PMEntrySha256,
    [switch]$Replace,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
$taskName = 'LGAX-PM-jeongiryang'

function Get-ExternalPath([string]$Path, [bool]$MustExist = $true, [bool]$Directory = $false) {
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path -notmatch '^[A-Za-z]:[\\/]' -or
        $Path -match '["\x00-\x1f]') { throw 'An absolute literal filesystem path is required.' }
    $full = [IO.Path]::GetFullPath($Path)
    if ($MustExist -and -not (Test-Path -LiteralPath $full)) { throw 'Required external deployment path is missing.' }
    if (Test-Path -LiteralPath $full) {
        $item = Get-Item -LiteralPath $full -Force
        if ([bool]$item.PSIsContainer -ne $Directory) { throw 'Deployment path has the wrong file/directory type.' }
    }
    $cursor = if ($Directory) { $full } else { [IO.Path]::GetDirectoryName($full) }
    if (Test-Path -LiteralPath $full) {
        if ((Get-Item -LiteralPath $full -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Linked deployment paths are forbidden.'
        }
    }
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (-not $item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Deployment path ancestors must be plain directories.'
            }
        }
        if (Test-Path -LiteralPath (Join-Path $cursor '.git')) {
            throw 'PM deployment files must be outside every source-controlled checkout.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor.TrimEnd('\', '/'))
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}

function Get-Digest([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Digest([string]$Path, [string]$Expected) {
    if ($Expected -notmatch '^[0-9a-fA-F]{64}$' -or (Get-Digest $Path) -ne $Expected.ToLowerInvariant()) {
        throw 'A pinned deployment file changed; review and redeploy instead of installing it.'
    }
}

function Test-Under([string]$Path, [string]$Parent) {
    $plain = $Parent.TrimEnd('\', '/')
    return ($Path.Equals($plain, [StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($plain + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase))
}

function ConvertTo-Literal([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }

$resolvedConfig = Get-ExternalPath $ConfigPath
$resolvedPython = Get-ExternalPath $PythonPath
$resolvedEntry = Get-ExternalPath $PMEntryPath
Assert-Digest $resolvedEntry $PMEntrySha256
if ([IO.Path]::GetFileName($resolvedEntry) -ne 'pm_entry.py') { throw 'Use the external hash-checked pm_entry.py runtime.' }
$settings = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8 | ConvertFrom-Json
$policy = Get-ExternalPath ([string]$settings.policy_file)
Assert-Digest $policy ([string]$settings.policy_sha256)
$policySettings = Get-Content -LiteralPath $policy -Raw -Encoding UTF8 | ConvertFrom-Json
if ($policySettings.pm_account -ne 'jeongiryang' -or
    $policySettings.repo -ne '2026-LG-kitchen-chicken-team/lg-ax-2026') {
    throw 'Only the approved LG repository and jeongiryang PM are supported.'
}
$state = Get-ExternalPath ([string]$settings.state_dir) $false $true
$journal = Get-ExternalPath ([string]$settings.journal_file) $false
$controllerToken = Get-ExternalPath ([string]$settings.controller_token_file)
$execution = Get-ExternalPath ([string]$settings.executor.workspace_root) $true $true
$profile = Get-ExternalPath ([string]$settings.executor.auth_root) $true $true
if ($settings.executor.image -notmatch '^sha256:[0-9a-f]{64}$') { throw 'An immutable Docker executor image ID is required.' }
$pinned = @(
    @{ Path = $resolvedEntry; Hash = $PMEntrySha256.ToLowerInvariant() },
    @{ Path = $resolvedConfig; Hash = (Get-Digest $resolvedConfig) },
    @{ Path = $resolvedPython; Hash = (Get-Digest $resolvedPython) },
    @{ Path = $policy; Hash = ([string]$settings.policy_sha256).ToLowerInvariant() }
)
if (-not $settings.readiness_files -or -not $settings.readiness_files.jeongiryang) {
    throw 'Pinned private PM Worker readiness evidence is required; metadata is not a substitute.'
}
foreach ($member in $settings.readiness_files.PSObject.Properties) {
    if ($member.Name -notin @('jeongiryang', 'unknownamed', 'ginaginaring', 'choigilung')) {
        throw 'Unknown readiness owner.'
    }
    $proof = Get-ExternalPath ([string]$member.Value.path)
    Assert-Digest $proof ([string]$member.Value.sha256)
    $pinned += @{ Path = $proof; Hash = ([string]$member.Value.sha256).ToLowerInvariant() }
}
foreach ($path in @($resolvedConfig, $resolvedEntry, $policy, $journal, $state, $controllerToken) + @($pinned | ForEach-Object { $_.Path })) {
    if ((Test-Under $path $execution) -or (Test-Under $path $profile)) {
        throw 'PM runtime, policy, journal and evidence cannot be inside guest work or the AI profile.'
    }
}
if ((Test-Under $state $execution) -or (Test-Under $execution $state) -or
    (Test-Under $profile $execution) -or (Test-Under $execution $profile) -or
    (Test-Under $state $profile) -or (Test-Under $profile $state)) {
    throw 'PM state, guest execution and AI authentication directories must be disjoint.'
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    if (-not $Replace) { throw 'The PM task already exists. Stop it, review changes, and use -Replace explicitly.' }
    if ((Get-ScheduledTask -TaskName $taskName).State -eq 'Running') {
        throw 'Stop the existing PM task before replacing its fixed deployment.'
    }
}

# This reads real GitHub/controller identity and exact Docker metadata. It never
# invokes a model, collects PR tests, publishes, enables modes, or logs in.
$preflightText = (& $resolvedPython -X utf8 $resolvedEntry --config $resolvedConfig --preflight 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw 'PM metadata preflight refused installation; inspect the private deployment.' }
try { $checked = $preflightText | ConvertFrom-Json } catch { throw 'PM preflight returned invalid metadata.' }
if ($checked.identity.operator -isnot [bool] -or $checked.model_called -isnot [bool] -or
    $checked.mutated -isnot [bool] -or $checked.boundary.linux_engine -isnot [bool] -or
    $checked.boundary.native_fallback -isnot [bool] -or
    $checked.preflight -ne 'passed' -or $checked.identity.account -ne 'jeongiryang' -or
    $checked.identity.operator -ne $true -or $checked.model_called -ne $false -or $checked.mutated -ne $false -or
    $checked.boundary.backend -ne 'docker' -or $checked.boundary.linux_engine -ne $true -or
    $checked.boundary.native_fallback -ne $false -or $checked.boundary.image_id -ne $settings.executor.image) {
    throw 'Actual PM identity, operator or fixed Docker preflight was not verified.'
}
foreach ($item in $pinned) { Assert-Digest $item.Path $item.Hash }

# Encode a fixed script, not a shell-built command line containing user text.
# Every launch rechecks deployment file hashes before starting the fixed runtime.
$checks = ($pinned | ForEach-Object {
    'Assert-Pinned ' + (ConvertTo-Literal $_.Path) + ' ' + (ConvertTo-Literal $_.Hash)
}) -join "`n"
$pythonArguments = '-X utf8 -u "' + $resolvedEntry + '" --config "' + $resolvedConfig + '"'
$launch = @'
$ErrorActionPreference = 'Stop'
function Assert-Pinned([string]$Path, [string]$Hash) {
    $cursor = $Path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Pinned PM deployment path became a link.'
            }
        }
        if (Test-Path -LiteralPath (Join-Path $cursor '.git')) {
            throw 'Pinned PM deployment moved inside a checkout.'
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor.TrimEnd('\', '/'))
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Hash) {
        throw 'Pinned PM deployment changed; reinstall the reviewed deployment.'
    }
}
'@
$launch += "`n" + $checks + "`n"
$launch += '$logRoot = ' + (ConvertTo-Literal (Join-Path $state 'background-logs')) + "`n"
$launch += '[IO.Directory]::CreateDirectory($logRoot) | Out-Null' + "`n"
$launch += '$run = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfff") + "-" + [Guid]::NewGuid().ToString("N")' + "`n"
$launch += '$process = Start-Process -FilePath ' + (ConvertTo-Literal $resolvedPython) +
    ' -ArgumentList ' + (ConvertTo-Literal $pythonArguments) + ' -WorkingDirectory ' + (ConvertTo-Literal $state) +
    ' -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $logRoot ($run + ".out.log"))' +
    ' -RedirectStandardError (Join-Path $logRoot ($run + ".err.log"))' + "`n"
$launch += 'exit $process.ExitCode' + "`n"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($launch))
if ($encoded.Length -gt 30000) { throw 'Pinned launcher is too large for a bounded Windows task command line.' }
$powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand ' + $encoded)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$options = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $options -Description 'LG AX fixed PM loop; no implicit activation; current user must be logged in.' -Force | Out-Null
if ($Start) { Start-ScheduledTask -TaskName $taskName }
Write-Output ('Installed ' + $taskName + '. Modes and authentication were not changed. PC offline/sleep/logoff stops availability; PM loop OS lock prevents duplicates. Fixed deployment changes require reviewed replacement.')
