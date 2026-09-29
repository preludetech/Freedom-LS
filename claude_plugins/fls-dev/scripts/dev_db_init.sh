#!/bin/sh
# Creates per-branch dev and test databases in the shared PostgreSQL container,
# owned by the non-superuser fls_dev role (created here if it doesn't exist yet).
# Idempotent: skips creation if a database or the role already exists.
# Assumes the docker container from dev_db/ is already running on port 6543.
#
# NOTE: The branch-to-db-name sanitization here mirrors
# freedom_ls.base.git_utils.branch_to_db_name — keep them in sync.

set -e

psql_cmd() {
    PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres "$@"
}

# Role first: the databases below are owned by it.
psql_cmd -v ON_ERROR_STOP=1 -f - <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fls_dev') THEN
        CREATE ROLE fls_dev LOGIN PASSWORD 'password' CREATEDB;
    END IF;
END
$$;
SQL

# The timeout sits on the role, not on individual databases, so pguser's own
# admin sessions are never cut off. No other timeout is set: statement or lock
# timeouts would abort slow migrations or a developer's open shell.
psql_cmd -c "ALTER ROLE fls_dev SET idle_in_transaction_session_timeout = '15min';"

ensure_db() {
    if psql_cmd -tc "SELECT 1 FROM pg_database WHERE datname = '$1'" | grep -q 1; then
        psql_cmd -c "ALTER DATABASE $1 OWNER TO fls_dev;"
    else
        psql_cmd -c "CREATE DATABASE $1 OWNER fls_dev;"
    fi
}

# Detect branch and sanitize
BRANCH=$(git branch --show-current 2>/dev/null || true)
if [ -z "$BRANCH" ]; then
    DB_NAME="db"
else
    DB_NAME="db_$(echo "$BRANCH" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g' | cut -c1-50)"
fi
TEST_DB_NAME="test_${DB_NAME}"

echo "Branch: ${BRANCH:-<none>} -> DB: ${DB_NAME}"

ensure_db "$DB_NAME"
ensure_db "$TEST_DB_NAME"

echo "Databases ready: ${DB_NAME}, ${TEST_DB_NAME}"
