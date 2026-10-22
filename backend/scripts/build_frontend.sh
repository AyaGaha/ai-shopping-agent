#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../frontend"
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20 is required to build the frontend." >&2
  exit 1
fi
node_major="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$node_major" != "20" && "$node_major" != "22" ]]; then
  echo "Node.js 20 or 22 is required (found $(node --version))." >&2
  exit 1
fi
npm ci
npm run build
