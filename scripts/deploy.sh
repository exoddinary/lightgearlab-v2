#!/usr/bin/env bash
# Deploy web/ to lightgearlab.com (nginx on 139.162.35.58, behind Cloudflare).
#
# Usage:
#   scripts/deploy.sh            # deploy
#   scripts/deploy.sh --dry-run  # show what would change, touch nothing
#
# Cloudflare caches js/css/svg/png for up to ~4h; purge the cache after
# deploying changed assets.
set -euo pipefail

HOST="root@139.162.35.58"
REMOTE_DIR="/var/www/lightgearlab.com"

cd "$(dirname "$0")/.."

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]]; then
  DRY_RUN="n"
fi

# macOS openrsync has no --chown, so ownership is fixed afterwards on the server.
rsync -rlptzi${DRY_RUN} --delete \
  --exclude .DS_Store \
  --exclude logos/originals/ \
  web/ "${HOST}:${REMOTE_DIR}/"

if [[ -n "$DRY_RUN" ]]; then
  echo "Dry run complete; nothing was changed."
  exit 0
fi

ssh "$HOST" "chown -R www-data:www-data '${REMOTE_DIR}' && nginx -t"

echo "Deployed to https://lightgearlab.com"
echo "Remember to purge the Cloudflare cache if assets changed."
