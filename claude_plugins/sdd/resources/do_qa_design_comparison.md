# QA design comparison

Read this run's screenshot and the design screenshot,
then check every design checklist line as `### Design check` in
`claude_plugins/sdd/commands/implement_plan.md` does (its step 2: elements listed region by region,
the same qualities judged and ignored). Append one record per test and viewport:

```json
{"type": "design", "test_id": "1.2-design", "viewport": "desktop", "design_screenshot": "<repo path>", "screenshot_path": "page-<timestamp>.png", "status": "pass|fail", "misses": ["…"]}
```

- `status` is `pass` when every checklist line is met and `fail` otherwise. Each unmet line is one
  entry in `misses`.
- The design is a visual reference, never a source of scope. A drawn element the checklist does
  not list is not a miss: the build is right to lack it. Never raise a question or todo about
  building something the design draws. Colour, font and icons follow the project's theme.
- The checklist line is the judge, never the drawing. Where the design screenshot draws an element
  one way and the checklist line or another spec document describes it another way, the page is
  right to follow the words (Rule 5): that is a pass.
