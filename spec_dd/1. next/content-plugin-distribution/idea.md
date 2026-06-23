# Distribute FLS authoring plugins to content repositories

## Problem

`fls-content-plugin/` is a self-contained Claude Code plugin (`.claude-plugin/plugin.json`,
name `fls-content`). It bundles the course-authoring commands (`init`, `format-content`,
`validate-content`), skills (content-types, conventions, markdown-conversion,
widget-reference), the `content-formatter` agent, and a Python validator (`validate/`).

It currently lives inside the `preludetech/Freedom-LS` monorepo. We need to:

- keep authoring it here, alongside the content-engine code it tracks, so it can be updated
  when content structures change (single source of truth); and
- get the latest version into separate **content repositories** where course authors work.

We also expect **more authoring plugins over time** — e.g. a `django-best-practice` plugin
that lives in a different directory of this monorepo, or a `pedagogy` plugin maintained in its
own separate repo. The distribution mechanism should handle several plugins from mixed
sources, not just this one.

We do not want to vendor/copy plugins into each content repo by hand — that makes updates a
manual re-apply everywhere.

## Mechanism: a Claude Code plugin marketplace (a thin catalog)

Claude Code's native mechanism is a **plugin marketplace**: a git repo containing a
`.claude-plugin/marketplace.json` manifest that lists plugins and where each one's source
lives. Content authors run two commands once:

```
/plugin marketplace add <owner/marketplace-repo>
/plugin install fls-content@<marketplace-name>
```

Updating is then `/plugin update` (or auto-update, depending on their config).
`${CLAUDE_PLUGIN_ROOT}` resolves to wherever the plugin is installed, so the validator and the
`init` venv setup keep working unchanged.

The important property: **`marketplace.json` supports a per-plugin `source`**, and an entry can
point at a *separate repo* or even *a subdirectory of a separate repo*. Supported source types:

| `source` | meaning |
|---|---|
| `"./plugins/x"` | a path inside the marketplace repo (vendored copy) |
| `{source: "github", repo: "owner/x"}` | a separate GitHub repo (whole repo is the plugin) |
| `{source: "git-subdir", url: "...", path: "fls-content-plugin"}` | a subdirectory of a separate repo |
| `{source: "url", url: "..."}` / `{source: "npm", ...}` | any git host / npm package |

So the marketplace repo can be a **pure catalog** — just `marketplace.json` + docs — with each
entry pointing Claude Code at wherever that plugin actually lives. No vendoring is needed for
any plugin whose source a consumer can already read.

## Submodules do NOT work (verified)

A tempting design is a marketplace repo whose plugins are git **submodules**. This does not
work: **Claude Code does not recurse submodules when a consumer adds a marketplace.** It clones
the marketplace repo and stops. Submodule directories would exist but be empty, so every plugin
would be missing its files for consumers. Submodules are off the table.

(They would also reintroduce the private-access problem below — a submodule is a pointer to a
remote repo, so a consumer would need read access to every plugin's upstream, not just the
marketplace.)

## The only axis that actually matters: can the consumer reach the source?

Submodule-vs-subtree was never the real question — **access** is. For each plugin, the consumer
(a content author) must be able to fetch whatever its `source` points at. That gives two cases:

- **Source is reachable by content authors** (a public repo, or a separate private repo they
  are granted access to) → reference it directly in `marketplace.json` with `github` /
  `git-subdir`. Nothing to sync, ever. A `pedagogy` plugin in its own repo is one `github`
  entry; a future `django-best-practice` plugin in this monorepo is one `git-subdir` entry
  pointing at its directory.
- **Source must stay private** (the monorepo, if we will not grant authors read access to it)
  → the plugin must be republished to a place authors *can* read, and the entry points there.
  This is the only place a sync step is needed.

## The governing decision

> **Will content authors be granted read access to the `preludetech/Freedom-LS` monorepo?**

- **Yes** → pure-catalog marketplace, `git-subdir` pointing straight at `fls-content-plugin/`
  (and at future plugin directories). No subtree, no submodule, no sync job at all. By far the
  simplest, and it scales to N plugins trivially.
- **No** → the marketplace is still a thin catalog, but each private-monorepo plugin needs a
  republish step into a small reachable repo, with its entry pointing there. Public/standalone
  plugins (e.g. pedagogy) are still referenced directly.

## If a republish step is needed: subtree split

Only relevant in the "monorepo stays private" branch. To lift a single subdirectory of the
monorepo into its own standalone, consumer-readable repo while preserving its history:

```
# in the monorepo:
git subtree split --prefix=fls-content-plugin -b dist/fls-content
git push <dist-repo> dist/fls-content:main
```

`subtree split` synthesizes a history containing only the commits that touched that
subdirectory, rewritten as if it were the repo root. It is incremental/idempotent — repeated
pushes fast-forward cleanly as long as monorepo history for that path is not rewritten. The
`marketplace.json` entry then points at `<dist-repo>` (whole-repo `github` source).

Keep this strictly **one-way**: edits happen in the monorepo, the dist repo is generated output
(protect its `main`, banner the README "do not edit — generated from Freedom-LS"). A direct
edit in the dist repo forks it and the next push conflicts.

## Versioning

`/plugin update` keys off the `version` in each plugin's `plugin.json`. Bumping it (semver) is
what signals content repos that there is something new — make a version bump part of any
release/republish step. Versions are per-plugin: a pedagogy release never forces an fls-content
bump. Because the validator's schema travels with the plugin, a content-structure change is:
edit schema + skills → bump `version` → push (and republish if private) → authors
`/plugin update`. The validator they run is always matched to the plugin version.

## Next steps (not yet done)

- Decide the governing question (monorepo read access for content authors: yes/no).
- Sketch the `marketplace.json` catalog (one entry per plugin, with the right `source` type
  per the decision above).
- Only if "no": write the subtree-split republish script (split + push + version-bump guard),
  and create the dedicated dist repo(s).
