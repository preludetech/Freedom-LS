# Caprover / Dead Deployment Cruft Inventory

_Scan date: 2026-06-21_
_Base directory: `/home/sheena/workspace/lms/freedom-ls-worktrees/concrete-implementation-helpers/`_

---

## Methodology

- Read every known deployment-related file in full.
- Grepped (case-insensitive) the entire repo for: `caprover`, `captain`, `nginx`, `gunicorn`, `docker` in all `.py`, `.yml`, `.md`, `.sh` files.
- Inspected `captain-definition`, `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `.dockerignore`, `nginx.conf`, and all `docs/` deployment files.
- Reviewed all `.github/workflows/` files.

---

## Item-by-Item Analysis

| # | Path | What it is | Classification | Reason |
|---|------|------------|----------------|--------|
| 1 | `captain-definition` | CapRover schema file — tells CapRover which Dockerfile to use | **DELETE (Caprover)** | Exclusively a CapRover artefact; no other deployment system uses this file. Zero value outside CapRover. |
| 2 | `docs/how tos/Caprover deploy.md` | Step-by-step CapRover deployment guide, references `CAPROVER_URL`, `CAPROVER_APP_TOKEN`, `captain-definition`, and CapRover-specific `docker ps --filter name=srv-captain--...` | **DELETE (Caprover)** | Entirely CapRover-specific. `docs/product/deployment.md` already marks it superseded and explains why (root access, no RBAC, ISO 27001 incompatible). |
| 3 | `docs/how tos/DOCKER_DEPLOY.md` | Docker Compose + nginx deployment guide, no CapRover content | **REVIEW (superseded, not Caprover)** | Generic Docker Compose instructions. `docs/product/deployment.md` explicitly marks it superseded (nginx replaced by Caddy) but not Caprover-specific. Contains useful procedural knowledge (migrations, content loading, log commands) that may inform the concrete-implementation helpers work. Defer — do not delete now, do not build on now. |
| 4 | `Dockerfile` | Multi-stage production Docker image (Node → TailwindCSS → Python/Gunicorn) | **REVIEW (generic Docker, not Caprover)** | Not CapRover-specific. Referenced by `docker-compose.yml` and `captain-definition` (the latter can be deleted independently). The Dockerfile itself is generic and will be needed for any container-based deployment. The current target architecture (Caddy + Gunicorn) still uses this image. Defer — do not delete, but review whether it should be updated (e.g., the `FLS_THEME` build-arg pattern documented in `DOCKER_DEPLOY.md` is not yet in the Dockerfile). |
| 5 | `docker-compose.yml` | Production Docker Compose stack: db + web + nginx | **REVIEW (partially superseded)** | Not CapRover-specific. The nginx service is superseded (target arch uses Caddy), but the db + web structure is still relevant. The future concrete-implementation helpers work may want a revised version (with Caddy instead of nginx). Defer — do not delete now. |
| 6 | `docker-entrypoint.sh` | Entrypoint script: fixes media/logs permissions, `exec gosu appuser "$@"` | **REVIEW (generic, useful)** | Pure Docker utility, zero CapRover coupling. Required by `Dockerfile`. Keep as-is. Defer — no action needed now. |
| 7 | `.dockerignore` | Standard Docker ignore list | **REVIEW (generic, useful)** | No CapRover content. Standard practice. Keep as-is. Defer — no action needed now. |
| 8 | `nginx.conf` | nginx reverse proxy config (media serving, Django proxy, health check) | **REVIEW (superseded)** | Not CapRover-specific, but superseded: the target architecture replaces nginx with Caddy. The config is simple and its contents (media serving, health check, proxy headers) can serve as reference for writing a Caddyfile. Defer — do not delete now; flag as reference material for future deployment work. |
| 9 | `README.md` line 31 | Sentence: "...Caprover predeploy hook..." in the "Tailwind in deploys / CI" section | **DELETE (Caprover mention)** | Single stale Caprover reference embedded in otherwise valid content about `npm run tailwind_build`. The sentence can be updated to remove the CapRover example while keeping the Docker image build and CI step examples. |
| 10 | `docs/product/deployment.md` lines 113–114 | "Superseded Deployment Guides" section listing `DOCKER_DEPLOY.md` and `Caprover deploy.md` as superseded | **KEEP** | This section is doing the right thing: documenting what is obsolete and why. Nothing to remove here. |
| 11 | `docs/deployment-security-checklist.md` | Generic deployment security checklist (OS hardening, TLS, HSTS, DB security, etc.) | **KEEP** | No CapRover references. Fully generic and valuable. |
| 12 | `.github/workflows/tests.yml` | CI test pipeline (lint, type-check, unit tests, Playwright) | **KEEP** | No CapRover references. Clean CI. |
| 13 | `.github/workflows/security.yml` | SAST/audit pipeline (Bandit, pip-audit, Semgrep, Django deploy check) | **KEEP** | No CapRover references. |
| 14 | `.github/workflows/notify-downstream.yml` | Cross-repo notification on main push | **KEEP** | No CapRover references. |
| 15 | `.github/workflows/claude.yml` | Claude Code GitHub Action | **KEEP** | No CapRover references. |
| 16 | `config/settings_prod.py` | Production Django settings | **KEEP** | No CapRover references. Generic prod settings. |

---

## In-Code References That Would Break If DELETE Items Were Removed

| Deleted item | Location of reference | Impact |
|---|---|---|
| `captain-definition` | `docs/how tos/Caprover deploy.md` line 15 (mentions `captain-definition`) | No impact — that doc is also being deleted. |
| `docs/how tos/Caprover deploy.md` | `docs/product/deployment.md` line 114 (markdown link to the file) | The link in `deployment.md` will 404. **The link in `deployment.md` must be removed or updated when the file is deleted.** |
| README.md line 31 (Caprover mention) | Self-contained sentence in a paragraph | Safe to edit; rest of paragraph remains valid. |

No Python settings, imports, or environment variables are tied exclusively to CapRover or `captain-definition`. The env vars `CAPROVER_URL`, `CAPROVER_APP_TOKEN` appear only in the markdown doc, not in any `.py` or `.yml` file.

---

## Proposed Cleanup List (DELETE items)

These should be removed in a single cleanup commit:

1. **`captain-definition`** — delete the file entirely.
2. **`docs/how tos/Caprover deploy.md`** — delete the file entirely.
3. **`README.md` line 31** — edit the sentence `"...or Caprover predeploy hook..."` to remove the CapRover example (keep the surrounding valid content about CI and Docker image builds).
4. **`docs/product/deployment.md` lines 113–114** — after deleting `Caprover deploy.md`, remove or rewrite the broken link. The `DOCKER_DEPLOY.md` superseded note in that same section can remain (that file is REVIEW, not DELETE).

---

## Defer / Review Later List

These items are NOT Caprover-specific but are partially or fully superseded by the target architecture (Caddy + Ansible + GHCR CI/CD). They should be left alone until the deployment-helpers feature is actively specced and built.

| Item | Status | Notes |
|---|---|---|
| `docs/how tos/DOCKER_DEPLOY.md` | Superseded (nginx → Caddy), but useful reference | Already flagged superseded in `deployment.md`. Keep for now; revisit when writing concrete deployment helpers. |
| `Dockerfile` | In use; may need updates | Missing `FLS_THEME` build-arg pattern documented in `DOCKER_DEPLOY.md`. Update when building concrete deployment tooling. |
| `docker-compose.yml` | Partially superseded (nginx service) | Update nginx → Caddy when building concrete deployment tooling. |
| `docker-entrypoint.sh` | Still valid and needed | No action required. |
| `.dockerignore` | Still valid | No action required. |
| `nginx.conf` | Superseded (Caddy replaces nginx) | Keep as reference for writing Caddyfile. Remove once a Caddyfile exists. |

---

status: ok
