# Research: downstream inheritance, linking, and overriding of `qa_whole_system/` plans

## 1. How the FLS→downstream relationship actually works today

**Conclusion.** FLS sits inside a downstream ("concrete") project as a read-only git submodule at
`submodules/Freedom-LS`. Nothing downstream can write there without dirtying the submodule's working
tree, and the downstream's own `.claude/settings.json` denies `Write`/`Edit` on `submodules/**` by
convention (`claude_plugins/fls-dev/resources/template_repo_manifest.md:31`). Every existing
FLS→downstream mechanism (`/fls-dev:update_fls`, the conformance suite, `upgrade_notes.md`) is built
around this constraint: FLS ships signals and shared code that downstream *reads and calls into*, and
the downstream's own artifacts always live in the downstream's own tree, never inside the submodule.
This is the load-bearing fact for every design question below.

### The submodule-advance flow (`/fls-dev:update_fls`)

`claude_plugins/fls-dev/commands/concrete/update_fls.md` advances `submodules/Freedom-LS` one
completed spec at a time (chronological order, one commit per spec: `Update FLS: <spec-name>`). For
each spec it reads `submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md` — a
YAML-frontmatter file with machine-readable flags (`requires_migrations`, `requires_template_review`
+ `changed_template_paths`, `requires_settings_change` + `changed_settings`,
`requires_package_upgrade` + `changed_packages`, `requires_npm_install` + `changed_npm_packages`,
`requires_tailwind_rebuild`) — and runs only the integration steps the flags call for (§3e). If a spec
predates `upgrade_notes.md`, the command falls back to prose-inference from `1. spec.md` / `2. plan.md`
/ the diff.

**Template-drift detection (§3f)** is the closest existing precedent for "how do we know an inherited
artifact went stale": for each path in `changed_template_paths`, the command checks whether the
downstream ships its own override at the *same template path*. If it does, that override's upstream
source changed underneath it — the command **flags it for human review and does not auto-merge**
("re-applying customisations is a human decision", `update_fls.md:88`). This is a per-path,
flag-driven staleness check keyed off a list FLS itself authors at spec-completion time — not a
content hash and not a diff against the submodule. Section 3 below argues the QA-plan drift problem is
structurally the same and should reuse this pattern.

The command also has a durable **rollback procedure**: reset the submodule pointer to the last
`Update FLS: <spec>` commit via `git submodule update --init`, re-sync dependencies, and re-verify
(`update_fls.md:162–188`).

### The template repo (`/update_template_repo`, `template_repo_manifest.md`)

`claude_plugins/fls-dev/commands/update_template_repo.md` is the **upstream** counterpart: it edits a
*separate* git repository (`freedom-ls-concrete-template`, a GitHub Template Repository) that new
concrete projects are created from via "Use this template" (chosen specifically because it preserves
the `.gitmodules` submodule pointer — cookiecutter and clone-then-rename do not,
`template_repo_manifest.md:9–11`). `claude_plugins/fls-dev/resources/template_repo_manifest.md` is the
manifest: it lists the scaffold's file tree (`config/`, `apps/project_setup/`, `themes/custom/`,
`submodules/Freedom-LS/`, etc.) and, critically, a **"What must be absent"** exclusion table
(`template_repo_manifest.md:251–266`) — FLS-internal dev-only items (`freedom_ls.qa_helpers`,
`FORCE_SITE_NAME = "DemoDev"`, the DemoDev role module, FirstClass demo branding, the demo
`"regulation"` admonition) that must never be copied into a concrete scaffold. This table is the
existing precedent for "some of what FLS ships is FLS-internal and must not propagate downstream" —
the QA-plan equivalent is: FLS's own demo-content-coupled or brand-coupled QA plans (if any) must not
be blindly copied either.

`update_upgrade_notes.md` (`claude_plugins/fls-dev/commands/update_upgrade_notes.md`) is what
*produces* `upgrade_notes.md`: run at spec-completion time, it reads the spec/plan/diff and writes the
frontmatter block above plus prose "Breaking changes" / "Manual steps" sections. It is the structured
artifact `update_fls` consumes — the schema is defined once, in this file.

### The conformance suite (`freedom_ls/contrib/conformance/`) — the direct analogue

This is FLS's existing shared-test-suite mechanism, and it is architecturally the closest thing to
what a shared `qa_whole_system/` needs to become. Its shape:

- `freedom_ls/contrib/conformance/__init__.py` re-exports named pytest functions
  (`test_fls_namespace_reverses`, `test_reference_url_reverses`,
  `test_configured_backend_instantiates`, `test_active_theme_resolves`,
  `test_active_icon_set_resolves`, `test_migration_state_consistent`) plus a `drop()` function, with a
  documented **two opt-in forms**:
  ```python
  from freedom_ls.contrib.conformance import *          # simple, all six run
  # or, collision-safe (recommended):
  from freedom_ls.contrib import conformance
  test_fls_namespace_reverses = conformance.test_fls_namespace_reverses
  ```
- `update_fls.md` §3i requires every concrete project to have a `tests/test_fls_conformance.py` doing
  exactly one of those two forms, and explicitly forbids binding a subset ("a silent false green — the
  probes you leave out simply never run", `update_fls.md:134`).
- What it covers: URL-namespace reversal for the routes FLS's own code depends on
  (`test_urls.py` — `learner_interface:dashboard`, `course_detail`, `educator_interface:interface`,
  etc., plus `sitemap`/`robots_txt`), that the configured backend for a pluggable setting instantiates
  (`test_settings.py`), that the active theme and icon set resolve (`test_theme.py`), and that the
  downstream's migration state is internally consistent (`test_migrations.py`). It is a **wiring**
  check, not a functional/UX check — it proves the downstream's settings, URLconf, and app config
  still satisfy FLS's own internal assumptions, not that any given page renders correctly. A
  `qa_whole_system/` plan is one level up: it verifies *behaviour*, which conformance deliberately does
  not attempt.
- **The `conformance.drop(...)` escape hatch** (`freedom_ls/contrib/conformance/_registry.py`,
  `test_urls.py:93`): probes are split into **contract-tier** (`contract=True` — routes other FLS code
  actually depends on, e.g. `dashboard`, `course_detail`) and **internal-tier** (`contract=False` —
  e.g. `learner_interface:courses`, a listing page a downstream commonly restyles or removes). Only
  internal-tier probes can be dropped: a downstream calls `conformance.drop("learner_interface:courses")`
  from its own `conftest.py` (never from the generated `tests/test_fls_conformance.py` file itself —
  `update_fls.md:119` explicitly forbids adding a `drop(...)` call there, because "dropping a probe is
  a downstream decision about a route that project has actually customised", not something the
  integration command should decide for it) and that probe is `pytest.skip`ped rather than removed —
  it stays visible in the run as a skip, not silently absent. Attempting to drop a contract-tier id has
  no effect; the probe body enforces the tier split by construction (only non-contract probes consult
  `_is_dropped`). **This is the direct analogue of "this plan does not apply to us."** A per-plan
  equivalent — a downstream marking a specific inherited QA plan (or a specific scenario within it) as
  "customised away, do not run upstream's version" — should follow the same shape: an explicit,
  downstream-authored declaration, visible in the run output as a deliberate skip rather than a missing
  file, and restricted to plans/scenarios FLS itself has marked droppable (the QA-plan equivalent of
  the contract/internal split) if some plans must never be silently opted out of (e.g. auth, security).

### Where FLS physically sits, and what that reaches

A downstream file can reach FLS's committed content at `submodules/Freedom-LS/<anything>` — e.g.
`submodules/Freedom-LS/spec_dd/3. done/<spec>/upgrade_notes.md` is read directly by path in
`update_fls.md`. The same mechanism means a downstream file can read
`submodules/Freedom-LS/qa_whole_system/<area>.md` directly, at whatever commit the submodule pointer
currently names. It **cannot** write there (denied by `.claude/settings.json`, and conceptually wrong
even if allowed — see §2's symlink discussion). The submodule pointer moves only when
`/fls-dev:update_fls` moves it (spec by spec) or Step 4's final sync runs; between those moves, the
downstream's view of `qa_whole_system/` is frozen at whatever spec was last integrated, which is
already coarser-grained than "the latest QA plan."

---

## 2. Link-versus-copy: recommendation

**Recommendation: neither a filesystem symlink nor a full-content copy. Use a short local stub file
that names the upstream path and declares "run unchanged", backed by a manifest/index that gives an
at-a-glance status per area — the same two-tier shape the conformance suite already uses (a bare
import for the common case, an explicit per-item form when something needs distinguishing). Do not use
`git subtree`, sparse checkout, or vendoring for this.**

### Filesystem symlink — rejected

A symlink `qa_whole_system/learner_experience.md -> ../submodules/Freedom-LS/qa_whole_system/learner_experience.md`
looks like the cheapest form of "link, not copy," but fails on every axis that matters here:

- **Git storage.** Git stores a symlink as a mode-`120000` blob whose content is the literal target
  path string, not the referenced file's bytes — so the symlink survives a normal Unix checkout, but
  it is genuinely a different kind of tracked object, and its behaviour is controlled by
  `core.symlinks`, not by anything the repo can enforce on its own. ([sqlpey.com](https://sqlpey.com/git/git-symlink-management-storage-checkout/), [Codemia](https://codemia.io/knowledge-hub/path/git_symbolic_links_in_windows))
- **Windows.** `core.symlinks` defaults to `false` on Windows unless the user has Developer Mode /
  `SeCreateSymbolicLinkPrivilege` enabled. When it is false, Git checks the symlink out as an ordinary
  small text file *containing the target path string* rather than a working symlink — so an agent (or
  a human) opening it on a Windows checkout reads a one-line path, not the plan content, with no error
  raised anywhere. ([sqlpey.com](https://sqlpey.com/git/git-symlink-management-storage-checkout/), [Codemia](https://codemia.io/knowledge-hub/path/git_symbolic_links_in_windows))
- **The submodule pointer moves underneath it.** The symlink target is a path *inside*
  `submodules/Freedom-LS`, whose content at that path is whatever the currently-checked-out submodule
  commit has there. `/fls-dev:update_fls` moves that pointer spec-by-spec (§1 above); a rename or
  removal of the target path between two pointer moves leaves the symlink dangling with no signal
  except a broken link the next reader happens to open. Nothing in the existing pointer-move flow
  checks that a downstream's symlinks (or stubs) still resolve.
- **The report-location problem is decisive on its own even ignoring the above two.** A QA agent
  executing a plan writes `qa_report.md` and `screenshots/` **beside the plan it ran** — that is the
  literal, established layout `/fls-dev:do_qa` already uses for spec QA plans (`do_qa.md`: `<spec-dir>`
  is "the directory containing that test plan... `qa_report.md` and `screenshots/` are written there").
  If the plan file itself is a symlink resolving into `submodules/Freedom-LS/qa_whole_system/`, "beside
  the plan" is **inside the submodule** — a read-only, `Write`/`Edit`-denied dependency
  (`template_repo_manifest.md:31`) that the downstream must never dirty. Every execution of an
  inherited plan would either fail outright (permission denied) or, if permissions were loosened to
  allow it, leave untracked artifacts inside a vendored dependency that the next `git submodule
  update` silently discards. This alone rules the symlink out regardless of the OS/git-storage
  concerns above.

### Stub markdown file — recommended for the per-area file

A short local file at `qa_whole_system/learner_experience.md` (in the downstream's own tree, not a
symlink) containing prose to the effect of: *"This area is covered unchanged by the upstream plan at
`submodules/Freedom-LS/qa_whole_system/learner_experience.md`. Run it as-is against this project's
environment."* An executing agent resolves this exactly as it already resolves any other path
reference in this ecosystem — by reading the named path (a relative path from the project root, the
same style `update_fls.md` already uses for `submodules/Freedom-LS/spec_dd/...`). The stub is real,
diffable, committed content: it survives Windows checkouts because it is an ordinary file, it survives
the pointer moving because resolution happens at run time (the agent reads whatever is at that path
*right now*, not a frozen copy), and — the point that rules out the symlink — the **report and
screenshots still land beside the stub, in the downstream's own tree**, never inside the submodule.
The stub is functionally identical to the conformance suite's `from freedom_ls.contrib.conformance
import *` line: a one-line declaration that says "this concern is not reimplemented here, go run the
upstream one."

### Manifest/index file — recommended as the top-level view, not a replacement for stubs

A single `qa_whole_system/INDEX.md` (or similar) listing every area with a status
(`inherited` / `overridden` / `not applicable` / `local-only`) gives an at-a-glance view of the whole
suite's inheritance state without opening N files, and is the natural place to record *why* a plan is
`not applicable` (the downstream-specific reason, analogous to a `conformance.drop()` call's implicit
justification). What it gives up: there is nothing to open and read locally for an `inherited` area —
a reader who wants to know exactly what is being tested has to follow the path into the submodule.
That is an acceptable trade *only if* every `inherited` row is still backed by a stub file at the
conventional per-area path (so an agent asked to "run the learner_experience QA plan" doesn't need the
index at all, just the stub) — i.e. the index is a convenience summary derived from the stubs'
existence, not the sole source of truth. Recommend: keep both. The index is generated/checked
mechanically from the presence and content of per-area files; the per-area stub or override is what an
executing agent actually opens.

### Git submodule-native options — none fit

- **Sparse checkout** narrows *what the submodule's own working tree materialises*, not what the
  downstream's own tree links to — it doesn't produce anything at `qa_whole_system/<area>.md` in the
  downstream at all, so it solves a different problem (reducing checkout size) and is orthogonal here.
- **`git subtree`** merges the *upstream repository's history and content* into the downstream repo —
  the opposite of "link rather than copy": it is copy-with-history, and it reintroduces the exact
  duplication problem the requirement is trying to avoid, at higher cost (the downstream's repo now
  carries FLS's QA-plan history too). It is the right tool for vendoring a third-party dependency you
  intend to *modify in place and never re-sync structurally* ([adam-p.ca](https://adam-p.ca/blog/2022/02/git-submodule-subtree/), [DataCamp](https://www.datacamp.com/tutorial/git-subtree)) — not for "point at an upstream file and re-read it live."
- **Vendoring** (copying the file in wholesale) is exactly the "making a copy" the idea explicitly asks
  to avoid for unchanged plans.

FLS already made this submodule-vs-subtree choice at the whole-project level (submodule, not subtree,
per `template_repo_manifest.md`'s "Use this template" rationale) precisely because a pointer that can
move independently, without duplicating history, is what the FLS→downstream relationship needs. The
same reasoning applies one level down to individual QA plans.

### Prior art

- **The conformance suite itself** is the strongest and most directly applicable precedent, and it
  already lives in this codebase (§1 above): shared, named, importable test objects in the upstream
  package; a downstream opts in with a one- or two-line local file; a registry-based `drop()` prunes
  the subset that's genuinely inapplicable, without touching the shared source. The recommended stub
  file is a markdown-flavoured restatement of the same idea — the difference is only that a QA *plan*
  is prose an agent reads and drives Playwright from, not a Python callable pytest collects, so "import"
  becomes "read this path and run it," and "collision-safe rebind" becomes "manifest row."
- **`cruft`** (built on Cookiecutter) tracks the **commit hash of the template at instantiation time**
  in a `.cruft.json` sidecar file in the generated project; `cruft diff` / `cruft update` use that
  recorded hash to compute what changed upstream since. ([cruft.github.io](https://cruft.github.io/cruft/), [GitHub](https://github.com/cruft/cruft)) This is the general pattern behind "detect drift against a recorded baseline" —
  see §3, where FLS already has a lighter-weight version of the same idea (`changed_template_paths` in
  `upgrade_notes.md`) that doesn't require a hash at all because the upstream repo itself declares what
  changed.
- **pytest's own abstract-test-suite idiom**: define a base class or a set of bare test functions in a
  shared module, mark it so pytest doesn't collect the base directly, and let a downstream module
  import/subclass/rebind it to make it collectible in its own suite ([pytest docs — unittest support](https://docs.pytest.org/en/7.1.x/how-to/unittest.html), [Adam Johnson — sharing common tests](https://adamj.eu/tech/2025/05/30/python-unittest-common-tests/)). This is exactly the shape `freedom_ls/contrib/conformance/__init__.py` already
  implements for Python tests, and it generalises cleanly to markdown QA plans via the stub-file
  mechanism above.
- **Django's own reusable-app testing guidance** centres on apps shipping their own test modules that a
  consuming project's test runner discovers by pointing `INSTALLED_APPS`/test discovery at the package,
  with `override_settings` for environment-specific values ([Testing reusable Django apps — Nicolas Le Manchet](https://lemanchet.fr/articles/testing-reusable-django-apps.html); settings-pattern discussion at [overtag.dk](https://overtag.dk/v2/blog/a-settings-pattern-for-reusable-django-apps/)) — the same "run the
  shared thing where it lives, parameterise the environment" shape, one more layer up the stack from
  the conformance suite.
- No WordPress/Drupal-specific "theme test inheritance" precedent was found that adds anything beyond
  the above; the general reusable-test-suite pattern is the operative one across ecosystems.

**FLS's conformance suite already follows the "shared source, thin local opt-in, registry-based drop"
model.** The recommendation for `qa_whole_system/` is to follow the same model at the markdown-plan
level rather than inventing a second mechanism.

---

## 3. What "customising" a plan means and where drift bites

**Conclusion.** A plan has exactly two kinds of content, and only one kind is a legitimate override.
Drift detection should reuse the `upgrade_notes.md` flag pattern (FLS declares what changed) rather
than a content-hash scheme (the downstream infers it) — because FLS already knows, at spec-completion
time, whether a given change touches a QA plan, the same way it already knows whether it touches a
template.

### Environment-specific vs behaviour-specific content

**Environment-specific** (must be parameterised, never hand-copied into a plan body): base URL,
credentials, site/domain names, which QA dataset/seed to load. These already have an established home
in this codebase: `.claude/fls-dev/config.md` carries "Base URL" and "Dev Credentials" today
(`config.md:1–9`), and `## QA Dev Data` there names the shell commands used to reset/seed data for
`/fls-dev:do_qa`. A plan that hardcodes `http://127.0.0.1:8000` or `demodev@email.com` in its body
cannot be inherited unchanged even when the *behaviour* it tests is identical — the parameterisation is
what makes "link rather than copy" possible at all. A plan needs, at minimum: the base URL, which
credentials to log in as (role, not literal secret), and which QA dataset/seed list to run against
(the idea's own §1–§2 already establishes a single `setup_qa_data` function and an environment
argument — dev vs stage — as the mechanism a plan's execution supplies these through, rather than the
plan file itself naming them).

**Behaviour-specific** (what the page should show, which elements exist, what a given action does) is
the only kind of content a downstream customisation should ever touch. A downstream with a different
learner dashboard genuinely needs a different `learner_experience.md` body describing *its* dashboard
— that is a real override, not environment drift.

### The drift problem, and the precedent that already solves an equivalent one

FLS updates `qa_whole_system/learner_experience.md`; a downstream copied it three months ago and never
notices. Three candidate detection mechanisms, evaluated:

- **Content hash recorded at copy time** (the `cruft`/`.cruft.json` model, §2) — works, but requires
  the downstream to maintain a sidecar state file per inherited plan and a tool to diff against it. It
  is general-purpose but re-derives, per plan, information FLS's own spec-completion workflow already
  has for free.
- **The `upgrade_notes.md` `changed_template_paths` / `requires_template_review` pattern — direct
  precedent, and the recommended mechanism.** `update_upgrade_notes.md` already requires every spec to
  declare, in machine-readable frontmatter, which template paths it touched
  (`update_upgrade_notes.md:17–18, 45`), and `update_fls.md` §3f already turns that declaration into a
  "flag every override for human review, do not auto-merge" step whenever the downstream has its own
  file at that same path. A `changed_qa_plan_paths` (or equivalent) entry in the same frontmatter block
  — populated whenever a spec's own `2. plan.md` or diff touches a `qa_whole_system/<area>.md` — gives
  `/fls-dev:update_fls` exactly the same signal it already uses for templates: for each changed path,
  check whether the downstream has an **overridden** (not inherited-stub) copy at that area, and if so,
  flag it for human review rather than silently continuing to serve stale prose. This needs no hash and
  no diff tool — FLS already knows what it changed, because it wrote the spec that changed it. An
  **inherited** (stub) area needs no such flag at all: the stub always resolves to the current upstream
  content, so it cannot drift by construction — that is the entire value of "link rather than copy"
  over "copy at a point in time." Drift is only possible for **overridden** areas, and this mechanism
  is exactly the one that already exists for templates, applied one directory over.
- **Diffing against the submodule at its recorded commit** — equivalent in spirit to the hash approach,
  but has no existing tooling in this codebase and, unlike the frontmatter-flag approach, cannot
  distinguish "this diff is a rewording" from "this diff changes behaviour a downstream override needs
  to re-examine" — exactly the reason `update_fls.md` §3f flags for **human** review rather than
  attempting to auto-merge template diffs. The same reasoning applies to plan diffs: a raw diff is
  strictly worse signal than an authored flag.

### Should an overridden plan still run the upstream one?

**No, by direct analogy with `conformance.drop(...)`.** A downstream that has overridden a plan has
made a deliberate declaration that its behaviour differs; re-running the upstream version alongside its
own would either double-report the same area or produce a false failure against behaviour the
downstream intentionally changed (the exact failure mode `conformance.drop()` prevents for
internal-tier route probes). The manifest/index (§2) should record the override as a visible,
deliberate substitution — the plan-level equivalent of `conformance.drop()`'s "skip, not silently
absent" behaviour — rather than the outcome being indistinguishable from "we forgot this area." Whether
any plan should be **un-droppable** (contract-tier, in conformance's vocabulary — e.g. an
authentication or data-isolation QA plan FLS considers non-negotiable even for a customised dashboard)
is a product decision this research does not resolve, but the conformance suite's contract/internal
split is the existing mechanism FLS would extend to express it.

---

## 4. Who runs what, and where the artifacts land

**Conclusion.** `qa_report.md` and `screenshots/` for an inherited plan must be written in the
downstream's own `qa_whole_system/` tree, at the same relative area path as the stub, never inside
`submodules/Freedom-LS`. This is not a new constraint to invent — it is the existing layout
`/fls-dev:do_qa` already uses for spec-directory QA plans, generalised.

`do_qa.md` establishes the precedent precisely: `<spec-dir>` is "the directory containing that test
plan[;] `qa_report.md` and `screenshots/` are written there" (`do_qa.md:20–22`), and screenshots are
moved from the Playwright server's fixed `qa-screenshots/` output directory into
`<spec-dir>/screenshots/` by a script that "validates that `<spec-dir>` is inside the project"
(`do_qa.md:350`) — an explicit guard against writing into anything that isn't part of the writable
project tree. Applied to `qa_whole_system/`: the plan being executed is the **stub** at
`qa_whole_system/<area>.md` in the downstream's own tree (§2), so "beside the plan" is automatically
inside the downstream, never inside the submodule — the report and screenshots for
`qa_whole_system/learner_experience.md` land at `qa_whole_system/learner_experience/qa_report.md` and
`qa_whole_system/learner_experience/screenshots/` (or whatever per-area subdirectory convention the
implementing spec settles on), exactly parallel to today's per-spec layout. This is the layout that
satisfies the constraint; the specific directory-naming convention is an implementation decision, not
a research finding.

### Environment supply

`.claude/fls-dev/config.md` (read by `/fls-dev:do_qa` today, `do_qa.md:26–30`) already carries
**Base URL** and **Dev Credentials**, and its `## QA Dev Data` section carries the non-interactive
shell commands used to reset/seed data (`config.md:10–22`). This is the existing convention for
supplying a plan's environment-specific parameters (§3) without hardcoding them in plan bodies — a
staging run would read the equivalent values from wherever the idea's environment-selection mechanism
(dev vs stage, per the idea's §4) resolves them, following the same file-based, non-interactive,
credential-out-of-band pattern `django-stack`'s own template (`claude_plugins/django-stack/templates/config.md`)
uses for its own dev credentials ("Never record a non-local credential here — this file is committed.
Machine-specific values belong in `.claude/ds/config.local.md`", `config.md:15`). `/fls-dev:init`
(`claude_plugins/fls-dev/commands/init.md`) is what creates `.claude/fls-dev/config.md` /
`config.local.md` for a new project (Steps 3–4) and installs the wrapper scripts `## QA Dev Data`
commands invoke — i.e. it is the existing bootstrap point a new "pull QA plans" flow would rely on
already being run, not a step it re-implements.

---

## 5. The plugin-distribution question

**Conclusion.** The new command is reachable from a downstream project today via the same route every
`fls-dev` command reaches a downstream: the downstream's `claude.sh` launches Claude with
`--plugin-dir` pointed at the checkout that holds `claude_plugins/` (its own copy of this repository,
resolved as `PLUGINS_ROOT` — normally `.` when the downstream *is* the FLS repo, but for a concrete
project it is wherever that project's own `claude_plugins/` checkout lives, per `init.md`'s
`PLUGINS_ROOT` resolution rule, `init.md:67–101`). `claude_plugins/fls-dev/commands/concrete/README.md`
confirms the intended location for downstream-only commands: "These commands are specifically for
concrete implementations of FLS. They typically include FLS as a submodule" — i.e.
`commands/concrete/` is not a distribution mechanism, it is a **scope label** inside the same
`fls-dev` plugin that also holds FLS-authoring commands. `update_fls.md` already lives there.

Distribution mechanics, concretely:

- The plugin itself (`claude_plugins/fls-dev/`, including `commands/concrete/`) is **not** duplicated
  into every concrete project's own tree. A concrete project's `claude.sh` wrapper points
  `--plugin-dir` at wherever its `PLUGINS_ROOT` resolves — which, per `init.md`'s own commentary, is
  most naturally the FLS submodule's own `claude_plugins/` directory for a project that vendors FLS as
  `submodules/Freedom-LS` (i.e. `submodules/Freedom-LS/claude_plugins`), though `init.md`'s rule
  explicitly refuses to assume or guess this — it only reads whatever value is already baked into
  `claude.sh` or a wrapper script, or falls back to `.` (`init.md`, "The `PLUGINS_ROOT` rule",
  step 3: "This is the only default, and it is the only candidate any init offers"). Concretely: the
  plugin tree a concrete project runs commands from is whatever checkout its `PLUGINS_ROOT` names —
  in the common case that is the FLS submodule's own copy of `claude_plugins/`, so `commands/concrete/`
  commands ship to every concrete project automatically the moment the submodule pointer advances,
  with no separate install step.
- There is no `.claude-plugin` marketplace manifest gating which commands within `fls-dev` a concrete
  project can see — `.claude-plugin/plugin.json` (`claude_plugins/fls-dev/.claude-plugin/plugin.json`)
  carries only `name`, `version`, and `description`; it does not enumerate or filter commands. Every
  command under `claude_plugins/fls-dev/commands/`, `concrete/` included, is available once the plugin
  is enabled (`"fls-dev": true` in `enabledPlugins`, set by `/fls-dev:init` Step 1) and the plugin
  directory is reachable via `--plugin-dir`.
- **Therefore**: the new "pull QA plans into a concrete implementation" command is reachable from a
  downstream exactly as `/fls-dev:update_fls` already is, provided it lives under
  `claude_plugins/fls-dev/commands/concrete/` in this repository — no new distribution channel, no
  marketplace registration, and no per-project install step beyond what `/fls-dev:init` already sets
  up. It becomes usable in an already-initialised concrete project the moment the submodule pointer
  advances past the commit that adds it (or, if a project's `PLUGINS_ROOT` points somewhere other than
  the submodule, the moment that separate checkout is updated).

---

## References

- [Git symlink storage and checkout behaviour — sqlpey.com](https://sqlpey.com/git/git-symlink-management-storage-checkout/)
- [Git symbolic links on Windows — Codemia](https://codemia.io/knowledge-hub/path/git_symbolic_links_in_windows)
- [`cruft` — template drift tracking via recorded commit hash](https://cruft.github.io/cruft/)
- [`cruft` GitHub repository](https://github.com/cruft/cruft)
- [Git Submodule vs Subtree — adam-p.ca](https://adam-p.ca/blog/2022/02/git-submodule-subtree/)
- [Git Subtree Explained — DataCamp](https://www.datacamp.com/tutorial/git-subtree)
- [pytest — how to use unittest-based tests (base-class collection)](https://docs.pytest.org/en/7.1.x/how-to/unittest.html)
- [Adam Johnson — sharing common tests in unittest](https://adamj.eu/tech/2025/05/30/python-unittest-common-tests/)
- [Testing reusable Django apps — Nicolas Le Manchet](https://lemanchet.fr/articles/testing-reusable-django-apps.html)
- [A settings pattern for reusable Django apps — overtag.dk](https://overtag.dk/v2/blog/a-settings-pattern-for-reusable-django-apps/)

## In-repo evidence

- `claude_plugins/fls-dev/commands/concrete/update_fls.md`
- `claude_plugins/fls-dev/commands/concrete/README.md`
- `claude_plugins/fls-dev/commands/update_template_repo.md`
- `claude_plugins/fls-dev/resources/template_repo_manifest.md`
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md`
- `claude_plugins/fls-dev/commands/init.md`
- `claude_plugins/fls-dev/commands/do_qa.md`
- `freedom_ls/contrib/conformance/__init__.py`
- `freedom_ls/contrib/conformance/_registry.py`
- `freedom_ls/contrib/conformance/test_urls.py`
- `.claude/fls-dev/config.md`
- `claude_plugins/django-stack/templates/config.md`
- `claude_plugins/fls-dev/.claude-plugin/plugin.json`

status: ok
