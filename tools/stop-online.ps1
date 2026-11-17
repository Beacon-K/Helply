# Stops the Helply online site that start-online.bat started from THIS folder, and nothing else.
# It matches processes by where their program lives (this folder's virtual environment and
# tools\cloudflared.exe), so other Python programs and other copies of Helply are left alone.
# Run with -List to only show what would be stopped.
param([string]$Root, [switch]$List)

$Root = (Resolve-Path $Root).Path.TrimEnd('\')
$self = $PID
$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $self -and (
        # waitress, run_jobs and monitor_check all run with this folder's virtual environment
        ($_.Name -eq 'python.exe' -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith("$Root\", 'OrdinalIgnoreCase') -and
            $_.CommandLine -match 'waitress|run_jobs|monitor_check') -or
        ($_.Name -eq 'cloudflared.exe' -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith("$Root\", 'OrdinalIgnoreCase')) -or
        # the console window that start-online.bat is sitting in
        ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'start-online\.bat')
    )
}

if (-not $targets) { Write-Host 'Nothing from this folder is running.'; exit 0 }
foreach ($p in $targets) {
    Write-Host ("  {0,-16} pid {1}" -f $p.Name, $p.ProcessId)
    if (-not $List) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
}
