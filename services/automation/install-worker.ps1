# Installs an opt-in current-user worker task; never changes PowerShell policy.
# Run in a dedicated execution account/VM. It does not enroll, log in, enable
# automation, install a GitHub runner, or copy an existing Codex authentication.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$WorkerPath,
    [Parameter(Mandatory = $true)][switch]$DedicatedExecutionEnvironment,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
if (-not $DedicatedExecutionEnvironment) {
    throw 'A dedicated execution account or VM is required.'
}
$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
$resolvedWorker = (Resolve-Path -LiteralPath $WorkerPath).Path
$settings = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8 | ConvertFrom-Json
if ($settings.account -notin @('jeongiryang', 'unknownamed', 'ginaginaring', 'choigilung')) {
    throw 'Unregistered worker account.'
}
if (-not $settings.isolation_acknowledged) { throw 'Execution isolation must be acknowledged in config.' }
if ($resolvedPython.Contains('"') -or $resolvedWorker.Contains('"') -or $resolvedConfig.Contains('"')) {
    throw 'Unsupported quote in literal path.'
}
$taskName = 'LGAX-Worker-' + $settings.account
$arguments = '"' + $resolvedWorker + '" --config "' + $resolvedConfig + '"'
$action = New-ScheduledTaskAction -Execute $resolvedPython -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$options = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $options -Description 'LG AX dedicated worker; controller remains OFF until PM enables it.' -Force | Out-Null
if ($Start) { Start-ScheduledTask -TaskName $taskName }
Write-Output ('Installed ' + $taskName + '. Runs only while this execution user is logged in; PC sleep/offline prevents work. Automation mode was not changed.')
