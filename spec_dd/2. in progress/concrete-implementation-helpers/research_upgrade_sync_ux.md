# Research: Upgrade/Sync UX — Making FLS Updates Safe, Smooth, and Trustworthy

## 1. What the Existing Command Does

The `update_fls.md` command in `fls-claude-plugin/commands/concrete/` implements a spec-by-spec upgrade flow:

1. **Identify new specs** by scanning the FLS git log for commits that moved a directory into `spec_dd/3. done/`. The directory name encodes a completion timestamp (e.g. `2026-03-18_13:49_webhook-translation-layer`).
2. **Integrate each spec sequentially** via a subagent loop:
   - Advance the submodule pointer to the commit that completed the spec.
   - Read `spec_dd/3. done/<spec>/1. spec.md` and `2. plan.md` to understand what was built.
   - Perform necessary integration work (migrations, template overrides, settings, Tailwind rebuild, package upgrades).
   - Run `uv run pytest` as a gate.
   - Commit with message `Update FLS: <spec-name>`.
3. **Final sync** to `origin/main` if post-spec commits exist, then one last full test run.

Strengths of this approach:
- Granular: one spec = one commit, so bisect and revert are tractable.
- Self-documenting: spec artifacts (spec.md, plan.md) provide human-readable context for each integration step.
- Test-gated: pytest must pass before advancing.
- Commit-before-proceeding discipline prevents half-applied states from accumulating.

---

## 2. Patterns from Mature Framework Ecosystems

### 2.1 Django's Release Notes + `makemigrations --check`

Django structures every release with:
- **"Backwards Incompatible Changes"** section — explicit, categorised, with before/after code examples.
- **"Deprecated Features"** section — what is warned now, what will be removed next major.
- **"Features Removed"** — what completed its deprecation cycle.
- An explicit **upgrade guide** linked from the release notes.
- `manage.py check --deploy` as a system health gate.
- `manage.py makemigrations --check` as a zero-exit-code signal that all model changes have been captured (no unapplied schema drift).

The key lesson: Django never expects downstream maintainers to diff commits. Instead, it publishes structured prose that tells them *what category of action is required* and for whom.

References:
- [Django 6.0 Release Notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- [Django Release Process](https://docs.djangoproject.com/en/dev/internals/release-process/)

### 2.2 Wagtail Upgrade Considerations

Wagtail's upgrade guide structures a concrete checklist per minor version:
1. Resolve existing deprecation warnings (`-Wa` flag or `PYTHONWARNINGS`).
2. Read the "Upgrade considerations" section in the release notes.
3. Back up the database.
4. Update dependencies, run migrations, apply code changes.
5. Clear browser cache (for admin static files).
6. Run the full test suite.

The incremental model is explicit: upgrade one minor version at a time, not version-skipping. This maps cleanly to FLS's one-spec-at-a-time model.

References:
- [Upgrading Wagtail](https://docs.wagtail.org/en/stable/releases/upgrading.html)
- [Wagtail 7.0 LTS Release Notes](https://docs.wagtail.org/en/latest/releases/7.0.html)

### 2.3 Symfony Flex `recipes:update`

Symfony Flex's `recipes:update` command (since v1.18/2.1) solves a problem FLS also faces: a framework ships scaffold files (templates, config) that downstream projects partially customise, and those scaffold files evolve.

The approach:
1. Records a **baseline hash** of each recipe file at install time.
2. On `recipes:update`, computes a diff between the originally-installed version and the current upstream version.
3. Applies that diff as a git patch — standard merge mechanics, familiar conflict markers.
4. Outputs a **CHANGELOG summary** of all upstream recipe PRs since installation, with clickable PR links.
5. Safe to run repeatedly.

The lesson: diff-based patching combined with inline provenance ("PR #892 — disable http_method_override") is vastly more trustworthy than "look at the code diff and figure it out yourself."

References:
- [Fast, Smart Flex Recipe Upgrades with recipes:update](https://symfony.com/blog/fast-smart-flex-recipe-upgrades-with-recipes-update)
- [Updating recipes](https://server-for-symfony-flex.readthedocs.io/en/latest/topics/recipe_updating/)
- [Flex Recipe Upgrades — SymfonyCasts](https://symfonycasts.com/screencast/symfony7-upgrade/upgrade-recipes)

### 2.4 Rails `app:update`

`rails app:update` re-runs the generator that Rails would use for `rails new`, but instead of overwriting files silently, it uses the same interactive conflict resolution that `rails generate` uses: it shows each changed file and asks whether to overwrite, diff, skip, or show the full change.

In Rails 7.2, this became a proper `Rails command` rather than a rake task, gaining standard `--help` and flag support.

The key pattern: **interactive review per file**, not a bulk overwrite. The downstream developer decides what to take.

References:
- [Rails 7.2 Adds app:update Task to be a Rails Command](https://blog.saeloun.com/2024/07/09/rails-app-update-command/)
- [Rails upgrade strategy](https://blog.simplificator.com/2022/05/25/rails-upgrade-strategy/)

### 2.5 `django-upgrade` / `pyupgrade` Codemods

`django-upgrade` is a fast codemod tool (uses stdlib `ast` + `tokenize-rt`) that automatically rewrites Python files to match a target Django version. It runs in under 0.5 seconds on 150k-line codebases.

The codemod model: instead of asking downstream maintainers to read release notes and manually update code, a tool detects the deprecated pattern and rewrites it in place. The output is a diff the developer can review in git.

For FLS this is not directly applicable today (FLS is the upstream, not a Django version). But the principle — **mechanical detection of required downstream changes** rather than human reading of prose — is transferable.

References:
- [django-upgrade PyPI](https://pypi.org/project/django-upgrade/)
- [Introducing django-upgrade](https://adamj.eu/tech/2021/09/16/introducing-django-upgrade/)
- [Upgrade Smarter, Not Harder: Python Tools for Code Modernization](https://www.caktusgroup.com/blog/2025/03/27/upgrade-smarter-not-harder-python-tools-code-modernization/)

### 2.6 Machine-Readable Changelog / Upgrade Notes

The emerging standard for framework upgrade communication is a machine-readable per-release artifact alongside the human-readable prose. Formats include YAML, JSON, and plain Markdown with stable URLs. Key properties:
- Structured fields: `breaking: true/false`, `requires_migration: true/false`, `affected_apps: [...]`, `action_required: <text>`.
- Stable URL per release so tooling can fetch it.
- Both a CHANGELOG (cumulative) and per-release notes (atomic).

References:
- [Changelog vs Release Notes: What's the Difference](https://www.releasepad.io/blog/changelog-vs-release-notes-whats-the-difference-and-which-do-you-need/)
- [Why Your Product Changelog Needs a Machine-Readable Markup Version](https://www.releasepad.io/blog/why-your-product-changelog-needs-a-machine-readable-markup-version/)
- [release-drafter machine-readable CHANGELOG issue](https://github.com/toolmantim/release-drafter/issues/253)

### 2.7 Git Submodule Safety Patterns

Established best practices for submodule-based integration:
- Pin to a specific commit SHA, not a branch head — stability vs. surprise.
- Never pull multiple specs simultaneously; advance one at a time, test, commit.
- `push.recurseSubmodules = on-demand` prevents pushing a super-repo commit that references an unpublished submodule commit.
- Document the submodule update workflow explicitly; it is the most common source of confusion in submodule projects.

References:
- [Git Submodules — Atlassian](https://www.atlassian.com/git/tutorials/git-submodule)
- [Git Submodules — Pro Git Book](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [Best Practices for Using Git Submodules](https://blog.pixelfreestudio.com/best-practices-for-using-git-submodules/)

### 2.8 Django Migration Conflicts

When a concrete implementation has its own apps with their own migrations, upgrading FLS can create migration graph conflicts if FLS migrations reference shared models or alter Django's built-in models (e.g. `ContentType`, `Permission`). Django detects this and refuses to run until a merge migration is created (`manage.py makemigrations --merge`). The `django-linear-migrations` tool enforces a single-head invariant via `max_migration.txt`, making conflicts loud and immediate rather than silent.

References:
- [Preventing migration conflicts in Django](https://nezhar.com/blog/preventing-django-migration-conflicts-during-development/)
- [django-linear-migrations — GitHub](https://github.com/adamchainz/django-linear-migrations)
- [How Django Migration Handles Conflict](https://medium.com/@shairfmabdullah/how-django-migration-handles-conflict-cd3d96439944)

---

## 3. Evaluation of `update_fls.md`

### 3.1 What It Does Well

**Spec-by-spec granularity.** One spec = one commit is the right unit. This matches Django's "upgrade one minor version at a time" principle, Rails' "one update - one commit" rule, and Wagtail's incremental approach. It keeps the git graph bisectable.

**Human-readable context.** Reading spec.md and plan.md before integrating is a genuine advantage over pure diff-reading. The intent and the architectural decisions are visible, not just the code delta.

**Test gate before advancing.** Requiring `pytest` to pass before moving to the next spec means failures are immediately localised to the spec just applied. This is exactly the "test after each update" pattern recommended by Rails upgrade guides.

**Subagent parallelism is correctly blocked.** Specs are applied sequentially, which prevents race conditions in the migration graph and in template state.

### 3.2 Gaps and Risks

**No machine-readable signal about what category of change a spec requires.**
Currently a subagent must read spec.md and plan.md, infer what integration work is needed, and decide whether to run migrations, update templates, change settings, etc. This is accurate but slow and prone to the subagent missing things. There is no structured field that says "this spec: adds migrations = yes, changes templates = yes, adds new required settings = no."

**No explicit handling of migration conflicts between FLS and the concrete project.**
If the concrete project has its own apps with migrations, and a FLS spec adds migrations that touch shared models or create new dependencies, the update step should explicitly run `manage.py makemigrations --check` to verify no unapplied model changes exist in the concrete project before attempting to apply FLS's new migrations. The current command only runs `manage.py makemigrations` after the fact (implied), not as a pre-flight check.

**No template-override drift detection.**
FLS templates are overridden by concrete projects for branding and UX customisation. When FLS changes a template (new HTMX attribute, restructured block, new cotton component reference), a concrete project's override may silently diverge and stop working or render incorrectly. The current command asks the subagent to "update template overrides to match new FLS templates" but provides no systematic way to discover which overrides are affected. There is no mechanism analogous to Symfony Flex's diff-based patching.

**No CHANGELOG or version signal.**
FLS has no CHANGELOG, no semantic version bump on spec completion, and no per-spec "upgrade notes" artifact. The update_fls.md command reconstructs the "what changed" list from git log by detecting spec directory moves — this is a fragile heuristic. If the spec move commit is squashed or the spec is completed via a merge commit that touches many files, the detection logic could miss it or mis-order specs. There is also no stable URL or artifact a downstream CI system could poll to learn "has FLS advanced since our last sync?"

**No dry-run or preview mode.**
The command goes straight to `git checkout <commit-hash>` and integration work with no preview step. A "what would change" report — listing the specs to be applied, flagging any with migrations or breaking template changes — would let the developer decide whether to proceed, defer, or split the upgrade across multiple sessions.

**No explicit rollback path.**
If a spec fails mid-integration (tests fail, migration conflict, broken template), the command says "commit before moving to next spec" but does not document what to do when integration fails. In practice, the developer must manually `git checkout` to restore the submodule pointer and revert their integration changes. A documented rollback procedure (e.g. `git stash` + revert the submodule pointer) is missing.

**Subagent fan-out for spec integration may compound errors.**
The command says "use a subagent to do the following" for each spec. If a subagent misinterprets a spec or applies incorrect integration, the error may not be caught until `pytest` runs — or may not be caught at all if the test coverage for that integration path is incomplete. The command provides no guidance on what to do when a subagent makes an incorrect inference.

**No explicit package-upgrade gating.**
If a FLS spec upgrades Django or a major dependency, the concrete project must upgrade that package in its own `pyproject.toml`. The current command mentions this as a possibility but provides no structured check (e.g. comparing `pyproject.toml` versions between FLS and the concrete project).

---

## 4. Recommendations

### 4.1 Introduce a Per-Spec `upgrade_notes.md` Artifact

Each completed spec in `spec_dd/3. done/<spec>/` should include an `upgrade_notes.md` file authored at the time the spec is completed (not retrofitted). This file would use a lightweight structured format:

```markdown
# Upgrade Notes: <spec-name>

## Integration Requirements

- requires_migrations: true
- requires_template_review: true
- requires_settings_change: false
- requires_package_upgrade: false
- requires_tailwind_rebuild: false

## Migrations

Adds migrations to `student_management`. No data migrations; schema only.
Run: `uv run python manage.py migrate`

## Template Changes

`freedom_ls/student_interface/templates/student_interface/toc.html` — new
`deadline_badge` cotton component reference added inside the topic loop.
Concrete projects overriding this template must add the component call.

## Breaking Changes

None.

## Settings

No new required settings.
```

This is the FLS equivalent of Django's "Backwards Incompatible Changes" section, but scoped to a single spec and structured for Claude-agent consumption. The update command can read this file first and use its flags to decide what integration steps to run — rather than inferring from spec.md prose.

### 4.2 Add a Pre-Flight Dry-Run Step to `update_fls.md`

Before any submodule pointer moves, add a Step 0 that lists all specs to be applied and their `upgrade_notes.md` summaries (or "no upgrade_notes.md found" for older specs). Output should include:
- Spec name and timestamp.
- Whether migrations are required.
- Whether templates need review.
- Whether package upgrades are required.
- Whether any spec has no upgrade_notes.md (meaning the subagent must infer).

This gives the developer a clear overview before committing to the process and surfaces the "how long will this take" and "how risky is this" questions upfront.

### 4.3 Add an Explicit Migration Pre-Check

Before applying each spec, run:
```
uv run python manage.py migrate --check
```
This exits non-zero if there are unapplied migrations — meaning the concrete project is not in a clean migration state before we add FLS's new migrations. If this check fails, surface the error and halt rather than proceeding into a migration conflict.

After applying FLS migrations, also run:
```
uv run python manage.py makemigrations --check
```
This confirms the concrete project's models still match the migration state (no unapplied model changes were accidentally introduced).

If the concrete project uses `django-linear-migrations`, ensure the `max_migration.txt` files are updated as part of the integration commit.

### 4.4 Add Explicit Template Drift Detection Guidance

The `update_fls.md` command should include a step that, for any spec whose `upgrade_notes.md` lists changed templates, explicitly:
1. Identifies which FLS templates changed in that spec commit (via `git diff --name-only <prev-commit> <spec-commit> -- freedom_ls/*/templates/`).
2. Checks whether the concrete project has an override file at the same path under its own `templates/` directory.
3. If an override exists, flags it for review and shows `git diff` of the FLS-side change so the developer can decide what to port.

This is a lightweight approximation of Symfony Flex's diff-based patching — no automatic merge, but at minimum the developer is told "you have an override of this file and it changed upstream."

### 4.5 Document a Rollback Procedure

Add a "If integration fails" section to `update_fls.md`:

```
If a spec fails and you need to roll back:
1. git -C submodules/Freedom-LS checkout <previous-commit>
2. git checkout HEAD -- submodules/Freedom-LS  (restore the .gitmodules pointer)
3. uv run python manage.py migrate <app> <previous-migration>  (if needed)
4. git stash drop  (discard any uncommitted integration changes)
```

This prevents the ad-hoc manual recovery that currently happens when things go wrong.

### 4.6 Consider a Machine-Readable Spec Index

A file at `spec_dd/spec_index.json` (or `CHANGELOG.md`) in FLS, updated whenever a spec moves to done, would allow the update command to fetch the list of new specs without parsing git log commit messages. Format:

```json
[
  {
    "spec": "deadlines",
    "completed_at": "2026-02-19T19:25:00",
    "commit": "abc123",
    "requires_migrations": true,
    "requires_template_review": true
  }
]
```

This is the machine-readable changelog pattern used by Jenkins and increasingly by AI-aware tooling. The update command becomes a consumer of a structured data source rather than a git log parser.

### 4.7 Require Explicit `upgrade_notes.md` in the Spec-Completion Workflow

For this to work going forward, FLS's own spec-completion process should include authoring `upgrade_notes.md` as a required step before moving a spec to `spec_dd/3. done/`. The update command should emit a warning (not a failure) when processing a spec that lacks `upgrade_notes.md`, reminding the integrator that they are flying blind and must read the full spec and diff.

### 4.8 Preserve the Core Design

The existing one-spec-one-commit model, the spec artifact reading, and the test-gate-before-advance discipline are all correct and should not change. The improvements above are additions and clarifications, not replacements. The goal is to make each integration step more deterministic by giving the subagent structured intent signals (upgrade_notes.md) rather than requiring it to infer from prose, and to make failure modes explicit rather than implicit.

---

## 5. Summary of Improvements vs Current State

| Dimension | Current state | Recommended improvement |
|---|---|---|
| Integration signal | Infer from spec.md prose | Structured `upgrade_notes.md` per spec |
| Pre-flight visibility | None — dive straight in | Dry-run step listing all specs + flags |
| Migration safety | Implied post-hoc only | Explicit `--check` pre and post each spec |
| Template drift | "Update if needed" (implicit) | Diff-based flag: "your override changed upstream" |
| Rollback guidance | None | Explicit step-by-step rollback section |
| Changelog signal | Git log parsing heuristic | Machine-readable `spec_index.json` or CHANGELOG |
| Package upgrade check | Mentioned as a possibility | Explicit `pyproject.toml` comparison step |
| Failure mode documentation | None | "If integration fails" section in command |

status: ok
