#!/bin/sh
# Drops per-branch dev and test databases, and any worker test databases xdist
# left behind, from the shared PostgreSQL container.
# DROP DATABASE ... WITH (FORCE) terminates active connections and drops the
# database in one statement (Postgres 13+).
#
# NOTE: The branch-to-db-name sanitization here mirrors
# freedom_ls.base.git_utils.branch_to_db_name — keep them in sync.

set -e

psql_cmd() {
    PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres "$@"
}

drop_db() {
    psql_cmd -c "DROP DATABASE IF EXISTS $1 WITH (FORCE);"
}

# Detect branch and sanitize
BRANCH=$(git branch --show-current 2>/dev/null || true)
if [ -z "$BRANCH" ]; then
    echo "Not on a branch. Nothing to delete."
    exit 0
fi
DB_NAME="db_$(echo "$BRANCH" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g' | cut -c1-50)"
TEST_DB_NAME="test_${DB_NAME}"

# A plain assignment, so set -e stops the script if the query fails.
WORKER_DBS=$(psql_cmd -Atc "SELECT datname FROM pg_database WHERE datname LIKE '${TEST_DB_NAME}\_gw%'")

drop_db "$DB_NAME"
drop_db "$TEST_DB_NAME"
for WORKER_DB in $WORKER_DBS; do
    drop_db "$WORKER_DB"
done

WORKER_DBS_CSV=$(echo "$WORKER_DBS" | tr '\n' ',' | sed 's/,/, /g; s/, $//')
echo "Dropped: ${DB_NAME}, ${TEST_DB_NAME}${WORKER_DBS_CSV:+, $WORKER_DBS_CSV}"
