# Script de despliegue manual en el VPS (alternativa cuando no hay CI).
# Ejecutar en el servidor dentro del directorio del proyecto:
#   bash deploy.sh prod
#   bash deploy.sh staging
set -euo pipefail

ENTORNO="${1:-prod}"
FILE_ENV=".env.${ENTORNO}"

if [ ! -f "$FILE_ENV" ]; then
  echo "Falta $FILE_ENV — copia .env.prod.example"
  exit 1
fi

echo "==> Determinando imagenes"
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-ghcr.io}"
REGISTRY_ORG="${REGISTRY_ORG:?Define REGISTRY_ORG}"
GHCR_USER="${GHCR_USER:?Define GHCR_USER}"
GHCR_TOKEN="${GHCR_TOKEN:?Define GHCR_TOKEN en el .env del servidor}"

echo "$GHCR_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USER" --password-stdin

echo "==> Descargando imagenes"
docker compose -f docker-compose.yml -f compose.prod.yml --env-file "$FILE_ENV" pull backend frontend

echo "==> Levantando stack"
docker compose -f docker-compose.yml -f compose.prod.yml --env-file "$FILE_ENV" up -d db backend frontend caddy

DOMAIN_API="$(grep '^DOMAIN_API=' "$FILE_ENV" | cut -d= -f2-)"
echo "==> Verificando https://${DOMAIN_API}/estado"
curl -fsS "https://${DOMAIN_API}/estado" && echo " -> OK"

docker image prune -f || true
echo "==> Despliegue completado ($ENTORNO)"