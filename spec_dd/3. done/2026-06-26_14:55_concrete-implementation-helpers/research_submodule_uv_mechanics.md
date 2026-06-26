# Research: Git Submodule + uv Mechanics for FLS Template Repo

**Context:** FLS is a Django LMS package. Downstream "concrete implementations" are fresh Django
projects that include FLS as a git submodule under `submodules/Freedom-LS`, installed editability
via `uv add submodules/Freedom-LS`. A template repo should scaffold this setup. This document
covers the mechanics needed to make that robust.

---

## 1. Current state (read from the codebase)

The existing `docs/how tos/incorperate into another project.md` describes a fully manual
bootstrapping sequence:

```
git submodule add git@github.com:preludetech/Freedom-LS.git submodules/Freedom-LS
uv add submodules/Freedom-LS
django-admin startproject config .
```

followed by manual settings wiring, Tailwind setup, conftest copying, etc. The `fls-claude-plugin`
`init.md` command automates the Claude-Code-specific bits (settings.json, wrapper scripts,
`.claude/fls/config.md`) but does **not** automate the git/uv bootstrapping above. The
`update_fls.md` command handles advancing the submodule pointer spec-by-spec and running
integration work.

Key observation: the wrapper scripts (`claude.sh`, `install_dev.sh`, `db_recreate.sh`, etc.) all
contain the placeholder `__FLS_PATH__` which the `fls:init` command replaces with the actual
relative path to FLS (defaulting to `submodules/Freedom-LS`). This mechanism is already in place
and working.

---

## 2. Git submodules: how they work, pitfalls, and best practices

### 2.1 How submodule pinning works

The parent repo's tree object stores a **gitlink** — a direct pointer to a specific commit SHA
in the submodule repo, not a branch name. This is what "pinning to a commit" means. When a
contributor runs `git pull` on the parent, they get the updated gitlink record, but the
submodule directory itself is **not updated automatically**. They must also run:

```
git submodule update --init --recursive
```

The `update_fls.md` command already models the correct pattern: `cd submodules/Freedom-LS && git
checkout <commit-hash>` followed by committing the parent pointer change.

References:
- [Git Book: Submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [Demystifying git submodules (cyberdemon.org, 2024)](https://www.cyberdemon.org/2024/03/20/submodules.html)

### 2.2 Detached HEAD — the primary gotcha

When `git submodule update` runs, Git checks out the pinned commit in the submodule directory,
leaving it in a **detached HEAD** state. This is intentional: the submodule is not on any branch.

The problem arises if someone accidentally starts editing files inside `submodules/Freedom-LS`:
any commits made there are not anchored to a branch and will be garbage-collected eventually by
git. They will also never be pushed to the FLS remote unless explicitly handled.

For the FLS case, the detached HEAD state is actually *correct and desirable*: no one should be
committing to `submodules/Freedom-LS` from inside a concrete project. The `update_fls.md`
command deliberately moves the pointer by checking out specific commits — this is the only
sanctioned way to advance the submodule.

References:
- [Git Submodule Detached HEAD Guide (copyprogramming.com)](https://copyprogramming.com/howto/git-submodules-still-with-detached-head)
- [Mastering Git Submodules (martinuke0.github.io, 2026)](https://martinuke0.github.io/posts/2026-04-01-mastering-git-submodules-a-comprehensive-guide-for-developers/)

### 2.3 Cloning correctly — downstream contributor footgun

The single most common footgun: a new contributor runs `git clone <repo>` and finds
`submodules/Freedom-LS` as an **empty directory**. This breaks everything silently. The fix is
either:

```bash
# Option A: at clone time
git clone --recurse-submodules <repo-url>

# Option B: after a plain clone
git submodule update --init --recursive
```

This must be documented prominently in the concrete project's README and/or enforced in the
`install_dev.sh` wrapper script. A post-clone check that exits with an error if the submodule
directory is empty is a good safety net:

```bash
if [ ! -f "submodules/Freedom-LS/pyproject.toml" ]; then
    echo "ERROR: FLS submodule not initialised. Run: git submodule update --init --recursive"
    exit 1
fi
```

References:
- [Git submodules best practices gist (slavafomin)](https://gist.github.com/slavafomin/08670ec0c0e75b500edbaa5d43a5c93c)
- [Working with submodules (GitHub Blog)](https://github.blog/2016-02-01-working-with-submodules/)

### 2.4 Updating the submodule pointer safely

The pattern described in `update_fls.md` is correct:

1. `cd submodules/Freedom-LS && git fetch origin main`
2. `git checkout <specific-commit-hash>` (not `origin/main` — pin to a known-good point)
3. Come back to the parent, `git add submodules/Freedom-LS`, and commit

Committing `submodules/Freedom-LS` alone (without a larger context commit) is a valid pattern.
The commit message should reference what changed in FLS (e.g. `Update FLS: <spec-name>`).

**Footgun**: running `git submodule update --remote` without thinking will advance the submodule
to the tip of its tracking branch, potentially skipping the spec-by-spec integration review that
`update_fls.md` mandates. Never use `--remote` for FLS submodule updates unless you've verified
all intervening specs.

### 2.5 Shallow clones in CI

For CI pipelines where build speed matters and history is not needed:

```bash
git clone --recurse-submodules --shallow-submodules --depth=1 <repo>
```

This fetches only the pinned commit of the submodule (depth=1), not its full history. Can also
be configured in `.gitmodules`:

```ini
[submodule "submodules/Freedom-LS"]
    path = submodules/Freedom-LS
    url = git@github.com:preludetech/Freedom-LS.git
    shallow = true
```

Note: shallow fetches are computationally more expensive server-side; for small teams this is
negligible, but worth noting.

References:
- [Get up to speed with partial clone and shallow clone (GitHub Blog)](https://github.blog/open-source/git/get-up-to-speed-with-partial-clone-and-shallow-clone/)
- [Git Submodules: The Complete Guide for 2026 (devtoolbox.dedyn.io)](https://devtoolbox.dedyn.io/blog/git-submodules-guide)

### 2.6 Merge conflicts on submodule pointer

If two branches both advance the FLS pointer to different commits, the merge will produce a
conflict on the gitlink entry. Resolve by picking the more recent of the two commits and staging
the submodule directory: `git add submodules/Freedom-LS`. Not a common scenario for FLS concrete
projects (they usually have one team), but worth knowing.

---

## 3. uv + editable local path dependency that is a submodule

### 3.1 How `uv add submodules/Freedom-LS` works

Running `uv add submodules/Freedom-LS` (without `--editable`) installs FLS as a regular
(non-editable) path dependency. The pyproject.toml gets a `[tool.uv.sources]` entry:

```toml
[project]
dependencies = ["freedom_ls"]

[tool.uv.sources]
freedom_ls = { path = "submodules/Freedom-LS" }
```

For an **editable** install (code changes reflected without reinstall), the flag is
`uv add --editable submodules/Freedom-LS`, which produces:

```toml
[tool.uv.sources]
freedom_ls = { path = "submodules/Freedom-LS", editable = true }
```

For a concrete implementation, **editable is the right choice**. The concrete project's Django
settings, templates, and Tailwind source all reference FLS code paths. Editable mode means the
`.venv` uses a `.pth` file pointing directly at `submodules/Freedom-LS/`, so the installed
package always reflects the pinned submodule's actual files without needing to reinstall after
every `git submodule update`.

References:
- [Managing dependencies | uv (docs.astral.sh)](https://docs.astral.sh/uv/concepts/projects/dependencies/)
- [Working on projects | uv (docs.astral.sh)](https://docs.astral.sh/uv/guides/projects/)

### 3.2 What `uv.lock` records for a local path dependency

For a local editable path dep, `uv.lock` records the package's name, resolved version (from the
submodule's `pyproject.toml`), and a source entry of the form:

```toml
[[package]]
name = "freedom-ls"
version = "0.1.0"
source = { editable = "submodules/Freedom-LS" }
```

Critically: **no hash of the source directory is stored**. The lock file records the *path* and
the *version string* from pyproject.toml. It does not record a content hash of the submodule
directory. This has an important implication (see §3.3 below).

References:
- [Locking and syncing | uv (docs.astral.sh)](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Lockfile Management | astral-sh/uv DeepWiki](https://deepwiki.com/astral-sh/uv/7.2-lockfile-management)

### 3.3 What happens when the submodule pointer moves?

When `update_fls.md` advances the submodule to a new commit, the files in
`submodules/Freedom-LS/` change, but `uv.lock` is **not automatically updated** unless the
`version` string in `submodules/Freedom-LS/pyproject.toml` also changed.

Behaviour in practice:
- If the FLS `pyproject.toml` version string stays `0.1.0` across commits, `uv.lock` already
  contains `version = "0.1.0"` for that source — uv sees the lockfile as still valid and
  `uv sync` installs from the path without re-locking.
- If FLS adds a new PyPI dependency (e.g. a new package added to `[project].dependencies`), uv
  *will* detect that the lockfile is outdated on the next `uv sync` and re-resolve.
- The editable `.pth` file always points at the current on-disk content of
  `submodules/Freedom-LS/`, so Python code changes are reflected immediately without any uv
  command.

**Practical implication for `update_fls.md`**: the integration step should always include
`uv sync` (or `uv lock && uv sync`) after advancing the submodule pointer, to catch any new
transitive dependency changes introduced by FLS. Using `uv sync --frozen` in CI is correct only
if `uv.lock` was also committed after the pointer move; if FLS added new deps and the concrete
project's `uv.lock` was not regenerated, CI with `--frozen` will fail (correctly).

References:
- [Locking and syncing | uv (docs.astral.sh)](https://docs.astral.sh/uv/concepts/projects/sync/)
- [local editable dependencies: uv lock behaves differently for projects and scripts (github issue #18312)](https://github.com/astral-sh/uv/issues/18312)

### 3.4 `--locked` vs `--frozen` in CI

- `uv sync --locked`: fails with an error if `uv.lock` is out of date relative to
  `pyproject.toml`. Use in CI to catch uncommitted lockfile updates.
- `uv sync --frozen`: installs from `uv.lock` as-is without even checking whether it's
  current. Slightly faster but misses drift detection.

**Recommendation**: use `uv sync --locked` in CI. If FLS adds a dependency and the concrete
project's `uv.lock` wasn't updated and committed, CI fails and the developer is told to run
`uv lock` locally and commit the result.

### 3.5 Workspace mode vs path dependency

uv workspaces share a single lockfile across all members, which is ideal when multiple Python
packages co-exist in one repo and need compatible dependency resolution. That is not the FLS
situation: FLS is a separate, independently-versioned package that the concrete project
consumes — it is not a co-developed sibling package. Using a **path dependency** (as currently
done) is the right choice. Workspace mode would create a shared lockfile that merges FLS's dev
dependencies with the concrete project's, which is undesirable.

References:
- [Using workspaces | uv (docs.astral.sh)](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [Question: Difference between workspaces and editable-dependencies (github issue #8195)](https://github.com/astral-sh/uv/issues/8195)

---

## 4. GitHub template repo and submodule behaviour

### 4.1 Does a generated repo keep the submodule?

Yes, as of October 2020 GitHub fixed template repo generation to include submodules.
([Source: GitHub Community Discussion #22244](https://github.com/orgs/community/discussions/22244))
When a user clicks "Use this template", the generated repo receives:
- The `.gitmodules` file
- The gitlink entry at the pinned commit SHA from the template

However, the generated repo is created with a **single commit** (no inherited history), so the
submodule pointer is whatever the template's HEAD had at generation time — not the latest FLS
commit.

### 4.2 The stale-pointer problem

Generated repos start with whatever commit the template pinned. This is intentional (submodules
pin to commits, not branches), but it means a project created from the template 6 months after
the template was last updated will immediately need `update_fls` run against it.

**Mitigations**:
- Keep the template repo's FLS pointer up-to-date via a Dependabot `gitsubmodule` config or a
  weekly GitHub Actions workflow that advances the pointer and opens a PR.
- Document in the template README that the first post-generation action is to run `update_fls`
  to get current.

References:
- [Keep template submodule pointed at latest commit (GitHub Community #32914)](https://github.com/orgs/community/discussions/32914)

### 4.3 Submodule initialisation after generation

After clicking "Use this template" and cloning, the user must still:
```bash
git clone --recurse-submodules <new-repo-url>
# OR: plain clone + git submodule update --init --recursive
```

The generated repo **does not** auto-run any setup. The template README or a post-clone script
(see §6.3) must guide the user through this.

---

## 5. Scaffolding mechanism tradeoff

Three main options for bootstrapping a concrete implementation:

### Option A: GitHub Template Repository

**Pros:**
- Zero tool installation required — users click "Use this template" in the GitHub UI
- `.gitmodules`, `pyproject.toml`, wrapper script stubs, `.claude/settings.json`, all
  committed into the template — every concrete project gets them immediately
- GitHub Actions workflows in the template are automatically inherited

**Cons:**
- No variable substitution at generation time (project name, theme slug, etc. must be
  changed manually or via a post-generation script)
- Template must be kept updated (submodule pointer will go stale)
- Generated repo starts with a single commit, which can be surprising
- Submodule is included but not initialised — the user still has to run
  `git submodule update --init --recursive` after cloning

**Verdict**: Works well for the FLS case because the template content is largely static
(the variation between concrete projects is small: project name, Django settings, theme).
The `fls:init` command handles the Claude-plugin-specific customisation after generation.

### Option B: cookiecutter

**Pros:**
- Jinja2 variable substitution handles project name, Django settings slug, etc.
- Post-generation hooks can run `git submodule add`, `uv add`, etc.
- The template itself is a separate repo; concrete repos have no template-dependency

**Cons:**
- Requires `cookiecutter` installed locally (Python tool, adds a bootstrapping step)
- Known issue: cookiecutter does not natively support git submodules in the template
  directory. The post-generation hook must explicitly run `git submodule add` because
  cookiecutter clones the template without `--recurse-submodules`.
  ([Source: cookiecutter issue #1041](https://github.com/audreyr/cookiecutter/issues/1041))
- No update path: once a project is generated, cookiecutter is out of the picture. Updates
  are handled by the existing `update_fls.md` mechanism anyway, so this is acceptable.

**Verdict**: Viable, but the submodule support gap requires a non-trivial post-generation hook
to patch things up. Adds a tool dependency for a one-time operation.

### Option C: Plain "clone and script"

The template repo is a plain git repo (not marked as a GitHub template). A user clones it,
renames it to their project, runs an `init.sh` script, and then detaches from the template
remote. The `fls:init` plugin command handles Claude-Code setup.

**Pros:**
- No external tool dependency
- The `init.sh` script has full shell power: can run `git submodule update --init`, `uv sync`,
  `npm i`, prompt for project name, update files in place, etc.
- Works offline (no GitHub template generation API call needed)

**Cons:**
- Slightly more manual (user must clone and run a script rather than clicking in the UI)
- Requires the user to manually update the git remote after cloning

**Verdict**: Simple, reliable, and requires no external tools. Well-suited for an audience of
developers who are already comfortable with the terminal.

### Recommendation: GitHub Template Repository (Option A) + `fls:init` post-generation

The combination of:
1. A GitHub template repo with FLS already added as a submodule (pinned to a recent commit),
   `pyproject.toml` with the editable path dep, and wrapper script stubs with `__FLS_PATH__`
   placeholders
2. `git clone --recurse-submodules` after generation (documented in README)
3. `uv sync` to install deps
4. `./claude.sh /fls:init` to set up the Claude plugin (replaces `__FLS_PATH__`, creates
   config files, etc.)

...gives the lightest user experience (UI-driven generation, no tool install) while
delegating all the smart customisation to the existing `fls:init` command. The stale-pointer
problem is mitigated by a Dependabot or GitHub Actions auto-update on the template repo itself.

If variable substitution for project name/slug is needed at generation time, a lightweight
post-clone `setup.sh` script that `sed`-replaces a few placeholder strings (e.g.
`MY_PROJECT_NAME`) is simpler and less fragile than introducing cookiecutter.

---

## 6. Preventing edits to the submodule

### 6.1 The problem

Claude Code and human developers working in a concrete project must not make commits to
`submodules/Freedom-LS`. That directory should be treated as read-only. However, git does not
enforce this natively — the files are writable on disk.

### 6.2 Claude Code deny rules (`settings.json`)

The most reliable enforcement for Claude Code is the `deny` list in `.claude/settings.json`.
Using glob patterns:

```json
"deny": [
    "Write(submodules/**)",
    "Edit(submodules/**)"
]
```

These deny rules apply even in `bypassPermissions` mode for non-dangerous operations, though
the strongest guarantee is that they appear in the project-level `.claude/settings.json` which
is committed to the repo.

The FLS plugin's existing `templates/settings.json` already contains a `deny` section; the
template repo should include these submodule deny rules in the project-level settings, not just
the plugin template.

References:
- [Claude Code Permissions docs](https://code.claude.com/docs/en/permission-modes)
- [Constraining Claude (Medium/Kantega)](https://medium.com/kantega/constraining-claude-514a7eed9fc7)

**Important caveat**: Claude Code has been reported to sometimes ignore `.gitignore`-based
restrictions. Explicit deny rules in `settings.json` are more reliable than relying on
`.gitignore` or `.gitattributes`.
([Source: The Register, Jan 2026](https://www.theregister.com/2026/01/28/claude_code_ai_secrets_files/))

### 6.3 CLAUDE.md instruction

The concrete project's `CLAUDE.md` should include a clearly marked section:

```markdown
## IMPORTANT: Do not edit the FLS submodule

The `submodules/Freedom-LS/` directory is a read-only reference to the upstream FLS package.
Never make edits, run migrations, or commit changes inside that directory.
To update FLS, use the `/fls:update_fls` command.
```

This is belt-and-suspenders alongside the deny rules — Claude reads `CLAUDE.md` at session
start and will apply the instruction even before hitting a deny rule.

### 6.4 Git-level protection

Git does not provide a built-in "make directory read-only" feature at the protocol level.
Options:

- **`submodule.ignore = dirty`** in `.gitmodules`: tells git to ignore any changes inside the
  submodule when showing status. This prevents `git status` noise if files are accidentally
  modified but does not prevent modifications.
  ```ini
  [submodule "submodules/Freedom-LS"]
      ignore = dirty
  ```
- **File-system permissions**: `chmod -R a-w submodules/Freedom-LS/` after submodule init would
  prevent accidental writes, but is cumbersome (breaks `git submodule update` which needs to
  write to the directory) and is not portable.
- **Pre-commit hook**: a hook that inspects `git diff --cached` for any staged changes inside
  `submodules/Freedom-LS/` and rejects the commit. This is the most practical git-native
  guard for human contributors.

For Claude Code, the `settings.json` deny rules are sufficient and should be the primary control.

---

## 7. Recommendations for FLS template repo

### R1. Use a GitHub Template Repository as the generation mechanism

Mark the template repo as a GitHub Template Repository. Include in it:
- `submodules/Freedom-LS` as an initialised git submodule, pinned to a recent stable commit
- `pyproject.toml` with `freedom_ls = { path = "submodules/Freedom-LS", editable = true }` in
  `[tool.uv.sources]`
- A committed `uv.lock` generated against the pinned submodule
- Wrapper script stubs with `__FLS_PATH__ = submodules/Freedom-LS` already substituted (or keep
  the `__FLS_PATH__` placeholder and handle it in `fls:init`)
- A project-level `.claude/settings.json` with submodule write deny rules
- A `CLAUDE.md` with the "do not edit submodule" instruction

### R2. Document the four post-generation steps prominently

In the template README (visible to any new repo created from it):
1. `git clone --recurse-submodules <your-new-repo-url>`
2. `uv sync` — installs all dependencies including FLS from the submodule
3. `npm i && npm run tailwind_build` — sets up Tailwind
4. `./claude.sh /fls:init` — sets up the Claude Code plugin

### R3. Add a submodule health check to `install_dev.sh`

The wrapper script should verify the submodule is initialised before proceeding:

```bash
if [ ! -f "$PROJECT_ROOT/submodules/Freedom-LS/pyproject.toml" ]; then
    echo "ERROR: FLS submodule not initialised."
    echo "Run: git submodule update --init --recursive"
    exit 1
fi
```

### R4. Never use `git submodule update --remote` in automation

Always pin to explicit commits. The `update_fls.md` workflow already enforces this correctly.
Document this rule in both the template README and the concrete project's `CLAUDE.md`.

### R5. Keep the template submodule pointer current

Set up a GitHub Actions workflow on the template repo that:
- Runs weekly
- Runs `cd submodules/Freedom-LS && git fetch && git checkout origin/main`
- Runs `uv lock` to update the lockfile
- Opens a PR with the changes

This prevents new concrete projects from starting with a very stale FLS version.

### R6. Add `submodules/**` deny rules to the committed project-level `.claude/settings.json`

```json
{
  "permissions": {
    "deny": [
      "Write(submodules/**)",
      "Edit(submodules/**)"
    ]
  }
}
```

These should be in the **project-level** file (`.claude/settings.json` in the concrete repo),
not just in the FLS plugin's template, so they are committed and enforced even before `fls:init`
is run.

### R7. Use `uv sync --locked` in CI

Concrete projects' CI pipelines should use `uv sync --locked` to catch cases where the
submodule's dependencies changed but the concrete project's `uv.lock` was not regenerated and
committed.

### R8. Use editable install, not regular path dep

`uv add --editable submodules/Freedom-LS` is the correct invocation. The resulting `.pth` file
in `.venv` means that advancing the submodule pointer (and running `git submodule update`)
automatically reflects the new FLS code without reinstalling. This is the behaviour assumed by
`update_fls.md`.

### R9. Prefer a light post-clone `setup.sh` over cookiecutter if variable substitution is needed

If project-name substitution or initial settings generation is needed, a short `setup.sh` script
that `sed`-replaces placeholder strings (e.g. `MY_PROJECT_SLUG`) and then removes itself is
simpler and more reliable than introducing a cookiecutter dependency. cookiecutter's submodule
support is incomplete without a custom post-generation hook.

---

## Reference URLs

- [Git Book: Submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [git-submodule documentation](https://git-scm.com/docs/git-submodule)
- [Demystifying git submodules (cyberdemon.org, 2024)](https://www.cyberdemon.org/2024/03/20/submodules.html)
- [Git submodules best practices (slavafomin gist)](https://gist.github.com/slavafomin/08670ec0c0e75b500edbaa5d43a5c93c)
- [Working with submodules (GitHub Blog, 2016)](https://github.blog/2016-02-01-working-with-submodules/)
- [Mastering Git Submodules (martinuke0.github.io, 2026)](https://martinuke0.github.io/posts/2026-04-01-mastering-git-submodules-a-comprehensive-guide-for-developers/)
- [Get up to speed with partial clone and shallow clone (GitHub Blog)](https://github.blog/open-source/git/get-up-to-speed-with-partial-clone-and-shallow-clone/)
- [GitHub Community: Submodules in template repos (#22244)](https://github.com/orgs/community/discussions/22244)
- [GitHub Community: Template submodule pinned vs latest (#32914)](https://github.com/orgs/community/discussions/32914)
- [Creating a repository from a template (GitHub Docs)](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
- [Managing dependencies | uv](https://docs.astral.sh/uv/concepts/projects/dependencies/)
- [Locking and syncing | uv](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Using workspaces | uv](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [uv local editable dep lock behavior issue #18312](https://github.com/astral-sh/uv/issues/18312)
- [Lockfile Management | astral-sh/uv DeepWiki](https://deepwiki.com/astral-sh/uv/7.2-lockfile-management)
- [cookiecutter submodule issue #1041](https://github.com/audreyr/cookiecutter/issues/1041)
- [Structkit vs cookiecutter vs copier comparison (DEV Community)](https://dev.to/structkit/structkit-vs-cookiecutter-vs-copier-which-project-scaffolding-tool-is-right-for-you-5gag)
- [Claude Code permission modes](https://code.claude.com/docs/en/permission-modes)
- [Claude Code ignores gitignore (The Register, Jan 2026)](https://www.theregister.com/2026/01/28/claude_code_ai_secrets_files/)
- [Git submodule detached HEAD guide](https://copyprogramming.com/howto/git-submodules-still-with-detached-head)
- [Git Submodules: The Complete Guide 2026 (devtoolbox.dedyn.io)](https://devtoolbox.dedyn.io/blog/git-submodules-guide)

status: ok
