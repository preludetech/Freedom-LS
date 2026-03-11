# Research: PostgreSQL Branch-Based Database Naming

## 1. PostgreSQL Database Naming Constraints

- **Max length:** 63 characters (NAMEDATALEN - 1). Names are silently truncated beyond this.
- **Allowed characters:** Letters, digits, underscores. Must start with a letter or underscore.
- **Case sensitivity:** Unquoted identifiers are folded to lowercase. Quoted identifiers preserve case but require quoting everywhere they're used.
- **Reserved names:** `template0`, `template1`, `postgres` cannot be dropped.

**Best practice:** Use lowercase, unquoted names with only letters, digits, and underscores.

Ref: https://www.postgresql.org/docs/17/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS

## 2. Sanitizing Git Branch Names

Git branch names can contain `/`, `-`, `.`, uppercase letters, and more. These must be sanitized for PostgreSQL:

```bash
# Shell sanitization
sanitize_branch() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g' | cut -c1-50
}
```

Mapping:
| Git branch | DB name |
|---|---|
| `main` | `db_main` |
| `feature/auth-flow` | `db_feature_auth_flow` |
| `fix/bug.123` | `db_fix_bug_123` |
| `UPPERCASE` | `db_uppercase` |

**Prefix with `db_`** to ensure the name always starts with a letter and to namespace dev databases.

**Truncate to ~50 chars** for the branch part, leaving room for the `db_` prefix and `test_` prefix (total max: `test_db_` + 50 = 58, within 63 limit).

## 3. Creating/Dropping Databases in Docker

Since the PostgreSQL container is already running (from `dev_db/docker-compose.yaml` on port 6543), use `psql` from the host:

```bash
# Create database
PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres -c "CREATE DATABASE ${DB_NAME};"
PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO pguser;"

# Drop database
PGPASSWORD=password psql -h 127.0.0.1 -p 6543 -U pguser -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
```

Alternatively, use `docker exec` if `psql` isn't installed on the host:

```bash
CONTAINER=$(docker compose -f dev_db/docker-compose.yaml ps -q postgres)
docker exec -e PGPASSWORD=password "$CONTAINER" psql -U pguser -d postgres -c "CREATE DATABASE ${DB_NAME};"
```

**Recommendation:** Use host `psql` via port 6543 — it's simpler and doesn't require knowing the container name.

## 4. `createdb` vs `CREATE DATABASE` SQL

| Approach | Pros | Cons |
|---|---|---|
| `createdb` | Simpler CLI, handles quoting | Separate binary, may not be installed |
| `CREATE DATABASE` via `psql` | Always available with `psql`, more explicit | Need to connect to an existing DB first (`postgres`) |

**Recommendation:** Use `psql -c "CREATE DATABASE ..."` connecting to the `postgres` database. It's more portable and explicit.

## 5. Granting Privileges

Since the `pguser` role creates the databases, it already owns them and has full privileges. The `GRANT ALL PRIVILEGES` is technically redundant but harmless and good for clarity:

```sql
GRANT ALL PRIVILEGES ON DATABASE db_my_branch TO pguser;
```

For the test database, Django needs `CREATE` permission on the database to create/drop the test schema. Since `pguser` is the owner, this is automatic.

## 6. Test Database Naming

Django automatically prepends `test_` to the `NAME` in `DATABASES['default']` when running tests. So:

- Dev DB: `db_main` → Test DB: `test_db_main`
- Dev DB: `db_feature_auth_flow` → Test DB: `test_db_feature_auth_flow`

The `dev_db_init.sh` script should create both databases upfront.

## 7. Gotchas with Long Branch Names

- **63-char limit:** `test_db_` prefix is 8 chars, leaving 55 for the sanitized branch name. Truncating at 50 chars provides a safe margin.
- **Collisions:** `feature/foo-bar` and `feature/foo_bar` both sanitize to `feature_foo_bar`. This is unlikely in practice but worth noting. Could add a short hash suffix if needed.
- **Detached HEAD:** No branch name available. Fall back to default `db`.
