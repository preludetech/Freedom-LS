# Tailwind `@source` into a gitignored directory: probe

Run on 2026-11-19 against the worktree's installed `tailwindcss` 4.1.16 CLI (`node_modules/.bin/tailwindcss`).

| Input CSS (at the repo root) | Result |
| --- | --- |
| `@source not-ignored "./.sdd-work/twtest_pkg";` | Build fails: ``Error: `@source` paths must be quoted.`` The `not-ignored` keyword does not exist in 4.1.16. |
| `@source "./.sdd-work/twtest_pkg";` (`.sdd-work/` is in `.gitignore`) | The arbitrary class in the probe file is generated. |
| `@source "./.venv/lib/python3.x/site-packages/claude_tw_probe/templates";` (`.venv` is in `.gitignore`) | Generated. |
| `@source "./.venv/lib/python3.x/site-packages/claude_tw_probe/templates/**/*.html";` | Generated. |

Conclusion: in Tailwind 4.1.16 an explicit `@source` path is scanned even when `.gitignore` covers it.
Only automatic source detection honours `.gitignore`. A plain `@source "<path>"` is what the generated
file writes. The `@source not-ignored:` spelling in the idea and in
`spec_dd/1. next/extract_panels_framework-5-package-and-install/research_uv_sources_and_consumers.md` breaks the build.

The `.venv` rows ran with uv's nested `.venv/.gitignore` (contents `*`) in place, the case a
Tailwind issue reported as blocking `@source`.

A second probe, from the repo root: `@source "./freedom_ls/**/templates/**/*.html";` followed by
`@source not "./freedom_ls/panel_framework";` builds cleanly and drops the classes used only in framework
templates (`animate-pulse`, `border-b-2`, `border-transparent`, `col-start-2` and others), 79 KB of
output against 92 KB without the exclusion. So `@source not` on a directory works.

A third probe added a positive `@source` of `freedom_ls/panel_framework/templates` after that
exclusion, once relative and once absolute. Both builds came out identical to the excluded one
(79 KB, no `animate-pulse`, no `col-start-2`). **A negated `@source` wins over any positive
`@source` inside the same directory, regardless of order or path form.** FLS therefore cannot
exclude the framework from its glob and re-add it through the generated file. Proving the generated
file's coverage needs a separate build whose input has `source(none)` and only the generated file.

`@source` paths resolve relative to the CSS file that contains them.

The probe files were deleted after the run.
