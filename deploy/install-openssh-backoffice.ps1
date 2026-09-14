#Requires -RunAsAdministrator
# =====================================================================
#  Back-office seguro por SSH sobre el equipo del POS (Windows)
# ---------------------------------------------------------------------
#  Instala OpenSSH Server, lo deja como servicio automático, abre el
#  puerto 22 en el Firewall y refuerza sshd_config.
#
#  USO: clic derecho sobre este archivo -> "Ejecutar con PowerShell" (admin)
#       (si ya tienes la consola abierta como administrador, usa:
#        powershell -ExecutionPolicy Bypass -File .\install-openssh-backoffice.ps1)
#
#  DESPUÉS, desde cualquier equipo de la misma red:
#      ssh Deimer@192.168.80.158                         (consola remota)
#      ssh -N -L 28742:localhost:28742 -L 28743:localhost:28743 Deimer@192.168.80.158
#      -> luego abrir http://localhost:28742 en ESE equipo = back-office.
#      (el puerto 28742 NO queda expuesto a internet; viaja cifrado por SSH)
# =====================================================================

$ErrorActionPreference = "Stop"
$LOGF = Join-Path $PSScriptRoot "openssh-backoffice.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -LiteralPath $LOGF -Value $line -Encoding utf8
}

# Auto-elevación si no se corrió como administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Log "=== Back-office por SSH: inicio ==="

# 1) Instalar OpenSSH Server (recurso de Windows, sin descargas)
if (-not (Get-Service -Name "sshd" -ErrorAction SilentlyContinue)) {
    Log "Instalando OpenSSH.Server..."
    try {
        $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" | Select-Object -First 1
        if (-not $cap) { throw "No se encontro la capacidad OpenSSH.Server (revisa conexion/Windows Update)." }
        Add-WindowsCapability -Online -Name $cap.Name | Out-Null
    } catch {
        Log "ERROR instalando OpenSSH.Server: $($_.Exception.Message)"
        exit 1
    }
} else {
    Log "OpenSSH.Server ya estaba instalado."
}

# 2) Servicios automáticos y arranque
Set-Service -Name "sshd" -StartupType Automatic
Set-Service -Name "ssh-agent" -StartupType Automatic
Start-Service -Name "sshd" -ErrorAction SilentlyContinue
Start-Service -Name "ssh-agent" -ErrorAction SilentlyContinue
Log ("sshd: " + (Get-Service sshd).Status + "  | ssh-agent: " + (Get-Service ssh-agent).Status)

# 3) Firewall: permitir TCP 22 (LAN) 
if (-not (Get-NetFirewallRule -DisplayName "OpenSSH-Server (back-office)" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "OpenSSH-BackOffice-In-TCP" `
        -DisplayName "OpenSSH-Server (back-office)" `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
    Log "Regla de firewall para TCP 22 creada."
} else {
    Log "Regla de firewall TCP 22 ya existia."
}

# 4) Refuerzo de sshd_config (idempotente, con respaldo)
$sshcfg = "C:\ProgramData\ssh\sshd_config"
if (Test-Path $sshcfg) {
    if (-not (Test-Path "$sshcfg.bak")) { Copy-Item $sshcfg "$sshcfg.bak" -Force }
    $keys = "PasswordAuthentication|PubkeyAuthentication|PermitRootLogin|AllowUsers|AllowGroups|PrintMotd"
    $keep = Get-Content $sshcfg | Where-Object { $_ -notmatch "^\s*#?\s*($keys)\s" }
    if ($env:USERDOMAIN -ieq $env:COMPUTERNAME) {
        $allow = "AllowUsers $env:USERNAME"
    } else {
        $allow = "AllowUsers $env:USERDOMAIN\$env:USERNAME"
    }
    $add = @(
        "PasswordAuthentication yes",
        "PubkeyAuthentication yes",
        "PermitRootLogin no",
        $allow,
        "PrintMotd no"
    )
    Set-Content -LiteralPath $sshcfg -Value ($keep + $add) -Encoding ascii
    Restart-Service -Name "sshd" -Force -ErrorAction SilentlyContinue
    Log "sshd_config reforzado y reiniciado."
} else {
    Log "WARN: no se encontro $sshcfg (revision manual necesaria)."
}

# 5) Verificación y resumen
Start-Sleep -Seconds 2
$listen = Test-NetConnection -ComputerName localhost -Port 22 -WarningAction SilentlyContinue
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.AddressState -eq 'Preferred' } | Select-Object -First 1).IPAddress
Log "Puerto 22 escuchando: $($listen.TcpTestSucceeded)"
Log "Comprueba que la cuenta $env:USERNAME tenga una contrasena fuerte (Panel de control > Cuentas)."
Log ""
Log ">>> LISTO. Desde otro equipo de la red ejecuta:"
Log "      ssh $env:USERNAME@$ip"
Log "      ssh -N -L 28742:localhost:28742 -L 28743:localhost:28743 $env:USERNAME@$ip"
Log "      (abre http://localhost:28742 en ese equipo y entra al POS como admin)"
Log ""
Log "=== Back-office por SSH: fin (ver: $LOGF) ==="