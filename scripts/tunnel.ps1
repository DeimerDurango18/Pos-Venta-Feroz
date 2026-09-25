# =============================================================
# tunnel.ps1 — Mantiene el túnel gratuito de Cloudflare (quick tunnel)
# hacia el backend del POS. Se ejecuta en un bucle: si cloudflared cae,
# lo relanza y guarda la URL pública vigente en scripts\tunnel_url.txt.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1 -BackendUrl http://127.0.0.1:28743
# =============================================================
param([string]$BackendUrl = "http://127.0.0.1:28743")
$ErrorActionPreference = "Continue"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $dir "tunnel.log"
$urlPath = Join-Path $dir "tunnel_url.txt"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] cloudflared no está en el PATH. Instálalo desde:"
    Write-Host "        https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
}

Write-Host "=== TÚNEL CLOUDFLARE (quick tunnel) -> $BackendUrl ==="
Write-Host "Presiona Ctrl+C para detener. La URL queda en $urlPath"
Write-Host ""

while ($true) {
    try {
        if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
            $args = @("tunnel", "--url", $BackendUrl, "--no-autoupdate", "--logfile", $logPath, "--loglevel", "info")
            $p = Start-Process -FilePath "cloudflared" -ArgumentList $args -PassThru -WindowStyle Hidden
            Write-Host "[$(Get-Date -Format HH:mm:ss)] cloudflared iniciado (PID $($p.Id))"
        }
    } catch {
        Write-Host "[$(Get-Date -Format HH:mm:ss)] No se pudo iniciar cloudflared: $($_.Exception.Message)"
    }

    try {
        if (Test-Path $logPath) {
            $log = Get-Content $logPath -Raw -ErrorAction SilentlyContinue
            if ($log -match "https://[a-z0-9-]+\.trycloudflare\.com") {
                $url = $Matches[0]
                $prev = if (Test-Path $urlPath) { (Get-Content $urlPath -Raw).Trim() } else { "" }
                if ($url -ne $prev) {
                    Set-Content -Path $urlPath -Value $url
                    Write-Host "[$(Get-Date -Format HH:mm:ss)] ⚠ URL NUEVA: $url"
                    Write-Host "   Actualiza en Pages: npx wrangler pages secret put API_ORIGIN --project-name pos-inventario-feroz-d"
                }
            }
        }
        if (Test-Path $urlPath) {
            $cur = (Get-Content $urlPath -Raw).Trim()
            Write-Host "[$(Get-Date -Format HH:mm:ss)] URL vigente: $cur"
        }
    } catch {
        Write-Host "[$(Get-Date -Format HH:mm:ss)] Error chequeando URL: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds 60
}