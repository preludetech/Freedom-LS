# Research: One command to run Django `runserver` + Tailwind v4 CLI `--watch`

## Goal

A single dev command that runs both `runserver` and the Tailwind v4 standalone CLI in
`--watch` mode, with Tailwind build logs **and** errors clearly visible in the console.

## This project's exact setup (the constraints that matter)

- Django 6.x, Python 3.13, managed with `uv` (e.g. `uv run python manage.py runserver`).
- TailwindCSS **v4** via the standalone CLI (`@tailwindcss/cli`), driven by npm scripts in
  `package.json`:
  - `tailwind_watch`: `npm run _write_active_theme && npx @tailwindcss/cli -i ./tailwind.input.css -o ./static/vendor/tailwind.output.css --watch`
  - `tailwind_build`: same, no `--watch`
  - `_write_active_theme`: `uv run manage.py write_active_theme_css` — **must run before Tailwind**
    to generate a theme CSS file that Tailwind then consumes.
- They do **not** use the `django-tailwind` pip package; they call `@tailwindcss/cli` directly.
- `django-browser-reload` is installed and active (middleware in `config/settings_dev.py`,
  `__reload__/` urls in `config/urls.py`). So browser refresh on file change is already solved;
  this research is only about *running the two processes together*.
- `django-watchfiles` is installed but commented out in `config/settings_dev.py` (line 38).
- Multi-tenant: a dev picks a tenant by choosing the `runserver` port (e.g. `runserver 8001`).
  Whatever we build must let the dev pass a port through to `runserver`.
- Platform: Linux, zsh.

Two important consequences of the setup:

1. **There is a required prestep.** `_write_active_theme` (a `uv`/Django management command)
   must run *once, before* Tailwind starts watching. Any solution has to sequence this.
2. **The port is a runtime argument.** The command must forward an arbitrary port to runserver.

---

## The critical gotcha: Django's autoreloader runs the program twice

`runserver` (with the default StatReloader / watchman / watchfiles reloader) starts **two
processes**:

- a **parent "watcher"** process that just monitors files and restarts the child, and
- a **child** process that actually serves requests. The child is launched by re-executing the
  same command line with the env var `RUN_MAIN=true` (historically also
  `DJANGO_AUTORELOAD_ENV`). On every code change the child is killed and respawned.

This is fine for plain `runserver`. It becomes a trap **only for approach #3** (a custom
management command that spawns Tailwind itself), because:

- If the command spawns Tailwind in *both* the parent and the child, you get **two Tailwind
  watchers**. Worse, every autoreload respawn of the child would spawn **another** Tailwind
  watcher → process leak, doubled rebuilds, garbled interleaved logs.
- On `Ctrl-C`, the parent receives SIGINT but a naively-spawned Tailwind subprocess (especially
  one launched from the child, or in its own session) can be **orphaned** and keep running,
  holding the output file open.

### How to handle it inside a custom command

- **Spawn Tailwind exactly once** by gating on the reloader child:
  ```python
  import os
  if os.environ.get("RUN_MAIN") != "true":
      # we are the parent watcher process → spawn Tailwind here, once
      ...
  ```
  Spawning in the **parent** is the usual choice: the parent lives for the whole session, while
  the child is repeatedly killed/respawned on every reload. (Conversely, if you wanted Tailwind
  tied to the child you'd gate on `RUN_MAIN == "true"` — but then it dies/respawns on every
  reload, which is wasteful. Parent-gating is preferred.)
- **Guarantee cleanup of the Tailwind process** so it doesn't orphan on exit:
  - Launch it in its **own process group/session** with `subprocess.Popen(..., start_new_session=True)`
    (the modern, thread-safe replacement for `preexec_fn=os.setsid`; `preexec_fn` carries an
    explicit thread-safety warning in the CPython docs and Django's reloader is multi-threaded).
  - On shutdown send the signal to the whole group:
    `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)`.
  - Register cleanup via `atexit` **and** a SIGINT/SIGTERM handler. Caveat: `atexit` does **not**
    run on a hard crash or `SIGKILL`, so signal handling is the more reliable path; treat
    `atexit` as a best-effort backstop.
  - `--noreload` is a tradeoff: it makes the command single-process (no parent/child, so the
    `RUN_MAIN` dance disappears and there is exactly one place to manage Tailwind), but you lose
    Python autoreload entirely — a real regression for daily dev. Not recommended as the default.

### Do the sibling approaches sidestep this? — Yes

Approaches **#1 (Node concurrently/npm-run-all)**, **#2 (honcho/Procfile)**, and **#5 (shell
script)** all run Tailwind as a **sibling process next to `runserver`**, not *inside* it. The
process manager launches `runserver` as one child and `npx @tailwindcss/cli --watch` as another.
The `RUN_MAIN` parent/child fork happens **entirely inside** the `runserver` child and is
invisible to the manager — the manager sees a single `runserver` process and a single Tailwind
process. So there is exactly **one** Tailwind watcher regardless of how many times Django
autoreloads, and Tailwind is unaffected by Django code reloads. This is the single biggest
reason to prefer a sibling-process approach over a custom command. (Orphan-on-exit still needs a
manager that kills its children properly — see each option below.)

---

## Approach 1 — Node concurrent runners (`concurrently` or `npm-run-all`/`run-p`)

### How it works
Add a dev npm script that launches both processes side by side, e.g. with `concurrently`:

```jsonc
"scripts": {
  "_write_active_theme": "uv run manage.py write_active_theme_css",
  "tailwind_watch": "npm run _write_active_theme && npx @tailwindcss/cli -i ./tailwind.input.css -o ./static/vendor/tailwind.output.css --watch",
  "dev": "concurrently --kill-others --names \"django,tw\" --prefix-colors \"green,magenta\" \"uv run python manage.py runserver\" \"npm run tailwind_watch\""
}
```

Run with `npm run dev`. The existing `tailwind_watch` script already chains `_write_active_theme`
*before* the CLI via `&&`, so the prestep is handled per-process — no extra wiring needed.

For port selection, either bake it into the script or pass through:
`npm run dev -- ...` is awkward for two commands, so a common pattern is a second script
(`dev:8001`) or using an env var read inside the runserver command.

`npm-run-all`'s `run-p` is the equivalent ("run in parallel"); it has fewer log/labeling
features than `concurrently` and the package is effectively unmaintained, so `concurrently`
is the better pick of the two.

### Output / logs / errors
`concurrently` **prefixes and colors** each line by process (`--names`, `--prefix-colors`, with
`--prefix` templates: `index|pid|time|command|name|none`). Tailwind v4 prints rebuild messages
and compile **errors** to its stdout/stderr, which `concurrently` passes through prefixed — so
errors stay visible. `--raw` exists if you want unprefixed passthrough.

### Kill / exit behavior
- By default `concurrently` keeps the others running when one exits.
- `--kill-others` kills the rest when **any** process exits; `--kill-others-on-fail` only kills
  when one exits **non-zero**. For a dev runner, `--kill-others` is usually what you want so
  Tailwind dies with Django.
- On `Ctrl-C`, `concurrently` forwards the interrupt and shuts down its children; it manages the
  child lifecycle, so no orphaned Tailwind watcher (the failure mode of approach #3).
- `--success first|last|all|command-<name>` controls the overall exit code.

### Fit for this stack
**Strong.** Tailwind is already npm-driven, so this lives naturally in `package.json`, reuses
the existing `tailwind_watch` (prestep included), and completely **sidesteps the `RUN_MAIN`
gotcha** (Tailwind is a sibling, immune to Django reloads). Cons: adds a Node dev dependency;
the "primary" entry point becomes `npm run dev` rather than a Django command (a small mental
shift in a uv/Django-centric project); passing an arbitrary port is slightly clunky.

---

## Approach 2 — `honcho` (Python Foreman clone) + `Procfile.dev`

### How it works
`honcho` is a Python port of Foreman that runs a `Procfile`. Add it as a dev dependency
(`uv add --dev honcho`), create `Procfile.dev`:

```procfile
django: uv run python manage.py runserver
tailwind: npm run tailwind_watch
```

Run `uv run honcho -f Procfile.dev start`. Each line is `name: command`; both start
concurrently. (The existing `tailwind_watch` again handles the `_write_active_theme` prestep via
`&&`.)

### Output / logs / errors
honcho **prefixes each line with the process name** (e.g. `tailwind | ...`), interleaving both
streams in one console. Tailwind build logs and errors appear under the `tailwind` prefix.
Coloring per process is supported. Less configurable than `concurrently` but perfectly readable.

### Kill / exit behavior
`Ctrl-C` stops all processes in the Procfile together. honcho manages the child processes, so
Tailwind is not orphaned. As a sibling-process manager it **sidesteps the `RUN_MAIN` gotcha**
just like `concurrently`.

### Fit for this stack
**Strong, and arguably the most "on-brand" for a uv/Python shop** — the launcher is Python and
runs under `uv`, keeping the toolchain Python-centric instead of pushing the entry point into
Node. A `Procfile.dev` is also reusable for adding future processes (e.g. a worker). Cons:
historically flaky on Windows (irrelevant here — Linux only); extra Python dev dependency; port
selection has the same "needs a second Procfile or env var" awkwardness. Note: this is exactly
the model `django-tailwind`'s own `tailwind dev` command uses under the hood (honcho +
`Procfile.tailwind`).

---

## Approach 3 — Custom Django management command spawning Tailwind via `subprocess.Popen`

### How it works
A command (e.g. `manage.py dev` or a `runserver` subclass) that spawns the Tailwind CLI with
`subprocess.Popen`, then calls runserver. Entry point stays a Django/uv command:
`uv run python manage.py dev 8001`.

Minimal sketch incorporating the gotcha fixes:

```python
import atexit, os, signal, subprocess
from django.core.management.commands.runserver import Command as RunserverCommand

class Command(RunserverCommand):
    def handle(self, *args, **options):
        if os.environ.get("RUN_MAIN") != "true":  # parent watcher only → spawn once
            # _write_active_theme prestep must run before Tailwind:
            subprocess.run(["uv", "run", "manage.py", "write_active_theme_css"], check=True)
            tw = subprocess.Popen(
                ["npx", "@tailwindcss/cli", "-i", "./tailwind.input.css",
                 "-o", "./static/vendor/tailwind.output.css", "--watch"],
                start_new_session=True,  # own process group for clean group-kill
            )
            def _cleanup() -> None:
                try:
                    os.killpg(os.getpgid(tw.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            atexit.register(_cleanup)
            signal.signal(signal.SIGINT, lambda *_: (_cleanup(), os._exit(0)))
        super().handle(*args, **options)
```

### Output / logs / errors
Tailwind's stdout/stderr inherit the console, so its logs/errors are visible — but **interleaved
with Django's, unprefixed**, so it can be harder to tell which process emitted a line compared
to `concurrently`/honcho. You'd have to add your own prefixing to match them.

### Kill / exit behavior
Entirely your responsibility, and this is where it gets fragile — see the gotcha section. You
must gate on `RUN_MAIN`, use `start_new_session=True` + `os.killpg`, and handle SIGINT/SIGTERM
plus `atexit`. The prestep must be sequenced explicitly. Easy to get subtly wrong (orphaned
watcher, doubled rebuilds).

### Fit for this stack
**Workable but the highest-effort and most error-prone option, and the only one exposed to the
`RUN_MAIN` gotcha.** Its one real advantage is ergonomics: the entry point stays a single Django
command with native port-as-argument support (`manage.py dev 8001`), matching how the team
already thinks (port = tenant). If a Django-native entry point is a hard requirement, this is the
way — but it must be implemented carefully per the gotcha section, and it needs `npx`/Node
present in the same environment as `uv`. Not recommended unless the single-command-Django-native
UX is explicitly valued over implementation simplicity.

---

## Approach 4 — `django-tailwind`'s `tailwind dev` command (reference only)

### How it works
The `django-tailwind` pip package ships a `python manage.py tailwind dev` command that, on first
run, generates a `Procfile.tailwind` with two lines (`python manage.py runserver` and
`python manage.py tailwind start`) and then **runs them via honcho**. `tailwind start` is the
watcher; `tailwind dev` is the combined runner. It relies on `django-browser-reload` for the
browser refresh.

### Why it doesn't apply here
This project deliberately does **not** use `django-tailwind` — it calls `@tailwindcss/cli`
directly and has a custom `_write_active_theme` prestep that `django-tailwind` knows nothing
about. Adopting `django-tailwind` would mean restructuring the whole Tailwind integration around
that package's conventions. **Not a fit.** The useful takeaway is purely architectural: even the
canonical Django+Tailwind package implements "one command" as **honcho + a Procfile**, i.e. the
sibling-process model of approach #2 — validating that approach as best practice.

---

## Approach 5 — Plain shell script wrapper

### How it works
A `bin/dev` script (zsh/bash) that runs the prestep, backgrounds Tailwind, runs runserver in the
foreground, and traps signals to clean up:

```bash
#!/usr/bin/env bash
set -euo pipefail
uv run manage.py write_active_theme_css
npx @tailwindcss/cli -i ./tailwind.input.css -o ./static/vendor/tailwind.output.css --watch &
TW_PID=$!
trap 'kill "$TW_PID" 2>/dev/null' EXIT INT TERM
uv run python manage.py runserver "${1:-8000}"
```

Run `./bin/dev 8001`.

### Output / logs / errors
Both streams go to the same console, **unprefixed/uncolored** (like approach #3). Tailwind errors
are visible but not labeled.

### Kill / exit behavior
Manual: a `trap ... EXIT INT TERM` that kills the backgrounded Tailwind PID. Reasonably robust on
Linux if written carefully, but signal/job-control edge cases (e.g. killing the whole job tree)
are fiddly, and it's another file/format to maintain outside the Python/Node toolchains.
Sibling-process model, so it **sidesteps the `RUN_MAIN` gotcha**.

### Fit for this stack
**Acceptable fallback.** Zero new dependencies and trivial port passthrough (`$1`). But it
duplicates logic that already exists in `package.json`, gives the worst log labeling of the
sibling approaches, and is the least cross-developer-friendly (shell quirks, not discoverable via
`npm run`/`manage.py`). Prefer `concurrently` or honcho over this unless avoiding any new
dependency is a hard rule.

---

## Recommendation (ranked for THIS stack)

Weighing **simplicity**, **log/error visibility**, and the **autoreload gotcha**:

1. **honcho + `Procfile.dev`** — *Recommended.* Keeps the launcher Python/uv-centric (fits a uv +
   Django shop), prefixes output per process for clear log/error visibility, cleans up children
   on `Ctrl-C`, reuses the existing `tailwind_watch` script (so the `_write_active_theme` prestep
   is already handled), and **sidesteps the `RUN_MAIN` gotcha** entirely. It's also the model the
   canonical `django-tailwind` package itself uses, and the `Procfile.dev` scales to future
   processes. One new dev dependency.

2. **`concurrently` (npm) `dev` script** — *Equally strong; pick this if you'd rather keep the
   runner in Node/`package.json`.* Best-in-class prefixing/coloring, `--kill-others` for clean
   shutdown, sibling-process model so no `RUN_MAIN` gotcha. Slight downsides vs honcho: entry
   point shifts to `npm run dev` (less natural in a uv/Django project) and arbitrary-port
   passthrough is a bit clunkier.

   *Tie-breaker:* choose **honcho** if the team thinks "Django/uv first" and wants port-as-tenant
   ergonomics close to manage.py; choose **concurrently** if the team is happy living in
   `package.json` and wants the richest console formatting.

3. **Plain shell script** — Fine fallback with zero new deps and trivial port passthrough, but
   worst log labeling and least discoverable/portable. Use only if adding a dependency is
   disallowed.

4. **Custom management command (`Popen`)** — Only if a single Django-native command with native
   port arg is a hard requirement. It is the **only** option exposed to the `RUN_MAIN` /
   orphaned-process gotcha and needs careful, correct implementation (`RUN_MAIN` gate,
   `start_new_session=True`, `os.killpg`, signal + `atexit` cleanup, explicit prestep sequencing).
   Highest effort, highest risk.

5. **`django-tailwind`'s `tailwind dev`** — Not applicable; the project doesn't use the package
   and has a custom prestep. Reference only.

**Bottom line:** prefer a **sibling-process runner (honcho #1 or concurrently #2)**. Both dodge
the autoreloader trap by design and give clearly labeled Tailwind logs/errors. Reserve the custom
management command for the case where a Django-native single command is non-negotiable, and
implement it strictly per the gotcha section.

---

## References

- Django ticket #8085 — `runserver` in a management command executes twice (autoreload): https://code.djangoproject.com/ticket/8085
- Django-Tailwind usage docs — `tailwind dev` uses honcho + `Procfile.tailwind`: https://django-tailwind.readthedocs.io/en/latest/usage.html
- Django-Tailwind usage (4.1.0) — Procfile process format: https://django-tailwind.readthedocs.io/en/4.1.0/usage.html
- `concurrently` on npm — `--kill-others`/`--kill-others-on-fail`, `--names`, `--prefix-colors`, `--prefix`, `--success`, `--raw`, exit/signal behavior: https://www.npmjs.com/package/concurrently
- `concurrently` GitHub (open-cli-tools): https://github.com/open-cli-tools/concurrently
- honcho GitHub (Python Foreman clone): https://github.com/nickstenning/honcho
- honcho docs — managing Procfile-based apps & using Procfiles: https://honcho.readthedocs.io/ and https://honcho.readthedocs.io/en/latest/using_procfiles.html
- "Consolidating your dev processes with honcho" — prefixed output, Procfile.dev with Django: https://mitchel.me/2016/consolidating-your-dev-processes-with-honcho/
- TimOnWeb — running multiple Django dev processes with honcho: https://timonweb.com/django/django-dev-made-easy-how-to-run-multiple-processes-simultaneously/
- Python subprocess process-group termination (`start_new_session`, `os.killpg`, `preexec_fn` thread-safety, `atexit` limits): https://alexandra-zaharia.github.io/posts/kill-subprocess-and-its-children-on-timeout-python/ and https://bugs.python.org/issue5115
- SaaS Hammer — integrating Tailwind CSS v4 into Django (standalone CLI + watch): https://saashammer.com/blog/how-to-integrate-tailwindcss-4-into-your-django-project/
