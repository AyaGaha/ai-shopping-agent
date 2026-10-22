#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
COMPOSE_FILE="$INFRA_DIR/docker-compose.yml"
INFRA_ENV="$INFRA_DIR/.env"
SECRETS_DIR="$INFRA_DIR/.secrets"
API_CREDENTIALS="$SECRETS_DIR/woocommerce-api.json"
SITE_URL="${SITE_URL:-http://localhost}"
WORDPRESS_PORT="${WORDPRESS_PORT:-80}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo 'Usage: SITE_URL=http://<public-ip-or-domain> [WORDPRESS_PORT=80] infra/provision.sh'
  echo 'Creates WordPress/WooCommerce, seeds catalog and API credentials, syncs and indexes products.'
  exit 0
fi
command -v docker >/dev/null || { echo "Docker is required. Install Docker Engine and Compose first." >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 is required." >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl is required to generate local secrets." >&2; exit 1; }
[[ "$SITE_URL" =~ ^https?://[^/]+$ ]] || { echo "SITE_URL must be an origin, e.g. http://203.0.113.10" >&2; exit 1; }

umask 077
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
if [[ ! -f "$INFRA_ENV" ]]; then
  cat > "$INFRA_ENV" <<EOF
MYSQL_DATABASE=wordpress
MYSQL_USER=wordpress
MYSQL_PASSWORD=$(openssl rand -hex 24)
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
WORDPRESS_PORT=$WORDPRESS_PORT
EOF
  chmod 600 "$INFRA_ENV"
fi

compose() { docker compose --env-file "$INFRA_ENV" -f "$COMPOSE_FILE" "$@"; }
wpcli() { compose --profile tools run --rm --no-deps wpcli "$@"; }

echo "Starting WordPress and MySQL (host port $WORDPRESS_PORT)..."
compose up -d db wordpress
ready=false
for _ in $(seq 1 60); do
  if wpcli core version >/dev/null 2>&1; then ready=true; break; fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo "WordPress did not become ready. Inspect the Docker Compose logs." >&2
  exit 1
fi

if ! wpcli core is-installed >/dev/null 2>&1; then
  # A surviving host-side credential file belongs to the old DB; issue a new key.
  rm -f "$API_CREDENTIALS"
  admin_password="$(openssl rand -hex 20)"
  wpcli core install --url="$SITE_URL" --title="AI Shopping Agent Demo" \
    --admin_user="agentadmin" --admin_password="$admin_password" \
    --admin_email="admin@example.invalid" --skip-email
  printf '%s\n' "$admin_password" > "$SECRETS_DIR/wordpress-admin-password"
  chmod 600 "$SECRETS_DIR/wordpress-admin-password"
  echo "Initial WordPress admin password saved under infra/.secrets/ (login: agentadmin)."
else
  wpcli option update home "$SITE_URL" >/dev/null
  wpcli option update siteurl "$SITE_URL" >/dev/null
fi

wpcli plugin is-installed woocommerce >/dev/null 2>&1 || wpcli plugin install woocommerce --version=11.2.1 --activate
wpcli plugin activate woocommerce >/dev/null
wpcli option update woocommerce_currency TND >/dev/null
wpcli option update woocommerce_default_country TN >/dev/null

echo "Creating/updating the demo products..."
wpcli eval-file /workspace/infra/provision-products.php

if [[ ! -s "$API_CREDENTIALS" ]]; then
  credential_tmp="$(mktemp "$SECRETS_DIR/.woocommerce-api.XXXXXX")"
  chmod 600 "$credential_tmp"
  if ! wpcli eval-file /workspace/infra/create-api-key.php > "$credential_tmp"; then
    rm -f "$credential_tmp"
    echo "Could not create WooCommerce REST API key." >&2
    exit 1
  fi
  python3 - "$credential_tmp" "$API_CREDENTIALS" <<'PY'
import json, os, sys
source, target = sys.argv[1:]
with open(source, encoding="utf-8") as stream:
    credentials = json.load(stream)
if not credentials.get("consumer_key", "").startswith("ck_") or not credentials.get("consumer_secret", "").startswith("cs_"):
    raise SystemExit("WP-CLI returned invalid WooCommerce credentials")
with open(target, "w", encoding="utf-8") as stream:
    json.dump(credentials, stream)
    stream.write("\n")
os.chmod(target, 0o600)
PY
  rm -f "$credential_tmp"
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"; fi
python3 - "$ROOT_DIR/.env" "$API_CREDENTIALS" "$SITE_URL" <<'PY'
import json, os, sys
from pathlib import Path
env_path, credentials_path = Path(sys.argv[1]), Path(sys.argv[2])
credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
lines = env_path.read_text(encoding="utf-8").splitlines()
values = {
    "WOOCOMMERCE_URL": sys.argv[3].rstrip("/") + "/wp-json/wc/v3",
    "WOOCOMMERCE_CONSUMER_KEY": credentials["consumer_key"],
    "WOOCOMMERCE_CONSUMER_SECRET": credentials["consumer_secret"],
}
for name, value in values.items():
    lines = [line for line in lines if not line.startswith(name + "=")]
    lines.append(name + "=" + value)
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(env_path, 0o600)
PY

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT_DIR/.venv"
  "$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
  "$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
fi

echo "Syncing the live WooCommerce catalog and building the Chroma index..."
(cd "$ROOT_DIR" && .venv/bin/python scripts/sync_woocommerce_catalog.py)
(cd "$ROOT_DIR" && .venv/bin/python scripts/index_catalog.py)

echo "Provisioning complete. WordPress: $SITE_URL (host port $WORDPRESS_PORT)."
echo "WooCommerce credentials are stored in root .env and infra/.secrets/ (permissions 0600)."
if ! grep -q '^GROQ_API_KEY=' "$ROOT_DIR/.env" || grep -q '^GROQ_API_KEY=your_key_here$' "$ROOT_DIR/.env"; then
  echo "Set GROQ_API_KEY in $ROOT_DIR/.env before starting the agent."
fi
