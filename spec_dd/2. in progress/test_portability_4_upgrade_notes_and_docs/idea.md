# Conformance upgrade-notes & plugin-doc tie-ins

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It bundles
**Layer 5** (the `upgrade_notes.md` tie-in) and the **Part-2 portion of Layer 6**
(plugin-doc touches) — the "make the new conventions stick" documentation work
that surrounds the conformance suite and system checks.

The full motivation and rationale live in the referenced source files below — not
duplicated here.

> **Revised 2026-08-23 (a).** Two corrections after later specs landed:
> `split-claude-plugin` (done 2026-07-28) moved every `fls-claude-plugin/…` file
> to `claude_plugins/fls-dev/…`, and one task in `2. plan.md` belonged to the
> Layer-0 slice rather than here. Paths updated and that task removed; see
> `1. spec.md` and `2. plan.md`.
>
> **Revised 2026-08-23 (b) — after `/sdd:improve_idea` research.** Five research
> files in this directory (`research_*.md`) checked this idea's assertions against
> the shipped tree. Three of them did not survive contact. The scope of the slice
> is unchanged — still exactly two file edits — but **what those edits should say
> has changed materially**. See § "Research corrections" below. The spec and plan
> in this directory still carry the pre-research wording and need updating to match.
>
> **Revised 2026-08-23 (c) — after a cross-slice consistency review.** `1. spec.md`
> and `2. plan.md` have since been revised twice more (their notes (c) and (d)),
> and this file had drifted behind them on four points; all four are corrected
> below. Two new facts also landed from outside the track and **grow the scope**
> from two file edits to five:
>
> 1. **The documented downstream marker selection changed under us.**
>    `basic_reports` (shipped 2026-08-21) added a fifth marker, `weasyprint`, and
>    published the corrected selection
>    `-m "not playwright and not fls_internal and not ci_only and not weasyprint"`.
>    Only `claude_plugins/fls-dev/skills/testing/SKILL.md` was updated;
>    `commands/concrete/update_fls.md` (all four call sites),
>    `resources/testing.md`, `resources/playwright-testing.md` and
>    `skills/playwright-tests/SKILL.md` still carry the four-marker form. A
>    downstream following `update_fls.md` therefore collects FLS's WeasyPrint
>    tests, which need Pango/cairo and an unregistered marker that
>    `--strict-markers` turns into a hard collection error. The "leave Part 1's
>    pytest lines alone" instruction below is **withdrawn**: this slice fixes the
>    selection string in all four files.
> 2. **This slice owns the track's close-out.**
>    `2. in progress/fls-test-portability-part-2/SUPERSEDED.md` says the umbrella
>    may be archived only once this slice lands, with its cross-references
>    rewritten in the same commit. Its own layer→slice table was stale on two
>    rows and has been corrected.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/SUPERSEDED.md` — the authoritative
  layer→slice map, and the instruction that this slice closes the track out.
- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea
  (§ "Layer 5", § "Layer 6 (Part-2 portion)").
- `2. in progress/fls-test-portability-part-2/1. spec.md` — **§ "Layer 5"**,
  **§ "Layer 6"**, and decision **D6**.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 5"** and
  **§ "Layer 6"** for the exact command/doc edits.
- Research (parent effort):
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`
- Research (this slice — supersedes the above where they conflict):
  - `research_upgrade_notes_command.md`
  - `research_update_fls_verification.md`
  - `research_conformance_suite_surface.md`
  - `research_system_checks_inventory.md`
  - `research_command_authoring_conventions.md`

## Research corrections

Five things this idea previously asserted are wrong or misleading. Each is
carried into the scope below.

1. **"Invoke the conformance suite" is redundant as originally scoped.** None of
   the four probe modules under `freedom_ls/contrib/conformance/` carries a
   `playwright`, `fls_internal`, or `ci_only` marker, and no `conftest.py` applies
   one after the fact. The marker selection `update_fls.md` **already** runs at
   four call sites therefore already collects every probe. The real gap is
   **opt-in**: the suite is an importable module, so a downstream only gets the
   signal if it has a `tests/` file importing it — and the concrete-project
   template does not ship that file yet (deferred to `/update_template_repo`,
   SDD step 12). For a downstream without it, the existing pytest run silently
   collects zero probes and is not a collection error. Layer 6 must therefore
   verify the wiring, not add a second invocation.
2. **D6's evidence citation is weak.** The spec credits "Part 1's own notes" for
   proving free text suffices, but that file's single `changed_settings` entry is
   a pytest-marker registration caveat whose hardness lives only in prose. The
   real precedent is elsewhere in the corpus. D6's *conclusion* (no new schema
   flag) still stands — see below.
3. **The check framing is too narrow.** Checks are spread across eight apps and
   all of them run on a plain `manage.py check`; only two are new from Layer 4.
   Guidance written against two hardcoded IDs would be obsolete on the next spec.
   **Do not quote a check count anywhere** — it goes stale on the next spec that
   adds one, which is exactly the failure mode this correction is about.
4. **`freedom_ls_course_access.E001` was repurposed, not merely renamed.** It
   still exists, now meaning "`COURSE_ACCESS_BACKEND` unset"; `.E002` took over
   its old meaning ("invalid `Course.access_config`"). This is *worse* than a
   plain re-ID: a downstream that silenced `E001` is now silencing a **different
   check** than it intended, with no error to tell it so.
5. **The Layer-3 upgrade notes are not a safe source for the opt-in snippet.**
   `3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md`
   carried a pre-`learner-terminology-rename` pruning example,
   `conformance.drop("student_interface:courses")` — a silent no-op, since
   `drop()` on an unknown probe id does nothing and the shipped code uses
   `learner_interface:*`. That one identifier has been corrected in place as part
   of this slice, but the **canonical** source stays the live package docstring at
   `freedom_ls/contrib/conformance/__init__.py`; copy the snippet from there.

## Scope of this slice (Layers 5 & 6)

**Five file edits**, up from two. The two originals are Claude Code slash-command
markdown files — use the `sdd:claude-code-authoring` skill for both. The other
three are the mechanical marker-selection sweep forced by revision note (c):
`resources/testing.md`, `resources/playwright-testing.md` and
`skills/playwright-tests/SKILL.md` each carry one stale copy of the selection
string and change by one token.

### Layer 5 — `claude_plugins/fls-dev/commands/update_upgrade_notes.md`

Add guidance covering **two** cases (the second is new since the last revision):

- **(a) Hard vs optional settings changes.** Teach the author to distinguish a
  **hard/required** settings change from an optional/informational one. When a
  spec introduces a hard config requirement, set `requires_settings_change: true`
  with the specific keys in `changed_settings`; when the spec also adds a Layer-4
  check enforcing it at boot, say so, so `update_fls` can point the downstream at
  `manage.py check`.
- **(b) Changed or repurposed check IDs are hard changes.** The command's current
  trigger list never mentions check IDs, yet renaming or repurposing one silently
  breaks a downstream's `SILENCED_SYSTEM_CHECKS` entry. Treat it as a hard change
  and name `SILENCED_SYSTEM_CHECKS` in `changed_settings`. The `E001` repurposing
  above is the worked example — and the sharpest one, because the silencing keeps
  working while now silencing the wrong check.

**No new schema flag (D6 stands), but for a better reason than the spec gives.**
The only consumer of these fields in the repo is an agent reading them as prose
(`update_fls.md` says `requires_settings_change` → "review and apply the listed
`changed_settings`"), so a machine-readable hard/soft flag would buy nothing.
Cite the notes that actually demonstrate the pattern — authors have already,
independently, encoded hardness as inline `#` comments inside `changed_settings`
(`SECRET_KEY # now mandatory — hard-fails at boot if missing/empty` sitting next
to `DB_SSLMODE # new env var (default "prefer")`), in
`3. done/…support-concrete-project-deployment-1-prod-settings/upgrade_notes.md`
and `3. done/2026-07-19_07:52_more-deploy-preparation/upgrade_notes.md` — **not**
Part 1's notes.

Motivating evidence that the guidance is needed at all: **2 of the 15** existing
`upgrade_notes.md` files set `requires_settings_change: true` for changes that are
purely optional parity, so today the boolean alone conflates "you must act" with
"here's a knob you may ignore."

Write the guidance **generally** — any future spec adding a hard-requirement check
follows the pattern. Cite the current hard-requirement checks as examples rather
than as the definition: `freedom_ls_course_access.E001` (`COURSE_ACCESS_BACKEND`)
and `freedom_ls_content_engine.E001` (`ADMONITION_TYPES`), both produced by the
shared `required_settings_errors()` helper in `freedom_ls/base/app_settings.py`.

### Layer 6 — `claude_plugins/fls-dev/commands/concrete/update_fls.md`

Add to the verification steps:

- **(a) A conformance opt-in precondition, not a new invocation.** Before treating
  the existing pytest run as the wiring signal, confirm the project has a `tests/`
  file importing `freedom_ls.contrib.conformance`. If it does not, that run
  collects zero conformance probes and proves nothing about wiring. If it is
  missing, **write it from the inline snippet, say that it was added, and
  continue** — this is mechanical one-time wiring, not a judgement call. Stop and
  report only if the file cannot be written. Take the snippet from the live
  package docstring at `freedom_ls/contrib/conformance/__init__.py`, **not** from
  `3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md`
  (see § "Research corrections" 5). Also note, at the existing pytest step,
  that *this* is where the suite runs — so a green run reads as meaningful rather
  than merely "tests passed".
- **(b) `uv run python manage.py check`** — but **not** because Layer-4 failures
  would otherwise go unseen. Django's `migrate` and `makemigrations` both inherit
  `requires_system_checks = "__all__"`, so every FLS check already runs, and every
  `Error` already aborts, inside the migration gates. The dedicated step earns its
  place for **attribution** (a configuration `Error` currently reads as migration
  trouble) and **warning visibility** (a Warning piggy-backed onto another command
  gets no summary line and never blocks). Every FLS check runs on the plain
  command — no `--deploy`, no `--tag` needed. Errors exit non-zero; Warnings do
  not.

**Placement and ordering:** `manage.py check` goes in **its own sub-step,
immediately before the post-flight `makemigrations --check`** (today's `3g`),
which means renumbering the sub-steps after it. The conformance opt-in
precondition goes in the **"Verify"** sub-step, ahead of the pytest gate it
guards. Mirror both in the `# Per-spec loop (reference)` pseudocode block, in the
same order, so the file stays internally consistent. The ordering rationale is
attribution, not timing: `check` runs **after** the pointer move, `uv sync` and
any flagged settings application, and **before** the migration conflict gate, so
configuration drift is named as configuration drift. Make both **blocking**,
matching the file's existing convention — every verification step in it already
is (the `migrate --check` and `makemigrations --check` gates both use "stop and
resolve" language). Step 4's final sync and the rollback green-check gain **no
new prose** — they are deliberately lightweight recovery gates — but their pytest
lines do pick up the corrected marker selection along with everything else.

**The port-pattern instruction is dropped.** `update_fls.md` has no runserver step
and neither new check needs one, so "use the documented port pattern" was a no-op.
If a later edit does add anything runserver-shaped, follow the documented pattern
(allocate via `.claude/ds/scripts/find_available_port.sh`, then
`runserver $PORT`) — but do not go looking for a runserver step to add here.

### Layer 6 — `claude_plugins/fls-dev/resources/template_repo_manifest.md`

Unchanged in scope: the `urls.py` checklist is out of sync with `config/urls.py`
(omits `applications/`, `interest/`, sitemap/robots). The **actual manifest edit
is `/update_template_repo`'s job (SDD step 12), NOT this slice** — this idea only
records the requirement so that step lands it. Do not pre-empt it.

Research strengthens the case: the manifest currently has **no mention at all** of
`tests/`, `pytest`, or `conformance`. Step 12 must also ship the downstream
`tests/` file importing the conformance suite — otherwise Layer 6's new
precondition check will report "not wired" for every freshly generated project.

## Constraint: `commands/concrete/` ships to downstreams

`update_fls.md` runs **inside a concrete project**, not in this repo. It must
never reference FLS's own `spec_dd/` layout, FLS-internal dev tooling paths, or
FLS-internal test markers as if the downstream had them. Everything it names must
exist in a concrete FLS checkout. (The opt-in snippet should be reproduced inline
rather than referenced by FLS spec path.)

## Dependencies between the split-out slices

- **`test_portability_2_conformance_suite` (Layer 3)** — **shipped**
  (`freedom_ls/contrib/conformance/`). It is an importable module with no
  management command and no `pytest --pyargs` target; the only invocation is the
  downstream's own pytest, after opt-in.
- **`test_portability_3_system_checks` (Layer 4)** — **shipped.** Its new checks
  are `freedom_ls_course_access.E003` and `freedom_ls_learner_interface.W001`,
  plus the downstream-visible `E001` repurposing described above. Its notes live
  in `3. done/2026-08-23_16:23_fls-integration-system-checks/` — note the
  directory name does not match the slice name, a minor repo-hygiene
  inconsistency.
- Independent of the Layer 0 settings-convention refactor (shipped 2026-07-10).
- Assumes Part 1 already switched the bare `uv run pytest` call sites to the
  documented marker selection. Part 1 shipped **no `e2e` marker** — `playwright`
  is the browser-test marker.

## Non-goals / recorded for later

- **A downstream-facing inventory of every FLS check ID.** No such doc exists;
  each app's `checks.py` docstring is the closest thing, and `docs/` names exactly
  one ID (`freedom_ls_deployment.W001`). Out of scope here — record it as a
  possible follow-up rather than growing this slice.
- **An opt-in snippet anywhere under `docs/`.** The only copy-pasteable forms live
  in `spec_dd/` (which a downstream never receives) and in the package docstring.
  `docs/product/configuration-and-extension.md`'s `Conformance Suite` section is
  deliberately symbol-free and never names the import path. Recorded as a possible
  follow-up; it is why `update_fls.md` must reproduce the snippet inline.
- **`update_fls.md` has no YAML front matter at all** (no `description:`, no
  `allowed-tools:`), unlike every sibling command in the plugin. Pre-existing and
  out of scope for this slice — tracked here as a separate cleanup item so it
  isn't lost.
- **"Never reuse a retired check ID"** as a third documented convention
  (`freedom_ls_reports.W003` is the in-repo precedent, retired and never reused).
  Considered and deliberately left out of the Layer-5 guidance to keep it focused;
  noted here in case a later spec wants it.
