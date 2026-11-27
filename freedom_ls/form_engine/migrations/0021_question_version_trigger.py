"""Make the question version table refuse UPDATE and DELETE in the database."""

from django.db import migrations

TABLE = "freedom_ls_form_engine_formquestionversion"
# Equals TRIGGER_NAME in form_engine.models.
TRIGGER = "form_question_version_immutable"
FUNCTION = "form_question_version_refuse_change"

CREATE = f"""
CREATE FUNCTION {FUNCTION}() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'FormQuestionVersion rows are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER {TRIGGER} BEFORE UPDATE OR DELETE ON {TABLE}
FOR EACH ROW EXECUTE FUNCTION {FUNCTION}();
"""

DROP = f"""
DROP TRIGGER {TRIGGER} ON {TABLE};
DROP FUNCTION {FUNCTION}();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_form_engine", "0020_backfill_question_versions"),
    ]

    operations = [migrations.RunSQL(CREATE, DROP)]
