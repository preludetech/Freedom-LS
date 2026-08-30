# Research notes: how `upgrade_notes.md` goes stale, and where a guard could catch it

## 1. The drift mechanism, in three sentences

`/update_upgrade_notes` authors `upgrade_notes.md` from a **snapshot** of the branch at one point in
the SDD run — the spec, the plan, and `git diff main..HEAD` at that moment — and nothing downstream
of that snapshot re-derives or re-checks it. Six more commits landed on `prod_bucket_setup` after
authoring (`888d290e`, `2da4bad8`, `752db66b`, `4f937a95`, `25a48721`, `5d33bbf6`, `614e681e` — seven,
one of which, `25a48721`, happened to touch the file), and one of the untouched six
(`752db66b`) deleted the exact class (`OverwritingFileSystemStorage`) the notes had just described as
the way to configure local-disk logo overwrite. Nothing in the rest of the SDD workflow — QA,
`address_pr_review`, `finish_worktree`, or the move to `spec_dd/3. done/` — reads `upgrade_notes.md`
for accuracy; the closest thing, `/update_template_repo`, reads it only to decide *what* to sync, not
whether its claims still resolve, and in this run that step's todo box (`spec_dd/3.
done/2026-08-27_12:32_prod_bucket_setup/todo.md` item 12) was never ticked at all, so it never even
ran.

## 2. What `/update_upgrade_notes` reads, and what it never checks

Source: `claude_plugins/fls-dev/commands/update_upgrade_notes.md`.

**Inputs (Step 2, lines 65–90):**
- `<spec-dir>/1. spec.md` and `<spec-dir>/2. plan.md` — read for prose content, not code facts.
- `git log main..HEAD --oneline` and `git diff main..HEAD` — the *actual* diff, run once, at
  authoring time.

The command explicitly tells the author to scan that diff for five signal classes: new/changed
migrations, changed templates, changed settings/`config/` files, `pyproject.toml`/`requirements*.txt`
changes, npm/Tailwind changes (lines 84–89). All five are diff-shape checks — "did a file matching
this glob change" — not resolution checks.

**What it never checks (nothing in the file does any of this):**
- No step imports, greps for, or otherwise confirms that any Python dotted path, class name, or
  symbol the prose names (e.g. `freedom_ls.deployment.storage.OverwritingFileSystemStorage`) actually
  exists in the tree at authoring time, let alone at any point afterward.
- No step confirms a named Django setting is declared in `config/settings_base.py`.
- No step confirms a named migration file exists on disk.
- No step confirms a named system-check id is emitted by a `checks.py` `register()`.
- No step confirms a referenced file path (e.g. the `env_example` template) still exists at the path
  named.
- Step 3's "Rules for the prose sections" (lines 95–102) say "Facts only... Base every statement on
  the spec, the plan, and the actual diff" — but that is an instruction to *not invent* facts, not an
  instruction to *re-verify* facts already written once code moves on. There is no re-read, no
  re-diff, no verification pass anywhere in the file.
- Step 4 (Tick the todo) is the command's only closing action, and it only calls the
  `update_todo` protected helper — a mechanical checkbox edit with no content check
  (`claude_plugins/sdd/commands/protected/update_todo.md` — confirmed by reading it in full: it
  matches `- [ ]` text and flips it to `- [x]`, nothing more).

## 3. Where the notes sit in the SDD run order, and what runs after them

Per `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/todo.md` (a real completed run) and
`claude_plugins/sdd/commands/README.md`, the canonical order is:

1. Idea → Spec → Threat model → Plan → Plan security review → Plan structure review
2. **Implementation** (`/sdd:implement_plan`)
3. Code security review (`/ds:security-review`)
4. **QA** (`/fls-dev:do_qa`) — the todo shows two QA-round bugfixes landed *after* this step in this
   run (todo lines 54–55), each its own commit
5. Product documentation (`/fls-dev:update_product_docs`)
6. **Upgrade notes** (`/fls-dev:update_upgrade_notes`) — todo section 11, authored at `3dc70cc7`
7. Template repo (`/fls-dev:update_template_repo`) — todo section 12, **never ticked** in this run
8. Author plugin sync (`/fls-dev:update_claude_plugin_fls_content`) — todo section 13
9. **Pull request** (`/sdd:make_pr_quickly`, then `/sdd:address_pr_review`) — todo section 14. This is
   where the bulk of the post-authoring commits landed: the todo lists **seven** `(user + cmd)` PR
   review fixes (lines 80–86), each an independent TDD fix, one of which is exactly `752db66b`
   ("`OverwritingFileSystemStorage.get_available_name` deleted before writing — replaced with
   Django's own `allow_overwrite`"). `/sdd:address_pr_review`
   (`claude_plugins/sdd/commands/address_pr_review.md`) fetches PR comments, fixes issues, runs
   `pytest` and `pre-commit` (Steps 5–6) — it never reads or touches `upgrade_notes.md`.
10. **Cleanup** (`/sdd:finish_worktree`) — todo section 15, the true last step before the spec directory
    moves to `spec_dd/3. done/`.

`/sdd:finish_worktree` (`claude_plugins/sdd/commands/finish_worktree.md`) is confirmed, by reading it
in full, to run: rebase → run unit tests if functionality changed → per-project teardown script →
tick the todo → **move the spec directory to `spec_dd/3. done/…`** (Step 5) → tidy Claude project
settings → commit → `git status` check. **`upgrade_notes.md` is never opened, read, or referenced
anywhere in this file.** The spec directory — including the now-stale `upgrade_notes.md` — is moved
to "done" and shipped in the same command that runs the last commit.

So structurally: the notes are authored roughly two-thirds of the way through the flow (after QA, at
the "docs" cluster), and everything from that point through PR review — which is exactly where most
substantive code correction happens, per this run's todo — has no re-verification step. `/sdd:next`
(`claude_plugins/sdd/commands/next.md`) mechanically walks the checklist top-to-bottom and has no
knowledge of content staleness either; it only knows whether a box is ticked.

## 4. Repeat-offence evidence

Sampled three other completed specs under `spec_dd/3. done/` with an `upgrade_notes.md`, spot-checking
the dotted paths, setting names, class names, file paths and management-command names each one names
against the code at HEAD:

- **`2026-08-22_15:42_learner-terminology-rename`** (the largest and most detailed notes file sampled,
  ~860 lines). Checked: `INSTALLED_APPS` entries `freedom_ls.learner_management`,
  `freedom_ls.learner_progress`, `freedom_ls.learner_interface` and the context-processor dotted path
  `freedom_ls.learner_management.context_processors.can_access_educator_interface` — all present
  verbatim in `config/settings_base.py` (lines 111–112, 125, 192). Checked the five renamed QA
  management commands (`qa_create_course_player_learner`, `qa_create_empty_learner_cohort`,
  `qa_create_password_reset_learner`, `qa_create_rich_dashboard_learner`,
  `qa_reset_learner_progress`) — all five exist as files under
  `freedom_ls/qa_helpers/management/commands/`. Checked `REPORTS_MAX_LEARNERS`, `LearnerRow`,
  `LearnerDetail`, `LearnerDetailLike`, and `AtRiskRule.evaluate(learner)` — all present and matching
  in `freedom_ls/reports/config.py`, `report_data.py`, and `at_risk.py`. **No drift found** despite
  this being the single riskiest notes file in the sample (an exhaustive rename with dozens of named
  symbols).
- **`2026-08-23_16:23_fls-integration-system-checks`** (renamed `freedom_ls_course_access.E001` to
  `.E002`, added `.E003`, added `freedom_ls_learner_interface.W001`). Checked: all four ids
  (`freedom_ls_course_access.E001/E002/E003`, `freedom_ls_learner_interface.W001`) are grepped as
  present in `freedom_ls/course_access/checks.py` and `freedom_ls/learner_interface/checks.py` (plus
  their test files). **No drift found.**
- **`2026-08-28_07:52_report-rendered-with-org-name`**. Checked: `OrganisationBrand` dataclass exists
  in `freedom_ls/reports/report_data.py`; the new partial
  `learner_interface/partials/course_organisation_chip.html` exists on disk;
  `HEADER_LOGO_ON_DARK_STATIC_PATH` is a live setting referenced in `config/settings_base.py`,
  `config/settings_dev.py`, `freedom_ls/reports/render.py`, and `freedom_ls/site_aware_models/config.py`.
  **No drift found.**

**Conclusion: this looks like an unlucky instance, not a systemic pattern — with one important
caveat.** All three comparison specs happen to be ones where the notes were authored either at or very
near the end of that branch's commit sequence (no evidence of a long post-authoring tail the way
`prod_bucket_setup` had six-of-seven post-authoring commits skip the file). The mechanism that broke
`prod_bucket_setup` — a late-authored artifact outlived by a long, review-driven fix tail — is a
property of *when in the branch's life the notes got authored relative to how much churn followed*,
not a property of the authoring command being generally sloppy. A spec with a short or absent PR
review round is structurally safe from this failure; one with a long review round (like
`prod_bucket_setup`'s seven TDD review fixes) is structurally exposed to it, regardless of how careful
the authoring command was at the time it ran. This argues for a **guard placed after the exposure
window closes** (PR review / worktree-finish) rather than one that only makes authoring itself more
careful.

## 5. What is mechanically checkable vs what needs judgement

| Claim class | Mechanically checkable? | The check | False-positive risk |
|---|---|---|---|
| Python dotted path / class / callable (`freedom_ls.deployment.storage.OverwritingFileSystemStorage`) | **Yes** | `importlib.import_module()` the module, `getattr()` the trailing symbol | Low. A prose sentence naming a class in backticks is usually unambiguous; the risk is under-extraction (missing a dotted path embedded in a code fence or table cell) rather than false alarms. |
| Django setting name (`REPORTS_STORAGE_ALIAS`, `HEADER_LOGO_ON_DARK_STATIC_PATH`) | **Yes, with caveats** | Grep for `^NAME\s*=` or `NAME:` in `config/settings_base.py` / `config/settings_dev.py` / `config/settings_prod.py`, or import `django.conf.settings` and `hasattr()` after `DJANGO_SETTINGS_MODULE` is set | Medium. Standard Django/library settings (`SILENCED_SYSTEM_CHECKS`, `INSTALLED_APPS`) are never declared in FLS's own settings files (they're framework-level) — a naive "must appear in `settings_base.py`" check would false-positive on those. Needs an allowlist of framework settings, or a check against `django.conf.global_settings` too. |
| Migration name (`freedom_ls_content_engine.0017_alter_file_file`) | **Yes** | File-exists check against `<app>/migrations/<name>.py` | Low, once the `app_label.migration_name` → path mapping is right (app label may differ from the Python package directory name, as `freedom_ls_organisations` vs the `organisations` app shows elsewhere in the repo). |
| System-check id (`freedom_ls_deployment.E001`, `freedom_ls_reports.W001`) | **Yes** | Grep `checks.py` files repo-wide for `id="<the id>"` in a `CheckMessage`/`Error`/`Warning` construction | Low-medium. A *deleted* check (like `W001` in this very spec) is the case the check exists specifically to catch, and greps cleanly since the string simply stops appearing. The one wrinkle: a check id that is genuinely gone is sometimes *correctly* still named in prose describing history ("W001 is gone") — the check needs to tolerate a claim-of-absence, not just flag every mention. |
| Repo-relative file path (`env_example`, a template path, `print.css`) | **Yes** | `Path(...).exists()` | Low. The one subtlety in this spec: `upgrade_notes.md` itself pointed at
`spec_dd/2. in progress/prod_bucket_setup/env_example` (line 105) — a path that is *correct at
authoring time* but becomes wrong the moment `/finish_worktree` moves the spec directory to `spec_dd/3.
done/…`. A path check run before that move would pass; the same check run after it would need to know
the move happened, or it flags a false positive on every single spec. This is the same failure class
the sibling idea (`root-env-example-stale-after-prod-bucket-setup`) raises independently. |
| Management command name (`qa_create_rich_dashboard_learner`) | **Yes** | File-exists check under `**/management/commands/<name>.py`, or `manage.py help <name>` and check exit code | Low. |
| Template path (`learner_interface/course_form_complete.html`) | **Yes** | `Path(...).exists()` relative to an app's `templates/` dir | Low, same caveat as file paths generally. |
| Package name/version (`package==version` in `changed_packages`) | **Yes** | Parse `pyproject.toml` (or `uv.lock`) and confirm the name+version pins appear | Low-medium. Version pins drift naturally as `uv lock` re-resolves; a check would need to compare against the version *range* accepted, not an exact pin, or it will false-positive on routine dependency bumps unrelated to this feature. |
| npm package name/version (`changed_npm_packages`) | **Yes, if `package.json` exists in FLS itself** | Parse `package.json` | Same caveat as above. |
| "Breaking changes" / "Manual steps" prose accuracy (e.g. "the fallback is gone", "this is a hard requirement") | **No — needs judgement** | Nothing mechanical confirms a behavioural claim like "booting without this setting now raises" without actually running the scenario (an integration test, not a static check). | N/A |
| Whether a claim is *complete* (nothing new that should be mentioned is missing) | **No — needs judgement** | Absence-of-omission cannot be checked by grepping the notes; it requires comparing the notes against the diff again, which is closer to re-authoring than verifying. | N/A |

The practical implication: everything **nameable** (a symbol, a setting, an id, a path, a command, a
package) is cheap to verify mechanically and would have caught this exact bug — `resolves at all` is
a much lower bar than `still describes current behaviour correctly`, but it is also the bar this bug
tripped. The **prose correctness** of "why" and "what to do about it" stays a judgement call no matter
what guard is chosen.

## 6. Options for the guard

**(a) A re-verify step appended to `/update_upgrade_notes` itself.**
Cost: cheap to add (a few grep/import checks at the end of Step 3), but it only re-verifies *at
authoring time* — the same moment the notes are already known-correct in this case (line 3dc70cc7's
notes about `OverwritingFileSystemStorage` were accurate when written). **Would not have caught this
bug**, because the drift happened six commits *after* authoring, and this option only runs once, at
authoring.

**(b) A separate verification pass invoked at worktree-finish, after the last code commit.**
Cost: one more command (or one more step folded into `/sdd:finish_worktree`) that re-reads
`upgrade_notes.md`, extracts the nameable classes from §5's table, and mechanically checks each one
against the tree as it stands right before the spec directory moves to `done`. **Would have caught
this bug** — `752db66b` landed at 11:18, well before `c43a3381` (12:33, the `finish_worktree` commit),
so a check running at that point would find `OverwritingFileSystemStorage` unresolvable. This is the
natural point because it is the one place in the whole run order that is provably *after* every code
commit and *before* the spec is archived — no later step re-opens the spec directory once it's in
`done`. `finish_worktree.md` already has an analogous late gate (Step 2's "run unit tests" and Step 8's
"confirm git status clean"), so adding a mechanical content check is consistent with the command's
existing shape rather than a new kind of step.

**(c) A checkable list item added to the SDD `todo.md` template.**
Cost: nearly free (one more `- [ ] (user)` or `- [ ] (cmd)` line), but a manual `(user)` checkbox is
exactly the kind of soft gate that this bug already slipped past — nothing forced anyone to look at
`upgrade_notes.md` again during the seven-item PR review round, and a checklist item does not change
that incentive. If it were instead a `(cmd)` item that runs a mechanical check (i.e., this option
becomes a thin wrapper around (b) or (d)), it inherits their coverage; as a bare human reminder alone,
**it would not reliably have caught this bug** — the equivalent human step already existed implicitly
("review the upgrade notes" is even the very next unchecked line under section 11 in the actual
`todo.md`, and it stayed unticked through to `finish_worktree`).

**(d) A pytest test or pre-commit hook that parses SDD artifacts and asserts every dotted path
resolves.**
Cost: the most durable option — once written, it runs on every commit thereafter with no per-spec
setup, and it would catch drift **within** a spec's own PR review round, not just at the end.
`752db66b`'s own commit ("close the four storage-resolution gaps PR review found") already ran through
`pre-commit` (per `address_pr_review.md` Step 6) and got a clean pass despite deleting a class the
still-present `upgrade_notes.md` named — a hook of this shape would have failed that exact commit.
Trade-off: it needs to know which `.md` files under `spec_dd/2. in progress/` are "live" (to avoid
scanning `spec_dd/3. done/` archives, which legitimately describe classes/settings from whatever
commit they were true as of, at the time the spec was current — see the sample in §4, where notes for
old, closed specs are correctly *static history* rather than something that must track HEAD forever).
Getting that scope boundary right is the main design cost, not the checking logic itself, which is the
same table as (b).

**(e) Moving the authoring of the notes to the end of the flow.**
Cost: this is a workflow reshuffle, not a guard — it would require re-ordering
`README.md`'s numbered steps and every `todo.md` section number after "Upgrade notes." It reduces the
*window* in which drift can happen (authored right before `finish_worktree` instead of two-thirds of
the way through), but does not eliminate it: `address_pr_review.md` can still land a fix after the
notes are authored if a reviewer comments post-hoc, and nothing stops that same review round from
re-opening once more after this reordering. It also does not eliminate the *sibling* problem
(`env_example` going stale) since that one lives entirely outside `upgrade_notes.md`. Given "Don't
build functionality that is not explicitly requested," a full reorder is disproportionate to what (b)
or (d) already buys more cheaply and without touching every spec's step numbering.

**Recommendation shape (not a decision — for the option-comparison the task asked for):** (b) and (d)
are the two options that actually intersect the moment this bug happened (post-authoring, pre-archive,
inside PR review), and they share the same underlying check table from §5 — (d) is (b)'s logic run
continuously via pre-commit/pytest instead of once at worktree-finish. (a) alone provably would not
have caught this bug since the notes were correct when (a) would have run. (c) alone is a no-op
restatement of a step that already existed and already failed to prevent this. (e) treats the symptom
(late authoring) rather than the cause (nothing re-verifies after authoring, regardless of when
authoring happens).

**Compatibility with the sibling idea.** `spec_dd/1. from concrete implementation/root-env-example-stale-after-prod-bucket-setup/idea.md`
proposes "a checklist item in `/update_upgrade_notes`" for a *different* artifact
(`.env.example`) going stale relative to a spec's own `env_example` template — structurally the same
"authored once, never re-verified before archive" problem, but for a file that lives at the repo root
rather than inside `upgrade_notes.md`. A guard shaped as (b) (a worktree-finish verification pass) is
the natural place both ideas converge: it can check "does the root `.env.example` reflect what this
spec's `env_example`/`upgrade_notes.md` claims" in the same pass as "does every dotted path in
`upgrade_notes.md` still resolve," rather than each idea inventing its own separate checklist
mechanism. A guard shaped as (c) alone (independent checklist items in each idea's fix) would instead
produce two near-duplicate manual review steps with the same failure mode as the one that already
missed this bug.

---

status: ok
