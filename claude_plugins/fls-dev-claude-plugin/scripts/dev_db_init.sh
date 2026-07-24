#!/bin/sh
# Creates per-branch dev and test databases in the shared PostgreSQL container.
# Idempotent: skips creation if database already exists.
# Assumes the docker container from dev_db/ is already running on port 6543.
#
# NOTE: The branch-to-db-name sanitization here mirrors
# freedom_ls.base.git_utils.branch_to_db_name — keep them in sync.

set -e

psql_cmd() {
    PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres "$@"
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

# Create dev database if not exists
psql_cmd -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    psql_cmd -c "CREATE DATABASE ${DB_NAME};"
psql_cmd -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO pguser;"

# Create test database if not exists
psql_cmd -tc "SELECT 1 FROM pg_database WHERE datname = '${TEST_DB_NAME}'" | grep -q 1 || \
    psql_cmd -c "CREATE DATABASE ${TEST_DB_NAME};"
psql_cmd -c "GRANT ALL PRIVILEGES ON DATABASE ${TEST_DB_NAME} TO pguser;"

echo "Databases ready: ${DB_NAME}, ${TEST_DB_NAME}"
