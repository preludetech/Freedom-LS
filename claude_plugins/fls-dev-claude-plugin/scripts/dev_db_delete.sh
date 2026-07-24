#!/bin/sh
# Drops per-branch dev and test databases from the shared PostgreSQL container.
# Terminates active connections before dropping.
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
    echo "Not on a branch. Nothing to delete."
    exit 0
fi
DB_NAME="db_$(echo "$BRANCH" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g' | cut -c1-50)"
TEST_DB_NAME="test_${DB_NAME}"

# Terminate connections and drop dev database
psql_cmd -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" 2>/dev/null || true
psql_cmd -c "DROP DATABASE IF EXISTS ${DB_NAME};"

# Terminate connections and drop test database
psql_cmd -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TEST_DB_NAME}' AND pid <> pg_backend_pid();" 2>/dev/null || true
psql_cmd -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};"

echo "Dropped: ${DB_NAME}, ${TEST_DB_NAME}"
