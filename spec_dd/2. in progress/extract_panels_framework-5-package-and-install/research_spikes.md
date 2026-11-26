# Research: the idea's spikes, run before the spec

Run by `/sdd:start` on 2026-11-26 with local uv 0.8.4. The scratch projects were throwaway. The
session's worktree isolation refused git commands outside the worktree, so each locked package used a
`file://` direct reference where the real setup uses `git+https://...@tag`. uv treats both as a
locked direct-URL source and replaces an install whose source differs from the lock, so the result
carries over. Re-check it once against the real git tag during implementation.

## Spike 1: does `uv run` revert a hand-installed editable copy?

Setup: a host project depends on `demo-pkg @ file://.../pkgrel`. `uv sync`, then
`uv pip install --no-deps -e .../pkgdev`.

| Step | `demo_pkg` imported from |
| --- | --- |
| `uv sync` | locked copy |
| `uv pip install --no-deps -e pkgdev`, then `.venv/bin/python` | editable |
| `uv run python ...` with no `UV_NO_SYNC` | **locked copy: `uv run` uninstalled the editable copy** |
| re-link, then `UV_NO_SYNC=1 uv run python ...` | editable |
| `uv run --no-sync python ...` | editable |
| `uv lock --locked` while the editable copy is installed | passes |
| `uv sync` | locked copy (expected) |

**Result:** the idea's assumed fallback holds. `UV_NO_SYNC=1` is mandatory for the live-edit loop and
must be documented in `fls-dev:git-worktree-setup`. The `PYTHONPATH` fallback is not needed. An
out-of-band editable install leaves `uv lock --locked` green.

## Spike 2: does a downstream project resolve FLS's dependency transitively?

Setup: two "FLS" stand-ins, each consumed by a "First-Class" stand-in through
`[tool.uv.sources] fls = { path = ..., editable = true }`, the way First-Class consumes FLS today.

- **Variant A (PEP 508):** the FLS stand-in declares `"demo-pkg @ file://..."` in
  `[project].dependencies` and has no `[build-system]` (legacy setuptools, like FLS). It **resolves**:
  the consumer installs `demo_pkg` with no entry of its own.
- **Variant B (sources only):** the FLS stand-in declares a bare `"demo-pkg"` plus
  `[tool.uv.sources] demo-pkg = { path = ... }`. It **also resolves**: the consumer's `uv.lock`
  records `source = { directory = "../pkgrel" }`. uv applies a *path* dependency's own
  `[tool.uv.sources]` when it builds it. `research_uv_sources_and_consumers.md` §5 predicted this
  variant fails, and that prediction is wrong for path-installed consumers. It would still fail for
  a consumer that installs FLS from a git URL or an index, and for anything outside uv's project
  mode.
- **The PEP 508 form stays the decision:** `freedom_ls_infra/fls-base/Dockerfile` installs with
  `uv pip install --system -r pyproject.toml`, which reads `[project].dependencies`. It also works
  for pip and for any non-path consumer. Neither First-Class nor the concrete template needs its own
  entry.
- **Build-backend gotcha found on the way:** with `build-backend = "hatchling.build"`, a direct
  reference in `[project].dependencies` fails the build with
  `ValueError: Dependency #1 of field project.dependencies cannot be a direct reference unless field
  tool.hatch.metadata.allow-direct-references is set to true`. FLS has no `[build-system]` and builds
  with legacy setuptools, which accepts it. If FLS ever moves to hatchling, it needs
  `[tool.hatch.metadata] allow-direct-references = true`. The package repo itself has no direct
  references, so this does not affect it.

## Spike 3: does `ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim` ship git?

`docker run --rm <image> ls /usr/bin`: 301 entries, with neither `git` nor `curl` among them.
**Result:** the concrete template's Python-dependency stage must `apt-get install -y --no-install-recommends git`
before `uv sync` fetches the git dependency. This goes into the upgrade notes' manual step for the
concrete template's Dockerfile.

status: ok
