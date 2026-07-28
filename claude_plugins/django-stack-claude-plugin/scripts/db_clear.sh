#!/bin/sh
# Clears local dev database data and media. Set DB_DATA_PATH to your dev
# Postgres data directory (see dev_db/docker-compose.yaml). No default is
# assumed — if DB_DATA_PATH is unset we skip the data wipe rather than guess.

if [ -n "${DB_DATA_PATH}" ]; then
    rm -rf "${DB_DATA_PATH}"
else
    echo "db_clear: DB_DATA_PATH is not set — skipping database data wipe." >&2
    echo "          Set DB_DATA_PATH to your dev Postgres data dir to enable it." >&2
fi

# Only clear a media dir that actually exists at the current path.
[ -d media ] && rm -rf media
