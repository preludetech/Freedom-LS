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

# Non-superuser roles — optional for local dev, required in CI so that
# migration 0002's REVOKE UPDATE/DELETE grants actually take effect under
# test. These roles are inert when the default (pguser) credentials are
# used; they only get exercised when a developer opts in by setting
# FLS_APP_DB_USER / FLS_ERASURE_DB_USER in their environment (mirroring
# what .github/workflows/tests.yml does in CI).
psql_cmd <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fls_app') THEN
        CREATE ROLE fls_app WITH LOGIN PASSWORD 'fls_app_pw' CREATEDB NOSUPERUSER;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fls_erasure_role') THEN
        CREATE ROLE fls_erasure_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fls_erasure_user') THEN
        CREATE ROLE fls_erasure_user WITH LOGIN PASSWORD 'fls_erasure_pw' NOSUPERUSER;
        GRANT fls_erasure_role TO fls_erasure_user;
    END IF;
END
$$;
SQL
# Hand DB ownership to fls_app so migrations run by fls_app can create
# and GRANT on tables. pguser is a superuser so this does not affect the
# default local dev flow — superusers bypass ownership checks.
psql_cmd -c "ALTER DATABASE ${DB_NAME} OWNER TO fls_app;"
psql_cmd -c "ALTER DATABASE ${TEST_DB_NAME} OWNER TO fls_app;"

echo "Databases ready: ${DB_NAME}, ${TEST_DB_NAME}"
echo "Non-superuser roles ready: fls_app, fls_erasure_role, fls_erasure_user"
