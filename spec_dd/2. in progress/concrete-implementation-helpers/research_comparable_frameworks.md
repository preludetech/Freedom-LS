# Research: How Comparable Frameworks Handle Downstream Projects

This document surveys how extensible/embeddable web frameworks structure "build-on-top-of-us"
projects and keep those projects in sync with upstream. The goal is to extract transferable lessons
for the Freedom Learning System (FLS) which is installed into downstream Django projects as a git
submodule with an editable pip install.

---

## 1. Wagtail

### The Two-Project Model: BakeryDemo vs. Starter Templates

Wagtail maintains a sharp distinction between its **reference demo** and its **starter templates**:

- **bakerydemo** ([GitHub](https://github.com/wagtail/bakerydemo)) is explicitly an *educational*
  resource, intended for developers who want to understand Wagtail's internals. The README states it
  is "not recommended as a starting point for your own site" and is "aimed primarily at developers
  wanting to learn more about the internals of Wagtail." Its role is to demonstrate common patterns
  and recipes, not to be a forkable foundation.

- **`wagtail start` project template** is the scaffolding entry point for new projects. Running
  `wagtail start mysite` generates a minimal Django project with a `home/` app, `search/` app,
  split settings (`base.py`, `dev.py`, `production.py`, `local.py`), base templates, and Docker
  config. Reference: [Wagtail project template docs](https://docs.wagtail.org/en/stable/reference/project_template.html).

- **Custom starter templates** can be passed via `--template=<URL>`. The news-template
  ([GitHub](https://github.com/wagtail/news-template)) is a production-ready example: it ships with
  Tailwind, Webpack, Sass, Fly.io deployment config, and content models for a news site. The
  philosophy is "deploy it as-is, or use it as a stable foundation." Wagtail explicitly encourages
  anyone to publish their own templates. Reference: [Wagtail starter kit blog post](https://wagtail.org/blog/new-starter-kit-for-wagtail-cms/).

**Key design choice:** once the `wagtail start` command is run, the generated project is fully
independent. There is no ongoing sync mechanism between the generated project and the template
source. Downstream projects are expected to pip-install `wagtail` at a pinned version and upgrade
through Wagtail's published upgrade path.

### Upgrade and Deprecation Policy

Wagtail publishes quarterly minor releases and patch releases for bugs and security. Its deprecation
policy: a feature deprecated in version N continues to work in N and N+1 (emitting warnings), and
is removed in N+2. Reference: [Wagtail upgrading docs](https://docs.wagtail.org/en/stable/releases/upgrading.html).

**Practical upgrade guidance for downstreams:**

- Upgrade one feature release at a time; do not skip versions.
- Make a database backup before upgrading.
- Read the "Upgrade considerations" section in each release's notes.
- Turn on Python deprecation warnings (`-Wa` or `PYTHONWARNINGS=default`) to catch ahead-of-time warnings.
- Downstream packages (third-party Wagtail apps) frequently lag a version or two; maintainers recommend filing issues or contributing patches.

**Change communication channels:** Wagtail uses a public roadmap, a release schedule wiki page, RC
releases 2-3 weeks before final, a newsletter ("This Week in Wagtail"), a Slack workspace, and
comprehensive release notes per-version. Reference: [Keeping up with Wagtail changes](https://wagtail.org/blog/keeping-up-with-upcoming-changes-in-wagtail/).

**Automation discussion (emerging):** As of 2025-2026, the Wagtail team is actively discussing
AI-assisted upgrade automation: structured release notes in `llms.txt` format, skills/SOPs for
agents, and linting rules generated from release notes (using tools like `django-upgrade`). The
finding: "I get much better results when I interpret the release notes and describe the checks to
create" — raw LLM generation from release notes underperforms human-guided check generation.
Reference: [Wagtail automating upgrades discussion](https://github.com/wagtail/wagtail/discussions/13902).

**A concrete example of downstream breakage (Wagtail 6.2):** report templates had their block
names renamed (`listing` to `results`, `no_results` to `no_results_message`), and
`template_name` attribute renamed to `results_template_name`. Any downstream project that
customised reporting templates had to manually locate and apply these renames — they are not
automatable without reading the release notes.

---

## 2. Saleor

### Architecture: API-First, Not Embeddable

Saleor takes a fundamentally different approach: it is a **headless, composable** platform. The
three components — core GraphQL API, Dashboard, and Storefront — are **separate repositories** that
communicate over HTTP/GraphQL rather than being installed into each other.

- **saleor-platform** ([GitHub](https://github.com/saleor/saleor-platform)) is a Docker Compose
  orchestrator that wires all three together for local development. It is explicitly "not meant to
  be deployed in any production environment" — it is a developer convenience, not a template.

- **saleor/storefront** ([GitHub](https://github.com/saleor/storefront)) is a Next.js/React
  reference storefront. Downstream teams fork it and customise it. With 820+ forks, it sees heavy
  community-driven divergence.

### How Downstreams Extend Saleor

Saleor's extension model is **API-level, not code-level**:

- Webhooks, metadata, attributes, and Saleor Apps (separate microservices) handle custom business
  logic without forking the core.
- 45+ mount points in the Dashboard allow custom tool integration without forks.
- A JavaScript SDK facilitates storefront customisation.

Critically: Saleor **discourages forking the core backend**. The documentation steers towards
plugins and Saleor Apps. FAQ: "If you would like to use other tax providers, you will need to
create a Saleor App" — not a fork. Reference: [Saleor FAQ](https://docs.saleor.io/docs/3.x/developer/community/faq).

### Downstream Sync Strategy

Because the core is pip-installed (or pulled via Docker image tag), downstream projects track
updates by bumping a version number in `docker-compose.yml` or `requirements.txt`. There is no
formal sync mechanism for forked storefronts; teams that fork saleor/storefront must manually pull
upstream or rebase. The project notes database migration issues during version upgrades and
encourages filing tickets for migration bugs. Reference: [Saleor Docker Compose docs](https://docs.saleor.io/setup/docker-compose).

**Lesson from Saleor:** The cleanest downstream model is one where the framework core is
*pip-installable at a version* (not forked), and customisation happens through documented extension
points (hooks, plugins, apps, API layers). Forks of any kind create a permanent maintenance burden
because the downstream must manually absorb every upstream change.

---

## 3. Django-Oscar

### Scaffolding: The Sandbox and the Fork Model

Django-oscar's reference project is the **sandbox** — a minimal Oscar installation with everything
in default state, used for development and exploration but not for production. Downstreams do not
start from the sandbox; they pip-install oscar into a fresh Django project.

Oscar's primary customisation mechanism is **app forking** via a management command:

```bash
./manage.py oscar_fork_app order yourappsfolder/
```

This creates a local app with the same Django app label that overrides Oscar's version in
`INSTALLED_APPS`. The generated structure includes `admin.py`, `app.py`, `models.py`, and a
migrations directory — essentially a local copy of the Oscar app that the developer can modify.
Class overrides are done by importing Oscar's class and extending it, then registering the
override through Oscar's dynamic class-loading mechanism. Reference:
[Oscar customisation docs](https://django-oscar.readthedocs.io/en/latest/topics/customisation.html),
[Oscar fork app docs](https://django-oscar.readthedocs.io/en/3.1/topics/fork_app.html).

### Pain Points: Migrations Are the Core Problem

Oscar's fork model is powerful but creates a severe upgrade problem around migrations:

**Scenario 1 (No model changes):** If you forked an Oscar app but did not change models, you must
manually copy Oscar's new migration files into your local app on each upgrade. This preserves data
migrations and avoids dependency errors.

**Scenario 2 (Model changes):** You have now permanently diverged from Oscar's migration tree.
Every Oscar release requires:

1. Review all new Oscar migrations manually.
2. For schema migrations: create equivalent migrations in your local app, possibly creating empty
   placeholder migrations with matching names to satisfy Oscar's dependency references.
3. For data migrations: manually replicate the `RunPython` operations, carefully ordering
   dependencies.

**Concrete failure mode:** "You will get dependency errors because new Oscar migrations reference a
migration you don't have." The only fix is creating empty migrations with matching names.
Reference: [Oscar upgrading docs](https://django-oscar.readthedocs.io/en/latest/topics/upgrading.html),
[community discussion: migrating forked order app](https://groups.google.com/g/django-oscar/c/2GL2XGHRcwM).

**Another concrete failure:** when a forked `catalogue` app diverges in migration names, promotions
and other Oscar packages that reference `catalogue` by migration name break entirely. Reference:
[django-oscar-promotions migration issue](https://github.com/django-oscar/django-oscar-promotions/issues/4).

**Summary of Oscar's lesson:** The fork-app model is the most invasive customisation strategy.
Every fork is a commitment to permanent manual migration management on every upstream release. The
Oscar docs acknowledge this with: "Please also carefully read the release notes; tricky migrations
will usually be mentioned" and recommend consulting the community mailing list for hard cases.

---

## 4. Cookiecutter-Django and Scaffolding Mechanisms

### Cookiecutter: Flexible Scaffolding with No Built-in Sync

**cookiecutter-django** ([GitHub](https://github.com/cookiecutter/cookiecutter-django)) is a
framework for generating production-ready Django projects from a template. It uses the Jinja2-based
cookiecutter CLI, prompt-driven (`cookiecutter.json`), and supports `pre_gen_project` and
`post_gen_project` hooks for setup tasks.

**Key tradeoff:** Cookiecutter is powerful for initial generation (it can express combinatorial
option sets that GitHub template repos cannot), but the generated project is a **snapshot** with no
built-in way to pull in upstream template improvements.

### GitHub Template Repos: Simpler but Less Powerful

GitHub template repositories are ordinary repos marked as templates. "Use this template" generates
a new repo with the same files. Limitations:
- Cannot accept parameters/prompt for configuration (unlike cookiecutter's `cookiecutter.json`).
- No combinatorial options: cookiecutter-django maintainers rejected conversion to GitHub templates
  specifically because "you cannot pass parameters and handle the multitude of combinations."
- Reference: [cookiecutter-django template repo discussion](https://github.com/cookiecutter/cookiecutter-django/discussions/3463).

**However**, for simpler cases (few or no configuration variants), GitHub template repos are
significantly easier to reason about and require no CLI tooling.

### The Sync Problem and Cruft

Cookiecutter has no sync mechanism. The community solution is **Cruft**:

- Cruft stores a `.cruft.json` at the project root containing the git commit hash of the template
  at generation time.
- `cruft update` diffs the current template state against the stored commit and proposes changes.
- `cruft check` validates whether a project is at the latest template version.
- `cruft diff` shows what diverged locally from the template.
- Can be automated via GitHub Actions (weekly cron, auto-PR on template changes).
- Reference: [Cruft docs](https://cruft.github.io/cruft/),
  [Cruft intro](https://timothycrosley.com/project-6-cruft).

**Cruft's fundamental limitation:** Conflicts are harder than standard git merges because there is
no common ancestor, so 3-way merges are impossible. In practice, teams that diverge heavily from
the template tend to abandon `cruft update` runs when they hit too many conflicts. Reference:
[Drawbacks of Cookiecutter with Cruft](https://ddumont.wordpress.com/2025/02/06/drawbacks-of-using-cookiecutter-with-cruft/).

**The expert recommendation from that analysis:** treat templates as one-time scaffolding, keep
template logic minimal, and move shared functionality into separately versioned *libraries* (pip
packages). This shifts "template sync" to "version bump in requirements.txt" — a much more
tractable problem.

### Alternative: Git-Based Template Branch Pattern

Before Cruft existed, the community designed a git-based workflow (described in
[cookiecutter issue #784](https://github.com/cookiecutter/cookiecutter/issues/784)):

1. A `template` branch in the generated project repo contains only the cookiecutter-rendered
   output, with no project-specific changes.
2. `.cookiecutter.json` in the project root records the original rendering context.
3. When the template updates, re-render into a temporary worktree checkout of `template`, commit,
   then merge `template` → `main`, resolving conflicts as normal git merges.

This leverages git's merge infrastructure and provides a common ancestor — avoiding Cruft's
3-way-merge limitation. The tradeoff: more manual setup, requires discipline to keep the `template`
branch clean.

---

## 5. Git Submodule + Editable Install: The FLS Pattern

### How It Works

FLS uses a pattern where the upstream framework is included as a **git submodule** (not a pip
package from PyPI) and installed in editable mode (`pip install -e ./freedom_ls/` or via `uv`).
This gives the downstream project:

- Full source access to FLS (for reference/reading, not editing).
- A pinned commit reference: the submodule SHA tracks exactly which FLS version is in use.
- Editable install semantics: no reinstall required during development.

This pattern is documented and workable: [Using Git Submodule and Develop Mode to Manage Python
Projects](https://shunsvineyard.info/2019/12/23/using-git-submodule-and-develop-mode-to-manage-python-projects/).

### Submodule Update Workflow

Pulling upstream FLS updates into a downstream project:

```bash
# Inside the submodule directory
git fetch origin
git checkout <new-tag-or-sha>

# Back in the host project
git add freedom_ls/
git commit -m "Bump FLS to v1.2.3"
```

The host project must record the new SHA in a separate commit. Two-repo discipline is required:
push the submodule update first, then push the host project update. Forgetting step 1 leaves
collaborators unable to fetch the referenced commit. Reference:
[Mastering Git submodules](https://medium.com/@porteneuve/mastering-git-submodules-34c65e940407).

### Submodule Pain Points

The most frequently reported problems with submodules in production codebases:

1. **Silent regressions from forgotten update step:** `git pull` on the host repo updates the
   gitlink but does not checkout the new submodule code unless `git submodule update --init
   --recursive` is also run. Missing this step means developers unknowingly work with stale
   submodule code, and their next commit silently pins back to the old SHA.

2. **Mandatory post-clone setup:** Every fresh clone requires `git clone --recurse-submodules` or
   a subsequent `git submodule update --init --recursive`. Undocumented setup steps are a
   consistent onboarding friction point.

3. **Branch-switching orphaned files:** switching branches where a submodule appears/disappears
   leaves files on disk as untracked, causing `unable to rmdir` errors.

4. **Duplication at scale:** multi-level submodule dependency trees (A depends on B which depends
   on C) can result in multiple copies of the same submodule; one report documented 6 copies of the
   same submodule in one repo.

5. **CLAUDE.md constraint (FLS-specific):** The spec explicitly states "Claude should not make
   edits to the freedom_ls submodule, it's only there as a reference." This requires clear
   documentation and/or a `.claude` or `.claudeignore` mechanism to prevent AI-assisted editing of
   the submodule directory.

References:
[Reasons to avoid git submodules](https://blog.timhutt.co.uk/against-submodules/),
[Git submodules comprehensive guide](https://devtoolbox.dedyn.io/blog/git-submodules-complete-guide),
[Git Book: Submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules).

### GitHub Actions for Submodule Sync

The **actions-template-sync** GitHub Action (mentioned in the template-sync context) can be adapted
for submodule-based repos: a scheduled action can check whether the FLS submodule is behind the
upstream main/tag and open a PR in the downstream project. Reference:
[GitHub templates and repository sync](https://0xdc.me/blog/github-templates-and-repository-sync/).

---

## 6. Cross-Cutting Patterns and Pain Points

### The Fundamental Tension

Every framework in this survey faces the same tension:

- **Deep integration** (forking, submodules, file-level overrides) enables maximum customisation
  but makes upstream absorption manual and error-prone.
- **Shallow integration** (API-level extension, pip version pins, plugin hooks) constrains
  customisation but makes upgrades mechanical (version bump + run migrations).

Oscar's fork-app model sits at the deep end: powerful but migration-management intensive. Saleor's
app/webhook model sits at the shallow end: constrained but upgrade-trivial. Wagtail sits in the
middle: pip-install the package, override templates and hooks, but avoid deep model forking.

### Scaffolding Mechanism Comparison

| Mechanism | Customisation power | Sync story | Good for |
|-----------|-------------------|------------|---------|
| Cookiecutter template | High (prompts, hooks) | Manual or Cruft (fragile) | One-time scaffold with many variants |
| GitHub template repo | Low (no params) | actions-template-sync (PR-based) | Simple scaffold, few variants |
| `wagtail start --template=URL` | Medium (Jinja vars in template) | None (pip upgrade) | Domain-specific starter kits |
| Git submodule + editable install | High (full source access) | Manual SHA bump + submodule update | Frameworks that aren't on PyPI |
| Pip version pin | Low (package API only) | `pip install --upgrade` + CHANGELOG | Stable, well-packaged libraries |

### What Frameworks Do Well

- **Wagtail:** clear separation between demo (educational) and starter template (production);
  systematic deprecation policy with advance warnings; per-release "upgrade considerations" section;
  multi-channel communication (newsletter, RC releases, Slack).

- **Django-Oscar:** `oscar_fork_app` management command automates local override scaffolding;
  detailed upgrade documentation per scenario; honest acknowledgement that migration handling for
  forked apps is hard and requires manual review.

- **Cruft/Cookiecutter ecosystem:** `.cruft.json` as a machine-readable record of template origin
  and context; `cruft check` for CI-based staleness detection; automated PR creation via GitHub
  Actions.

### Common Pain Points Downstream Users Report

1. **Migration divergence** (Oscar, any model-forking approach): the single largest source of
   upgrade pain. When downstream models diverge from upstream models, every upstream migration must
   be manually reviewed and ported.

2. **Template/block name renames** (Wagtail): renamed template blocks or template file paths
   silently break downstream template overrides with no error until the affected page is rendered.

3. **Submodule onboarding friction** (all submodule users): `git clone` without `--recurse-submodules`
   leaves an empty submodule directory. Many developers encounter this only after mysterious import
   errors.

4. **One-time scaffolding trap** (Cookiecutter): generated projects diverge from the template
   immediately; upstream improvements to the template (security fixes, new best practices) never
   reach generated projects unless actively applied. Cruft helps but conflicts are harder than git
   merges.

5. **Ownership ambiguity** (Cruft/template pattern): when the template provides code that the team
   also edits, it is unclear who "owns" that code and whether to accept or reject template updates.

---

## 7. Recommendations for FLS

### (a) The Separate Template Repo

**Use a GitHub template repo (not Cookiecutter) for the initial scaffold.** The FLS concrete
implementation spec describes a small number of variant concerns (theme, config, icons, optional
extra Django apps). A GitHub template repo is simpler to reason about, requires no CLI tooling, and
is sufficient for this variant space. Cookiecutter is justified only when the number of
configuration combinations is large; for FLS it is not.

**Structure the template repo with a clean split:**
- The `freedom_ls/` directory is the submodule (read-only by convention and enforced by
  CLAUDE.md).
- All downstream code (apps, templates, config, static) lives outside `freedom_ls/`.
- A `CLAUDE.md` in the repo root explicitly states that the submodule directory is off-limits for
  AI-assisted editing.

**Include a `UPGRADING.md` from day one.** Wagtail's practice of "upgrade considerations" per
release is the clearest transfer from the research. Every FLS release that changes migrations,
template hook names, or settings should ship a UPGRADING.md section documenting exactly what
downstream projects must change.

**Include a post-clone setup script or Makefile target.** The submodule onboarding problem
(empty directory on plain `git clone`) is solved by documenting `git clone --recurse-submodules`
prominently, and providing a `make setup` or `uv run setup_fls` command that runs
`git submodule update --init --recursive` and then `uv sync`.

### (b) Keeping Downstreams in Sync with FLS

**FLS should never force migration divergence.** The Oscar migration pain point is the clearest
warning sign. FLS should be designed so that downstream projects never need to fork FLS's migration
files. Custom models in concrete implementations should live in separate downstream apps, not as
overrides of FLS models. This keeps FLS migrations owned entirely by FLS, and concrete
implementation migrations owned entirely by the downstream.

**Tag FLS releases and use the submodule SHA as the version pin.** A concrete implementation's
`git log` should show entries like "Bump FLS to v1.2.3" whenever the framework is upgraded. This
gives downstream maintainers a clear audit trail and makes rollback straightforward.

**Provide a management command (or documented workflow) for FLS bumps.** Borrowing from Oscar's
`oscar_fork_app` pattern, FLS could ship a management command like `fls_check_upgrade` that:
1. Reads the currently pinned FLS submodule SHA.
2. Fetches the latest FLS tags.
3. Outputs the UPGRADING.md sections for each version between current and latest.
4. Warns about any known breaking changes that affect the detected downstream configuration.

**Consider a GitHub Action in the template repo that opens PRs when FLS has new tags.** This
follows the actions-template-sync pattern. A weekly action checks whether the FLS submodule is
behind the upstream `main` or latest tag and, if so, opens a PR in the concrete implementation
repo with the changelog content in the PR body. This shifts the burden from "will I remember to
check for updates" to "I have a PR to review."

**Keep template logic minimal; push functionality into FLS itself.** The Cruft research finding
applies here: the more logic lives in the template repo (rather than in FLS proper), the harder
sync becomes. Aim for the template repo to contain only project-specific glue — settings,
`INSTALLED_APPS` wiring, a base theme template, and entry-point URLs. Everything reusable should be
in FLS.

---

## Reference URLs

- [Wagtail bakerydemo GitHub](https://github.com/wagtail/bakerydemo)
- [Wagtail demo site docs](https://docs.wagtail.org/en/stable/getting_started/demo_site.html)
- [Wagtail project template reference](https://docs.wagtail.org/en/stable/reference/project_template.html)
- [Wagtail upgrading docs](https://docs.wagtail.org/en/stable/releases/upgrading.html)
- [Wagtail starter kit blog post](https://wagtail.org/blog/new-starter-kit-for-wagtail-cms/)
- [Wagtail keeping up with changes blog](https://wagtail.org/blog/keeping-up-with-upcoming-changes-in-wagtail/)
- [Wagtail automating upgrades discussion](https://github.com/wagtail/wagtail/discussions/13902)
- [Wagtail news-template GitHub](https://github.com/wagtail/news-template)
- [Saleor Core GitHub](https://github.com/saleor/saleor)
- [Saleor storefront GitHub](https://github.com/saleor/storefront)
- [Saleor platform GitHub](https://github.com/saleor/saleor-platform)
- [Saleor FAQ docs](https://docs.saleor.io/docs/3.x/developer/community/faq)
- [Django-oscar customisation docs](https://django-oscar.readthedocs.io/en/latest/topics/customisation.html)
- [Django-oscar fork app docs](https://django-oscar.readthedocs.io/en/3.1/topics/fork_app.html)
- [Django-oscar upgrading docs](https://django-oscar.readthedocs.io/en/latest/topics/upgrading.html)
- [Oscar migration issue: forked order app](https://groups.google.com/g/django-oscar/c/2GL2XGHRcwM)
- [django-oscar-promotions migration dependency issue](https://github.com/django-oscar/django-oscar-promotions/issues/4)
- [Cookiecutter-django GitHub](https://github.com/cookiecutter/cookiecutter-django)
- [Cookiecutter-django template repo discussion](https://github.com/cookiecutter/cookiecutter-django/discussions/3463)
- [Cookiecutter update issue #784](https://github.com/cookiecutter/cookiecutter/issues/784)
- [Cruft docs](https://cruft.github.io/cruft/)
- [Cruft GitHub](https://github.com/cruft/cruft)
- [Drawbacks of Cookiecutter with Cruft](https://ddumont.wordpress.com/2025/02/06/drawbacks-of-using-cookiecutter-with-cruft/)
- [GitHub templates and repository sync (actions-template-sync)](https://0xdc.me/blog/github-templates-and-repository-sync/)
- [Reasons to avoid git submodules](https://blog.timhutt.co.uk/against-submodules/)
- [Git Book: Submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [Mastering Git submodules (Medium)](https://medium.com/@porteneuve/mastering-git-submodules-34c65e940407)
- [Git submodule + develop mode for Python projects](https://shunsvineyard.info/2019/12/23/using-git-submodule-and-develop-mode-to-manage-python-projects/)

status: ok
