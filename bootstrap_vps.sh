#!/usr/bin/env bash
# =============================================================
# Bootstrap de un servidor VPS (Ubuntu/Debian) para el POS.
# Instala Docker, clona el repositorio y prepara .env.<entorno>.
#
# Uso (como root o con sudo):
#   bash bootstrap_vps.sh            # entorno = prod
#   bash bootstrap_vps.sh staging    # podrías usar un entorno propio
#
# Luego edita /opt/pos/.env.prod (dominios, claves) y despliega:
#   cd /opt/pos && bash deploy.sh prod
# =============================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/DeimerDurango18/Pos-Venta-Feroz.git}"
APP_DIR="${APP_DIR:-/opt/pos}"
ENTORNO="${1:-prod}"
FILE_ENV=".env.${ENTORNO}"

if [ "$(id -u)" -ne 0 ] && [ -z "${SUDO_UID:-}" ]; then
  echo "Ejecuta con root o sudo: sudo bash bootstrap_vps.sh"
  exit 1
fi

echo "==> [1/4] Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "    Instalando Docker Engine + compose..."
  apt-get update -y
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  code_name="$( (. /etc/os-release && echo "$VERSION_CODENAME") || echo focal )"
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${code_name} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi
docker --version
docker compose version

echo "==> [2/4] Clonando repositorio"
mkdir -p "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only origin main
fi
cd "$APP_DIR"

echo "==> [3/4] Archivo de entorno ${FILE_ENV}"
if [ ! -f "$FILE_ENV" ]; then
  cp ".env.prod.example" "$FILE_ENV"
  echo ""
  echo "    Creado $APP_DIR/$FILE_ENV. DEBES editarlo y rellenar:"
  echo "      - DOMAIN_APP  -> app pública (ej: pos.tudominio.com)"
  echo "      - DOMAIN_API  -> API pública (ej: api.pos.tudominio.com)"
  echo "      - SA_PASSWORD / SECRET_KEY -> claves reales"
  echo "      - CORS_ORIGINS -> https://<DOMAIN_APP>"
  echo "      - REGISTRY=ghcr.io  REGISTRY_ORG=deimerdurango18  TAG=latest"
  echo ""
  echo "    Luego despliega con:  cd $APP_DIR && bash deploy.sh $ENTORNO"
  exit 0
fi
echo "    $FILE_ENV ya existe, no se sobrescribió."

echo "==> [4/4] Desplegando"
cd "$APP_DIR"
bash deploy.sh "$ENTORNO"