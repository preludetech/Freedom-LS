"""Grant fls_erasure_role the read / insert privileges the erasure flow
actually needs.

Migration 0002 granted UPDATE on experience_api_event but nothing else.
erase_actor also needs:

- SELECT on experience_api_event — to find rows by actor_user_id /
  actor_ifi before anonymising them.
- INSERT on experience_api_actorerasure — to write the audit row.

No UPDATE / DELETE is granted on experience_api_actorerasure: that table
remains append-only for every caller, erasure role included
(test_erasure_role_cannot_update_actor_erasure pins this guarantee).
"""

from django.db import migrations


FORWARD_SQL = """
GRANT SELECT ON TABLE experience_api_event TO fls_erasure_role;
GRANT INSERT ON TABLE experience_api_actorerasure TO fls_erasure_role;
"""

REVERSE_SQL = """
REVOKE SELECT ON TABLE experience_api_event FROM fls_erasure_role;
REVOKE INSERT ON TABLE experience_api_actorerasure FROM fls_erasure_role;
"""


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("experience_api", "0002_revoke_mutations"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
