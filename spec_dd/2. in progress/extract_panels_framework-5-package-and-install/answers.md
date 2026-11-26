# Answers: extract_panels_framework-5-package-and-install

Asked by `/sdd:start` before the spec was written.

- Q: How should the new django-panel-framework repo start its git history? → A: A fresh import commit that copies the app in and cites the FLS commit it came from. No history extraction. (asked up front)
- Q: How should FLS drop the old `freedom_ls_panel_framework_bulkactionrun` table? → A: No SQL. A `RunPython` step checks that the table exists through `connection.introspection` and calls `schema_editor.delete_model` on a throwaway model with that `db_table`. The `django_migrations` and ContentType rows are removed through the ORM. No raw-SQL security review is needed. (asked up front)
- Q: Where should the "installed panel_framework is the locked rev" check run? → A: Before landing. An fls-dev check runs when a worktree lands and fails if the editable checkout's HEAD is not the locked rev or has uncommitted changes. It does not block commits while work is in progress. (asked up front)
- Q: Should the implementation push to the public GitHub repo and create the v0.1.0 tag itself? → A: Yes. Agents push to `preludetech/django-panel-framework` and create and push `v0.1.0` once the package suite passes, without stopping to ask. (asked up front)
- Q: Who changes the other repos' Docker setup? → A: This spec commits the `git` addition to `freedom_ls_infra/fls-base/Dockerfile` directly. The concrete template's Dockerfile split (a Python stage that feeds its Tailwind stage) goes into `upgrade_notes.md` as a manual step, applied by `/fls-dev:update_concrete_projects`. (asked up front)
- Q: Keep or drop FLS's drift guard `educator_interface/tests/invariants/test_framework_copies_match_base.py` once the framework is an external package? → A: Drop it. From `v0.1.0` the package owns its copies and may diverge from FLS's originals on purpose. (asked while research ran)
