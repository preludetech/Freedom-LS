# Prerequisite: `learner-terminology-rename`

**Added by the `learner-terminology-rename` work. This spec's own prose and plan are untouched —
read this file alongside them, not instead of them.**

## Why you are reading this

`spec_dd/2. in progress/learner-terminology-rename` renames three apps. This spec's plan specifies
files and identifiers that no longer spell the way it says they do. Everything below is stale in
`2. plan.md` and must be translated as you implement it.

| Old | New |
| --- | --- |
| `freedom_ls.student_interface` | `freedom_ls.learner_interface` |
| `freedom_ls.student_management` | `freedom_ls.learner_management` |
| `freedom_ls.student_progress` | `freedom_ls.learner_progress` |
| app label `freedom_ls_student_interface` | `freedom_ls_learner_interface` |
| `StudentInterfaceConfig` | `LearnerInterfaceConfig` |
| URL namespace `student_interface:` | `learner_interface:` |

## The specific trap: `checks.py`

The plan (§ around line 591) specifies a **not-yet-created** file:

```
freedom_ls/student_interface/checks.py
```

with Django system-check IDs `freedom_ls_student_interface.E001`, `.E002` and `.W001`.

**That file still does not exist.** Confirm that for yourself before writing it — it was absent
when the rename swept the tree, which is why the rename could not fix it for you. Post-rename it
must be:

```
freedom_ls/learner_interface/checks.py
```

with check IDs `freedom_ls_learner_interface.E001`, `freedom_ls_learner_interface.E002` and
`freedom_ls_learner_interface.W001`.

The check-ID convention is `<app_label>.<ID>`, and the app label is now
`freedom_ls_learner_interface`. Anything else is wrong.

Related: `freedom_ls/learner_interface/apps.py` is still a bare `AppConfig` with no `ready()`, as
the plan observed — that observation survives the rename, only the class name changed
(`StudentInterfaceConfig` → `LearnerInterfaceConfig`).

## The other trap: do not copy naming out of the shipped conformance package

The plan duplicates the `FLS_NAMESPACE_PROBES` list inline (§ around lines 375–399) using
`student_interface:*` viewnames and `"freedom_ls.student_interface"` app paths. **The shipped
`freedom_ls/contrib/conformance/` package has already been updated to `learner_interface:*` and
`"freedom_ls.learner_interface"`.** Copy from the live package, not from this plan's inline copy
and not from the acceptance table at lines 27–31.

The corrected probe table:

| App path | Viewname | Tier |
| --- | --- | --- |
| `freedom_ls.learner_interface` | `learner_interface:dashboard` | contract |
| `freedom_ls.learner_interface` | `learner_interface:course_detail` | contract |
| `freedom_ls.learner_interface` | `learner_interface:course_home` | contract |
| `freedom_ls.learner_interface` | `learner_interface:initiate_course_access` | contract |
| `freedom_ls.learner_interface` | `learner_interface:courses` | internal (prunable) |

## Why the app-path half matters more than it looks

A stale **viewname** fails loudly — `NoReverseMatch`. A stale **app path** fails silently:
`probe_namespace_reverses` skips when its app is not installed, and `freedom_ls.student_interface`
is no longer installed. The whole probe table then self-disarms and the suite reports green with
skips, having tested nothing.

Verify by skip count, not exit code:

```bash
uv run pytest freedom_ls/contrib/conformance -rs
```

Every FLS namespace probe must **run**.

## Full reference

`spec_dd/2. in progress/learner-terminology-rename/upgrade_notes.md` carries the complete old→new
table — import paths, app labels, `AppConfig` class names, URL names, template paths, static
paths, permission strings, the role key and default table names.
