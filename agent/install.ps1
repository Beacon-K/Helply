<#
Helply monitoring agent - Windows installer (Windows Server 2016+ / Windows 10+).

  powershell -ExecutionPolicy Bypass -File install.ps1 -Url https://YOUR-HELPLY -Token TOKEN
  powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall

Run as Administrator. Installs C:\ProgramData\HelplyAgent (agent + private Python venv with psutil),
a config file only SYSTEM/Administrators/the agent can read, and a scheduled task "HelplyAgent" that
starts at boot as LOCAL SERVICE and restarts if it stops. The agent only sends readings.
#>
param(
    [string]$Url = "",
    [string]$Token = "",
    [int]$Interval = 10,
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$Dir = Join-Path $env:ProgramData "HelplyAgent"
$Conf = Join-Path $Dir "agent.conf"
$TaskName = "HelplyAgent"

function Say($text) { Write-Host "[helply] $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host "[helply] $text" -ForegroundColor Red; exit 1 }

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "Please run PowerShell as Administrator."
}

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    if (Test-Path $Dir) { Remove-Item -Recurse -Force $Dir }
    Say "Helply agent removed."
    exit 0
}

$Url = $Url.TrimEnd("/")
if (-not $Url) { Fail "Missing -Url (the address of your Helply, e.g. https://helply.example.com)." }
if (-not ($Url.StartsWith("https://") -or $Url.StartsWith("http://127.0.0.1") -or $Url.StartsWith("http://localhost"))) {
    Fail "-Url must start with https://"
}
if (-not $Token) { $Token = Read-Host "Agent token" }
if (-not $Token) { Fail "Missing -Token (shown in Helply when you add the server)." }
if ($Interval -lt 5) { $Interval = 10 }

# Find a real Python 3.8+ (not the Microsoft Store shortcut).
$python = $null
foreach ($candidate in @("py", "python", "python3")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $cmd -or $cmd.Source -like "*WindowsApps*") { continue }
    $pyArgs = @()
    if ($candidate -eq "py") { $pyArgs = @("-3") }
    try {
        $exe = & $cmd.Source @pyArgs -c "import sys; print(sys.executable if sys.version_info >= (3, 8) else '')" 2>$null
    } catch { $exe = $null }
    if ($exe) { $python = $exe.Trim(); break }
}
if (-not $python) {
    Fail "Python 3.8+ not found. Install it from https://www.python.org/downloads/windows/ (tick 'Install for all users' and 'Add to PATH'), then run this again."
}
Say "Using Python: $python"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$agent = Join-Path $Dir "helply_agent.py"
Say "Downloading the agent from $Url"
Invoke-WebRequest -UseBasicParsing -Uri "$Url/monitoring/agent/helply_agent.py" -OutFile "$agent.new"
if (-not (Select-String -Path "$agent.new" -Pattern "Helply monitoring agent" -Quiet)) { Fail "The download does not look like the agent." }
Move-Item -Force "$agent.new" $agent

$venv = Join-Path $Dir "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Say "Creating a private Python environment"
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python environment." }
}
Say "Installing psutil"
& (Join-Path $venv "Scripts\python.exe") -m pip install -q --disable-pip-version-check psutil
if ($LASTEXITCODE -ne 0) { Fail "Could not install psutil (is pypi.org reachable?)." }

@"
# Helply agent settings. Keep this file private: the token identifies this server.
HELPLY_URL=$Url
HELPLY_TOKEN=$Token
HELPLY_INTERVAL=$Interval
"@ | Set-Content -Path $Conf -Encoding ASCII

# Least privilege: run as LOCAL SERVICE. A Python installed only for one user lives in that user's
# profile, which LOCAL SERVICE cannot read - then fall back to SYSTEM and say so.
$runAs = "NT AUTHORITY\LOCALSERVICE"
if ($python -like "$env:SystemDrive\Users\*") {
    $runAs = "NT AUTHORITY\SYSTEM"
    Say "Python is installed for one user only, so the agent will run as SYSTEM. Reinstall Python 'for all users' to run it as LOCAL SERVICE."
}
# Config readable only by SYSTEM, Administrators and the account the agent runs as.
& icacls $Conf /inheritance:r /grant:r "*S-1-5-18:F" "*S-1-5-32-544:F" "*S-1-5-19:R" | Out-Null

$pythonw = Join-Path $venv "Scripts\pythonw.exe"
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$agent`" --config `"$Conf`"" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -AtStartup
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $runAs -LogonType ServiceAccount -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $settings `
    -Description "Helply monitoring agent (read-only reporter)" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Say "Testing one report..."
& (Join-Path $venv "Scripts\python.exe") $agent --config $Conf --once | Select-Object -Last 1
Start-Sleep -Seconds 3
$state = (Get-ScheduledTask -TaskName $TaskName).State
Say "Done. Scheduled task '$TaskName' is $state (runs as $runAs). The server's card in Helply turns live within ~10 seconds."
