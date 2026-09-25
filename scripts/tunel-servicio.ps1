# =============================================================
# tunel-servicio.ps1 — Registra una tarea programada de Windows que
# inicia tunnel.ps1 al encender el equipo, manteniendo el túnel público
# del POS levantado automáticamente (se reinicia si muere).
#
# Requiere consola ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File scripts\tunel-servicio.ps1
#
# Para desinstalar la tarea:
#   Unregister-ScheduledTask -TaskName "pos-tunnel" -Confirm:$false
# =============================================================
$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $dir "tunnel.ps1"
$taskName = "pos-tunnel"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[ERROR] Debes ejecutar este script como Administrador."
    exit 1
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 9999) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Mantiene el túnel público Cloudflare para el POS (quick tunnel)." -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Tarea '$taskName' instalada y arrancada."
Write-Host "El túnel se mantiene vivo al encender el equipo. El script vive en $scriptPath"
Write-Host "Lógica: si cloudflared muere, se relanza solo y guarda la URL en scripts\tunnel_url.txt"