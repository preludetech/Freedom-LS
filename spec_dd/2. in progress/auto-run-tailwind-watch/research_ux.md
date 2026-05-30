# UX / Developer-Experience Research: One Combined Dev Command (Django runserver + Tailwind v4 `--watch`)

Goal of this doc: capture the UX and developer-experience best practices, common complaints, and pitfalls-to-avoid when combining Django's `runserver` with the Tailwind v4 CLI in `--watch` mode into a **single dev command/terminal**, given that `django-browser-reload` is already installed and active.

This is design guidance, not an implementation plan. Each section ends with concrete recommendations for *this* command.

---

## 0. Two architectural shapes (frames everything below)

There are two dominant ways the ecosystem solves "one command, two processes". The choice drives almost every UX decision in this doc.

1. **Process-manager / sibling-processes model** — a parent (e.g. `concurrently`, `foreman`, `honcho`, or a custom asyncio launcher) spawns *both* `runserver` and `tailwind --watch` as peers and multiplexes their output. This is what `django-tailwind`'s `tailwind dev` does (writes a `Procfile.tailwind` with `django:` + `tailwind:` lines and runs it under **honcho**, color-coding each process). ([django-tailwind usage](https://django-tailwind.readthedocs.io/en/latest/usage.html))

2. **Watcher-under-Django's-autoreloader model** — a single management command (e.g. `django-tailwind-cli`'s `tailwind runserver`) starts the Tailwind watcher *inside* Django's own auto-reloader and then transparently passes through to `runserver`. "The watcher runs under Django's own auto-reloader, so editing `settings.py` ... restarts it automatically." It is "a transparent passthrough: every positional argument and option (apart from `--force-default-runserver`) is forwarded verbatim to the underlying `runserver`." ([django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli))

The watcher-under-autoreloader model is the more modern / Tailwind-v4-native pattern and sidesteps several pitfalls below (notably the double-start and Windows-honcho problems), at the cost of being more tightly coupled to Django internals. The process-manager model is simpler to reason about and more portable, but you own teardown and the autoreload double-start yourself.

---

## 1. Log & error visibility

The single biggest readability problem: Tailwind's compile output gets buried in Django's per-request log noise (`"GET /static/... 200"` lines scroll the real error off screen).

**What good combined runners do:**

- **Per-process prefixing + color.** `concurrently` prefixes every line so you can tell streams apart. `--prefix` accepts `index | pid | time | command | name | none` or a custom template; `--names "django,tailwind"` plus `--prefix "[{name}]"` yields readable `[django]` / `[tailwind]` labels. `--prefix-colors` (Chalk colors, `auto` for automatic per-process variation) gives each stream its own color. ([concurrently README](https://github.com/open-cli-tools/concurrently/blob/main/README.md), [concurrently npm](https://www.npmjs.com/package/concurrently))
- **honcho/foreman** color-code each Procfile process line automatically for the same reason. ([django-tailwind usage](https://django-tailwind.readthedocs.io/en/latest/usage.html))
- The whole point, per concurrently's docs, is that "each process receives its own color ... allowing clear distinction of which logs belong to which process."

**Interleaving / buffering pitfall (Python-specific, important here):**

- Python aggressively buffers stdout when it is **not** attached to a TTY (which is exactly the case when a parent process manager captures the pipe). Symptom: Tailwind/Django logs arrive late, batched, and **out of order**, so a Tailwind error appears detached from the action that caused it. Fix is to force unbuffered output (`python -u` / `PYTHONUNBUFFERED=1`). This was a real reported foreman+honcho complaint. ([honcho issue #38](https://github.com/nickstenning/honcho/issues/38))

**Making Tailwind COMPILE ERRORS stand out:**

- Tailwind CLI writes build status and errors to **stderr**; ensure stderr is *not* swallowed or merged in a way that hides it. Keep the `[tailwind]` prefix/color on error lines so a red `[tailwind]` block is visually obvious against Django's request log.
- Do not let request-log volume drown it: a Tailwind error should remain the last thing visible after a failed rebuild. Prefixing is what makes this survivable; without prefixes the error is indistinguishable from a Django traceback.

**Recommendations for this command:**
- Prefix and color both streams. Use stable, lowercase labels like `[django]` and `[tailwind]` (or `[css]`).
- Force unbuffered Python output (`PYTHONUNBUFFERED=1`) so logs interleave in real time and errors stay attached to their cause.
- Never redirect Tailwind stderr to `/dev/null` or merge it silently — compile errors are the headline use-case the developer explicitly asked for.
- Tailwind's own `--watch` already prints "Rebuilding..." / "Done in Xms" / error blocks; surface those verbatim, just prefixed.

---

## 2. Ctrl-C / teardown (the #1 complaint)

The single most-reported complaint about combined runners is **orphaned watcher processes**: you Ctrl-C the server, Django dies, but the Tailwind watcher keeps running in the background (and keeps holding the output file / a port), or you have to Ctrl-C twice.

**Evidence from the ecosystem:**

- foreman: "when sending SIGINT to foreman, it kills foreman and direct child shell processes, but application processes ... are left running"; SIGTERM is not reliably forwarded to the child. ([foreman #440](https://github.com/ddollar/foreman/issues/440), [foreman #508](https://github.com/ddollar/foreman/issues/508))
- honcho: its `Process` class can effectively ignore SIGINT/SIGTERM and only exits when its child shell exits, so a wrapping shell can leave grandchildren orphaned. ([honcho process source](https://github.com/nickstenning/honcho/blob/main/honcho/process.py))
- The custom-asyncio approach (Bradley Kirton's script) exists *specifically* to solve this: it installs handlers for `SIGINT` and `SIGTERM`, sets a shutdown event, sends `SIGTERM` to **all** subprocesses, and `await process.wait()`s each one — "Prevents processes from continuing after the parent script exits." ([Bradley Kirton blog](https://bradleykirton.com/2023/06/02/a-script-for-running-django-runserver-and-tailwindcss-watch/))
- Generic Django note: a backgrounded/abandoned `runserver` survives terminal close and must be hunted with `lsof`; avoid creating that situation. ([Adam Johnson](https://adamj.eu/tech/2023/11/19/django-stop-backgrounded-runserver/))

**Why the watcher-under-autoreloader model wins here:** because Tailwind runs *inside* the Django process tree (under the autoreloader), a single Ctrl-C tears down the watcher with Django — there is no second sibling process to orphan. This is the cleanest teardown story.

**Recommendations for this command:**
- Guarantee that **one** Ctrl-C stops **everything**, with no orphan and no need to press it twice.
- If using the sibling-process model: trap SIGINT/SIGTERM in the parent and explicitly signal/`wait()` on every child; consider spawning children in their own process group so the signal reaches grandchildren, not just the immediate shell.
- Prefer running the watcher under Django's autoreloader (or as a managed child you fully own) over shelling out to `concurrently`/`honcho` if cross-platform clean teardown matters.
- Test the failure mode explicitly: Ctrl-C, then `ps`/`lsof` to confirm no stray Tailwind process and no held output file handle.

---

## 3. When one process dies (kill-others vs keep-alive)

Decision: if Tailwind crashes (e.g. bad CSS syntax in v4), should the whole command die, or should Django keep serving?

**Patterns observed:**

- `concurrently` exposes both behaviors: `--kill-others-on-fail` (and the more general `--kill-others-on <success|failure>`). The documented motivation is the surprise factor: "if one process fails, others still keep running and **you won't even notice the difference**." It also offers `--restart-tries` / `--restart-delay` for auto-recovery. ([concurrently README](https://github.com/open-cli-tools/concurrently/blob/main/README.md))
- foreman/honcho default the *other* direction and devs find it surprising: in foreman, "process in Procfile exiting with 0 kills all sibling processes" — i.e. one process ending takes the others down whether you wanted it or not. ([foreman #676](https://github.com/ddollar/foreman/issues/676))

**What is least surprising for a CSS watcher specifically:**

- A Tailwind **compile error** (bad utility / bad CSS) is a *recoverable, expected* event during development. Tailwind's `--watch` does **not** exit on a compile error — it prints the error and keeps watching, rebuilding when you fix it. So the natural, least-surprising behavior is: **Django keeps running, Tailwind keeps watching, the error is shown, and the next save fixes it.** Killing Django because of a CSS typo would be hostile.
- The kill-others behavior is more appropriate for a hard *startup* failure (e.g. the Tailwind binary is missing, or `runserver` can't bind the port) — there it's better to fail loudly and stop everything than to leave a half-working environment.

**Recommendations for this command:**
- Do **not** tear down Django on a Tailwind *compile* error; let the watcher recover. This matches Tailwind's own watch semantics.
- Do fail loudly and stop everything on a *startup/exec* failure (binary missing, port in use, watcher process can't even start) so the dev isn't fooled by a half-up environment.
- Whatever you choose, make a dying child **loud** — a silently-dead watcher that leaves stale CSS is the worst outcome.

---

## 4. Interaction with browser live-reload (`django-browser-reload`)

The intended loop is the standard one: **edit template → Tailwind rebuilds `output.css` → `django-browser-reload` detects the changed static file → browser refreshes.** `django-browser-reload` watches templates and static files and reloads the browser when they change; pairing it with a Tailwind watcher is the documented standard "edit → CSS rebuilds → browser refreshes" workflow. ([django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli), [Django Cookiecutter: Tailwind & Browser Reload](https://django-cookiecutter.readthedocs.io/en/latest/how-tos/how-to-tailwind.html))

**Ordering / race issues people report:**

- The dependency chain has two hops (Tailwind writes the file, *then* the reloader notices it). If the browser reload fires before Tailwind has finished writing `output.css`, you get a refresh that shows **stale CSS**, and you have to save again. This race is more likely on large rebuilds or slow disks. (General class of problem flagged in watcher pipelines, e.g. [Tailwind #4023](https://github.com/tailwindlabs/tailwindcss/issues/4023).)
- Mitigation that works in practice: let `django-browser-reload` watch the **built `output.css`** (the file Tailwind produces) rather than racing on the source. When the reload trigger is the *output* of the build, the build is by definition already complete, so the browser reloads correct CSS. Make sure the Tailwind output file lives in a watched static directory.
- A separate annoyance: editing a template can trigger **two** reloads — one because the template changed, and another moments later because Tailwind rewrote `output.css`. Watching the built output (and not double-registering the source) keeps it to a single, correct refresh.

**Recommendations for this command:**
- Ensure Tailwind's `output.css` is written into a directory that `django-browser-reload` watches, so the browser refresh is driven by build *completion*, not build *start*.
- Accept that this is the canonical combo and lean into it; just be aware of and document the stale-CSS-on-first-save race so it isn't mistaken for a bug.
- No extra reload tooling is needed — `django-browser-reload` already does the browser half; this command only needs to own the CSS-rebuild half cleanly.

---

## 5. Discoverability & not breaking existing flows

**The core motivation (why this command exists at all):** onboarding pain. As the django-tailwind feature request put it: "The current approach would require us to teach every developer on our team to always start the tailwind watcher as well." Forgetting to start the watcher → "why is my CSS not updating?" is the classic new-dev trap. ([timonweb/django-tailwind #198](https://github.com/timonweb/django-tailwind/issues/198))

**Naming & convention from the ecosystem:**

- `django-tailwind` uses `tailwind dev` (process-manager style) and keeps `tailwind start` (watch only) + plain `runserver` available separately. ([django-tailwind usage](https://django-tailwind.readthedocs.io/en/latest/usage.html))
- `django-tailwind-cli` uses `tailwind runserver` and is a **transparent passthrough** of all `runserver` args/options, and still keeps `tailwind watch` + `runserver` available individually. ([django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli))
- Both keep the separate building blocks; neither removes plain `runserver`.

**Default vs opt-in:**

- The strong argument for making the combined command the **discoverable, recommended** one is exactly the onboarding point above — devs shouldn't have to remember a second terminal.
- The argument against *replacing* `runserver` outright: some workflows (CI, debugging, profiling, running under a debugger, Windows where honcho doesn't work) want plain `runserver` with no watcher. `django-tailwind`'s honcho mode is explicitly noted as "doesn't work on Windows," which is a concrete reason not to make a process-manager-based combined command the *only* path. ([django-tailwind usage](https://django-tailwind.readthedocs.io/en/latest/usage.html))

**Recommendations for this command:**
- Add a clearly-named combined command rather than silently overloading `runserver`. A transparent-passthrough wrapper (forwarding all `runserver` args/flags, e.g. host:port, `--noreload`) is the least-surprising design — devs keep their existing muscle memory.
- **Keep the building blocks available**: plain `runserver` and a standalone Tailwind `watch`/`build` must still work for CI, production builds, debugging, and any environment where the combined runner is unsuitable.
- Make the combined command the **documented default for local dev** (README "to start developing, run X") so new devs fall into the pit of success, while leaving `runserver` as the explicit escape hatch.
- Document the one-liner prominently; the whole value proposition is "no one has to remember the second terminal."

---

## 6. Other common complaints / pitfalls (startup ordering, double-start, first-run race)

- **Autoreloader double-start (Django-specific, must handle).** `runserver` runs your code **twice**: once in the outer reloader process and once in the spawned child. Django sets `RUN_MAIN=true` in the child. If a naive combined command spawns the Tailwind watcher on *both*, you get **two watchers** fighting over `output.css` (duplicate rebuilds, doubled logs, possible file-write churn). Guard watcher startup with `os.environ.get("RUN_MAIN") == "true"` (or run with `--noreload`). The watcher-under-autoreloader model (django-tailwind-cli) is built to avoid exactly this. ([Django #14606](https://code.djangoproject.com/ticket/14606), [Chase Seibert: subclassing runserver runs twice](https://chase-seibert.github.io/blog/2013/10/24/django-subclass-runserver.html))
- **First-run race (page loads before CSS is built).** On the very first start, `runserver` is ready in milliseconds but Tailwind's initial full build takes longer; if you open the page immediately it loads **unstyled** until the first build lands. Least-surprising fix: run a **one-shot Tailwind build before/at startup** (or at least print a clear "building initial CSS..." line) so a missing/empty `output.css` doesn't render a broken-looking page. Also relevant for a clean repo where `output.css` doesn't exist yet.
- **Startup ordering in general.** Launch both promptly (in parallel) rather than gating Django on the watcher — Bradley Kirton's script uses `asyncio.gather(...)` precisely to start them together and avoid ordering delays. But pair that with the first-run build above so "started in parallel" doesn't mean "served unstyled." ([Bradley Kirton blog](https://bradleykirton.com/2023/06/02/a-script-for-running-django-runserver-and-tailwindcss-watch/))
- **Stale CSS after a crash.** If the watcher dies silently mid-session, `output.css` freezes and the dev edits classes with no effect — extremely confusing. Reinforces §2/§3: a dead watcher must be loud.
- **Output buffering making logs lag** — see §1; force unbuffered output.
- **Windows / honcho portability** — process-manager-based combined commands have a documented Windows gap; the in-process watcher model is more portable. ([django-tailwind usage](https://django-tailwind.readthedocs.io/en/latest/usage.html))

---

## TL;DR design checklist for this command

1. Prefix + color both streams (`[django]` / `[tailwind]`); force `PYTHONUNBUFFERED=1`; never swallow Tailwind stderr.
2. One Ctrl-C kills everything, no orphans, no double-press — own teardown explicitly or run the watcher inside Django's process tree.
3. Tailwind compile error → Django keeps running, watcher recovers (matches Tailwind `--watch`). Hard startup failure → stop loudly.
4. Drive `django-browser-reload` off the **built** `output.css` so the refresh waits for build completion (avoids stale-CSS race); this is the standard edit→rebuild→refresh loop.
5. New, intuitively-named passthrough command; keep plain `runserver` and standalone watch/build; make the combined command the documented local-dev default, not a forced replacement.
6. Guard watcher startup against the autoreloader double-start (`RUN_MAIN`); do a one-shot initial build so the first page load isn't unstyled.

---

## References

- concurrently README — https://github.com/open-cli-tools/concurrently/blob/main/README.md
- concurrently (npm) — https://www.npmjs.com/package/concurrently
- django-tailwind-cli (`tailwind runserver`, watcher under autoreloader, Tailwind v4) — https://github.com/django-commons/django-tailwind-cli
- Django-Tailwind usage (`tailwind dev`, honcho Procfile, color-coded, Ctrl-C, Windows gap) — https://django-tailwind.readthedocs.io/en/latest/usage.html
- timonweb/django-tailwind issue #198 (motivation: don't make every dev remember the watcher) — https://github.com/timonweb/django-tailwind/issues/198
- Bradley Kirton — asyncio script running runserver + Tailwind watch with SIGINT/SIGTERM teardown — https://bradleykirton.com/2023/06/02/a-script-for-running-django-runserver-and-tailwindcss-watch/
- Adam Johnson — stopping a backgrounded/orphaned runserver with lsof — https://adamj.eu/tech/2023/11/19/django-stop-backgrounded-runserver/
- honcho issue #38 — stdout buffering causing delayed/out-of-order logs (use `python -u`) — https://github.com/nickstenning/honcho/issues/38
- honcho process source — signal handling behavior — https://github.com/nickstenning/honcho/blob/main/honcho/process.py
- foreman issue #440 — SIGTERM not forwarded to child — https://github.com/ddollar/foreman/issues/440
- foreman issue #508 — orphaned processes after SIGINT — https://github.com/ddollar/foreman/issues/508
- foreman issue #676 — one process exiting kills siblings (surprising) — https://github.com/ddollar/foreman/issues/676
- Django ticket #14606 — module imported twice under the dev-server autoreloader — https://code.djangoproject.com/ticket/14606
- Chase Seibert — subclassing runserver causes command to run twice (RUN_MAIN) — https://chase-seibert.github.io/blog/2013/10/24/django-subclass-runserver.html
- Tailwind issue #4023 — watcher/recompile race in a build pipeline — https://github.com/tailwindlabs/tailwindcss/issues/4023
- Django Cookiecutter — Tailwind & Browser Reload how-to (standard edit→rebuild→refresh combo) — https://django-cookiecutter.readthedocs.io/en/latest/how-tos/how-to-tailwind.html
