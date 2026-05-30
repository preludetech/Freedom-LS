# One command to run the dev server + Tailwind watch

## Problem

During development we have to run two things in two separate terminals:

- `uv run python manage.py runserver`
- `npm run tailwind_watch`

It's easy to forget the second one, which leads to the classic "why isn't my CSS
updating?" confusion (especially for new devs onboarding). We want **one command**
that starts both, and we need Tailwind's build logs **and errors** to be clearly
visible in the console.

## Chosen approach

Use **`honcho`** (a Python/Foreman-style process runner) driven by a **`Procfile.dev`**.
Honcho runs `runserver` and the Tailwind watcher as two sibling processes, multiplexes
their output into one console with a per-process label, and tears both down on a single
`Ctrl-C`.

```procfile
# Procfile.dev
django: uv run python manage.py runserver
tailwind: npm run tailwind_watch
```

```
uv run honcho -f Procfile.dev start
```

Why honcho (vs. a custom `manage.py` command or the npm `concurrently` tool):

- It keeps the launcher Python/`uv`-centric, matching the rest of the toolchain.
- It runs Tailwind as a **sibling** of `runserver` rather than inside it, which sidesteps
  Django's autoreloader "runs everything twice" trap — there is only ever **one** Tailwind
  watcher no matter how often Django reloads, and no orphaned watcher on exit. A custom
  management command is the only option exposed to that trap.
- It reuses the **existing** `tailwind_watch` npm script unchanged, so the required
  `_write_active_theme` prestep (which must run before Tailwind) stays handled in one place.
- A `Procfile.dev` cleanly scales to future dev processes (e.g. a worker) later.
- It's the same model the canonical `django-tailwind` package uses for its own combined command.

## What we want (high level)

- **One documented command** to start local development that runs both processes.
- **Keep the existing commands working separately** — plain `runserver`, `npm run tailwind_watch`,
  and `npm run tailwind_build` must all still work (needed for CI, production builds, debugging,
  and any environment where the combined runner isn't wanted). The combined command is additive,
  not a replacement for `runserver`.
- **Readable, labelled logs.** Each process's output is prefixed/coloured (e.g. `django |` /
  `tailwind |`) so Tailwind compile errors don't get lost in Django's request-log noise.
- **Tailwind errors stay visible.** Tailwind's `--watch` prints compile errors to the console and
  keeps watching; a CSS typo must not silently break the loop or get swallowed.
- **Clean teardown.** A single `Ctrl-C` stops both processes with no leftover/orphaned Tailwind
  watcher holding the output file open.
- **A Tailwind compile error should not kill the dev server.** Tailwind keeps watching and recovers
  on the next save; Django keeps serving. (A hard startup failure — missing binary, port in use —
  should still fail loudly.)
- **Make it the documented default for local dev** in the README, with the separate commands noted
  as the escape hatch.

## Design considerations to resolve in the spec

- **Port / tenant selection.** This is a multi-tenant app where the dev picks a tenant by choosing
  the `runserver` port (`runserver 8001`). A static `Procfile.dev` bakes in port 8000. We need a way
  to pass a port through (e.g. an env var read in the Procfile line, or a documented second
  invocation) without losing the one-command convenience. Default to 8000 when none is given.
- **First-run / empty CSS.** On a fresh checkout `static/vendor/tailwind.output.css` may not exist
  yet, and the page can load unstyled before Tailwind's first build completes. Consider ensuring an
  initial build has run (the existing `tailwind_watch` does a build before watching) so the first
  page load isn't unstyled.
- **Browser refresh is already solved.** `django-browser-reload` is already installed and active, so
  the "edit → CSS rebuilds → browser refreshes" loop already works once both processes are running —
  no extra reload tooling is needed here.

## Out of scope

- Replacing or changing the behaviour of plain `runserver`.
- Anything to do with production builds/deploys (covered by `tailwind_build` in CI).
- Browser live-reload (already handled by `django-browser-reload`).

## Research

See `research_approaches.md` (approach comparison + the autoreloader gotcha) and
`research_ux.md` (log visibility, teardown, error handling, discoverability) in this directory.
