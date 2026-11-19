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

`@source` paths resolve relative to the CSS file that contains them.

The probe files were deleted after the run.
