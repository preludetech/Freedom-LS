# Conformance upgrade-notes & plugin-doc tie-ins

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It bundles
**Layer 5** (the `upgrade_notes.md` tie-in) and the **Part-2 portion of Layer 6**
(plugin-doc touches) — the "make the new conventions stick" documentation work
that surrounds the conformance suite and system checks.

The full motivation and rationale live in the referenced source files below — not
duplicated here.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea
  (§ "Layer 5", § "Layer 6 (Part-2 portion)").
- `2. in progress/fls-test-portability-part-2/1. spec.md` — **§ "Layer 5"**,
  **§ "Layer 6"**, and decision **D6**.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 5"** and
  **§ "Layer 6"** for the exact command/doc edits.
- Research:
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`

## Scope of this slice (Layers 5 & 6)

Summarised from spec/plan § "Layer 5" / "Layer 6" — see there for full detail:

- **Layer 5 — `commands/sdd/update_upgrade_notes.md`:** add guidance to recognise
  a **hard/required** settings change (vs optional/informational). When a spec
  introduces a hard config requirement, set `requires_settings_change: true` with
  the specific keys in `changed_settings`; when the spec also adds a Layer-4 check
  enforcing it, say so in the notes. **No new schema flag** (D6) —
  `requires_settings_change` + `changed_settings` suffices.
- **Layer 6 — `commands/concrete/update_fls.md`:** add to the verification steps
  (a) invoke the conformance suite as the positive signal, and (b) run `uv run
  python manage.py check` so system-check failures surface during an upgrade. Use
  the documented port pattern for any runserver step (do not hardcode 8000).
- **Layer 6 — `fls-claude-plugin/resources/template_repo_manifest.md`:** the
  `urls.py` checklist is out of sync with `config/urls.py` (omits `applications/`,
  `interest/`, sitemap/robots). The **actual manifest edit is
  `/update_template_repo`'s job (SDD step 12), NOT this slice** — this idea only
  records the requirement so that step lands it. Do not pre-empt it.

## Dependencies between the split-out slices

- **`fls-conformance-suite` (Layer 3)** — the `update_fls.md` edit invokes the
  conformance suite, so that slice should exist (or land together) for the
  instruction to be real.
- **`fls-integration-system-checks` (Layer 4)** — the Layer-5 hard-requirement
  guidance points downstreams at `manage.py check`; it pairs with those checks.
- Independent of the Layer 0 settings-convention refactor.
- Use the `fls:claude-code-authoring` skill for the slash-command edits.
- Assumes Part 1 already switched the bare `uv run pytest` call sites to the
  documented marker selection.
