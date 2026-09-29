#!/bin/sh
set -eu
COMPOSE_FILE="$(dirname "$0")/docker-compose.yaml"
echo "This destroys the dev server's volume: every worktree's database, and other projects' too."
printf 'Type "yes" to continue: '
read -r answer
[ "$answer" = "yes" ] || { echo "Aborted."; exit 1; }
docker compose -f "$COMPOSE_FILE" down -v
docker compose -f "$COMPOSE_FILE" up -d
echo "Reset. Run setup in each worktree: .claude/fls-dev/scripts/install_dev.sh"
