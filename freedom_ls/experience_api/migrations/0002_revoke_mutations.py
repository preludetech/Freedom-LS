"""Defence-in-depth DB-level append-only enforcement.

REVOKEs UPDATE and DELETE on experience_api_event and
experience_api_actorerasure from the current (application) role, then creates
an fls_erasure_role group role and GRANTs UPDATE on the events table to it.
The erasure role intentionally receives no grants on actor_erasure -- the
audit log is strictly insert-only for everyone.

The role is created NOLOGIN. A separate login user (provisioned out-of-band)
is made a member via GRANT fls_erasure_role TO <login_user>; the erase_actor
management command connects as that login user via a separate "erasure"
Django DB connection.

Security note: the application DB user must not be a Postgres superuser --
superusers bypass grants. See docs/deployment-security-checklist.md
"Database Security".
"""

from django.db import migrations


FORWARD_SQL = """
-- Revoke write privileges on the event log for the current application role.
DO $$
BEGIN
  EXECUTE 'REVOKE UPDATE, DELETE ON TABLE experience_api_event FROM ' || quote_ident(current_user);
  EXECUTE 'REVOKE UPDATE, DELETE ON TABLE experience_api_actorerasure FROM ' || quote_ident(current_user);
EXCEPTION WHEN insufficient_privilege THEN
  NULL;
END$$;

-- Create the erasure role (idempotent, NOLOGIN group role).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fls_erasure_role') THEN
    CREATE ROLE fls_erasure_role NOLOGIN;
  END IF;
END$$;

-- Grant UPDATE on the events table to the erasure role. Do NOT grant
-- UPDATE / DELETE on actor_erasure -- that table is append-only for every
-- caller including the erasure role.
GRANT UPDATE ON TABLE experience_api_event TO fls_erasure_role;
"""

REVERSE_SQL = """
-- Re-grant UPDATE / DELETE to the application role.  Does NOT drop
-- fls_erasure_role -- dropping a role that still owns grants is risky.
DO $$
BEGIN
  EXECUTE 'GRANT UPDATE, DELETE ON TABLE experience_api_event TO ' || quote_ident(current_user);
  EXECUTE 'GRANT UPDATE, DELETE ON TABLE experience_api_actorerasure TO ' || quote_ident(current_user);
EXCEPTION WHEN others THEN
  NULL;
END$$;

REVOKE UPDATE ON TABLE experience_api_event FROM fls_erasure_role;
"""


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("experience_api", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
