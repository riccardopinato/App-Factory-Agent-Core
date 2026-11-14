# GBrain WSL KeepAlive — Windows logon task (opt-in)
# This script does NOT configure GBrain, Tailscale, OAuth or the AppFactoryAgent worker.
# Requires Windows, PowerShell, WSL Ubuntu and Task Scheduler.
# Review before running. This script has NOT been tested on the operator's Windows device.
# Usage: pwsh -NoProfile -File .\windows_gbrain_keepalive.ps1 -Mode Status|Install|Remove

[CmdletBinding()]
param(
    [ValidateSet('Status', 'Install', 'Remove')]
    [string]$Mode = 'Status'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskName = 'AppFactory-GBrain-WSL-KeepAlive'
$wslPath = Join-Path $env:SystemRoot 'System32\wsl.exe'
if (-not (Test-Path -LiteralPath $wslPath -PathType Leaf)) {
    throw "WSL non trovato: $wslPath"
}

function Get-KeepAliveTask {
    Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}

function Show-GBrainLocalHealth {
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        $response = & $wslPath -d Ubuntu --exec /usr/bin/curl -fsS --connect-timeout 2 --max-time 5 'http://127.0.0.1:3131/health' 2>$null
        if ($LASTEXITCODE -eq 0) {
            try {
                $health = ($response | Out-String) | ConvertFrom-Json -ErrorAction Stop
                if ($health.status -eq 'ok') {
                    Write-Output "GBRAIN_LOCAL=OK version=$($health.version) engine=$($health.engine)"
                    return
                }
            }
            catch {
                # Bounded retry on malformed response.
            }
        }
        if ($attempt -lt 6) { Start-Sleep -Seconds 2 }
    }
    Write-Output 'GBRAIN_LOCAL=UNHEALTHY; check service; no automatic restart performed'
}

switch ($Mode) {
    'Status' {
        $task = Get-KeepAliveTask
        if ($null -eq $task) {
            Write-Output "KEEPALIVE_TASK=NOT_INSTALLED name=$taskName"
        }
        else {
            Write-Output "KEEPALIVE_TASK=$($task.State) name=$taskName"
            $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            if ($null -ne $info) { Write-Output "KEEPALIVE_LAST_RESULT=$($info.LastTaskResult)" }
        }
        Show-GBrainLocalHealth
    }
    'Install' {
        if ($null -ne (Get-KeepAliveTask)) {
            throw "Task $taskName gia presente: non sovrascrivo. Usare -Mode Status."
        }
        $windowsUser = (& whoami.exe).Trim()
        if ([string]::IsNullOrWhiteSpace($windowsUser)) { throw 'Utente Windows non identificato' }
        # A long-lived, unprivileged sleep process keeps WSL in use while signed in.
        $action = New-ScheduledTaskAction -Execute $wslPath -Argument '-d Ubuntu --exec /usr/bin/sleep infinity'
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $windowsUser
        $principal = New-ScheduledTaskPrincipal -UserId $windowsUser -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Keep Ubuntu WSL active for GBrain MCP while signed into Windows; separate from AppFactoryAutopilot' | Out-Null
        Start-ScheduledTask -TaskName $taskName
        Write-Output "KEEPALIVE_TASK=INSTALLED_AND_STARTED name=$taskName"
        Show-GBrainLocalHealth
    }
    'Remove' {
        if ($null -eq (Get-KeepAliveTask)) {
            Write-Output "KEEPALIVE_TASK=ALREADY_ABSENT name=$taskName"
            return
        }
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output "KEEPALIVE_TASK=REMOVED name=$taskName"
    }
}
