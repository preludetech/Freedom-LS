# Plan notes: line targets for per-placement due dates

Exact spots the spec's requirements touch, checked against the code when the spec was reviewed.
Re-read the code before editing; lines drift.

## Query budgets

- `freedom_ls/deadlines/tests/test_resolver.py:399-425`: `django_assert_max_num_queries(5)` for 6
  and 60 items and for 3 records, raised to 6. `:577-581`: 6, raised to 7.
- `freedom_ls/deadlines/tests/test_policy.py:272` (8) does not change. `policy.resolve_for` does not
  call the resolver.
- These are ceilings. Today's fixtures place topics straight in the course, so the part-rows query
  is skipped (an empty `__in`), and the real count is 3 to 5.
- `_defaults_by_course` docstring (`resolver.py:155`) says "Three queries".

## Code spots

- `content_save.py:957-969`: `collections_data` holds courses before parts. `:1059`: item sync
  loop. `:1072-1075`: `children_list` built from `child.overrides`. `:1157-1168`:
  `update_or_create` with `overrides`. `:1176-1182`: unknown-child `ValueError`.
- `resolver.py:185-197`: the crediting loop where a placement value replaces `value`.
- `deadlines/queries.py:18-28`: `content_default_for`. `:31-70`: `layers_beneath`, `canonical_beneath`.
- `deadlines/admin.py:141`: `replaced_value` stamp. `:272-276`: "Content default". `:286-296`:
  "Default has changed".
- `content_engine/admin.py:149-168`: `ContentCollectionItemInline` with `overrides`. `:256`:
  `ContentCollectionItemAdmin`, `:266` its `readonly_fields`.
- `content_base/schema.py:104`: `_one_kind_of_due_date` reads `getattr(self, "file_path", None)`.

## Docs

- `claude_plugins/fls-content/skills/content-types/resources/course-files.md`: the `time_limit_days`
  row `:31`, the `children` row `:32`, "Children ordering" `:69-78`, part table `children` row `:431`.
- `topic-files.md:30-33`, `form-files.md:30`: the "not in the course's `children:` list" lines.
- `.claude/skills/domain-glossary/SKILL.md:30` (`ContentCollectionItem`), `:70` (content default),
  `:71` (the "Never `ContentCollectionItem.overrides`" clause).
- `docs/product/content-editing-workflow.md:112`: the unknown-child rule.
