# Launcher editing (`claude.sh`)

> Duplicated into each plugin that adds a `--plugin-dir` line, because `${CLAUDE_PLUGIN_ROOT}` is
> per-plugin and a plugin here depends on no other plugin. Apart from the parameter table below the
> copies are identical — diff them when you change one.

| Parameter | Value in this copy |
|---|---|
| `<PLUGIN_DIR_NAME>` | `sdd` |
| `<MAY_CREATE>` | **false** — `/ds:init` owns the launcher skeleton |

`claude.sh` is a shared file. This procedure changes exactly one thing: it makes sure **one**
`--plugin-dir` line for `<PLUGIN_DIR_NAME>` is present, in the canonical form. It never adds,
removes, reorders, or reformats another plugin's line.

Every rule is idempotent: running the whole procedure twice makes no second change.

## L0 — Read and classify (preflight; no writes)

Record these facts. Later rules act on them and never re-derive them.

- **invocation line** — the one non-comment line that runs `claude` as a command (a line that merely
  assigns the word to a variable, e.g. `CLAUDE_BIN=claude`, is not one). **If the file does not exist,
  record shape `absent` and skip the rest of L0 — an absent launcher is never a STOP.** If the file
  exists and has zero such lines, or more than one, **STOP in preflight**: this launcher needs
  hand-editing.
- **sentinel** — the leading `NAME=1` assignment on that line, if any. Record `NAME`.
- **plugin-dir arguments** — every `--plugin-dir "<path>"`, wherever it sits (on the invocation line
  or on its own continuation line). Record each path, in order, and whether it contains the path
  segment `/claude_plugins/`.
- **`PLUGINS_ROOT=` / `SCRIPT_DIR=`** — present or absent, and where.
- **shape** — `absent`, `single-line` (no backslash continuations), or `multi-line`.

## L1 — Absent launcher

- `<MAY_CREATE>` false → preflight already stopped; this branch is unreachable.
- `<MAY_CREATE>` true → copy `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/claude.sh`, replace
  `__PLUGINS_ROOT__` with the resolved value, `chmod +x`. **Stop here** — the template already
  carries this plugin's line, the sentinel, and `PLUGINS_ROOT`. Do not run L2–L6.

## L2 — Normalise to the canonical multi-line shape

Run this before anything else, so every later rule has a standalone `"$@"` line to anchor on. It is
a pure reformat — identical tokens, rearranged. Nothing is added or dropped.

If **shape** is `single-line`, rewrite the invocation line as:

```bash
<SENTINEL>=1 claude \
  --plugin-dir "<path 1>" \
  --plugin-dir "<path 2>" \
  "$@"
```

preserving every existing argument verbatim, in its original order, one per continued line. If the
line carried no `--plugin-dir`, the result is the invocation line, then the `"$@"` line. If it had
no `NAME=1` prefix, omit it here — L6 adds one.

If **shape** is `multi-line` but no line's sole non-whitespace content is `"$@"`, split `"$@"` onto
its own line, keeping the preceding line's trailing `\`.

**Postcondition: the file now contains exactly one line whose only non-whitespace content is
`"$@"`.** Every later rule anchors on that line, so "immediately above the `"$@"` line" is defined
for every input shape — including the one-line pre-split launcher.

## L3 — Ensure `PLUGINS_ROOT`

- Present → leave it. Preflight already adopted its value.
- Absent → insert `PLUGINS_ROOT="<resolved value>"` on its own line immediately above the
  `SCRIPT_DIR=` line. If there is no `SCRIPT_DIR=` line either, insert both — `PLUGINS_ROOT=` then
  `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` — immediately below the last leading
  comment or shebang line.

Run L3 **before** L4 and L5. A `--plugin-dir` line that expands `$PLUGINS_ROOT` must never be
written into a file that has no such variable — that produces a path like `//claude_plugins/…` and
the plugin silently fails to load.

## L4 — Retire a pre-`claude_plugins` argument — *only when `<MAY_CREATE>` is true*

For each recorded `--plugin-dir` argument whose path does **not** contain the segment
`/claude_plugins/` (i.e. it points at a pre-split monolith checkout):

- If this plugin's canonical line is already present (L5's count ≥ 1) → **delete** that argument's
  line.
- Otherwise → **replace** that argument's line, in place, with the canonical line text from L5. A
  replacement, never an insertion.

An argument whose path *does* contain `/claude_plugins/` belongs to some plugin's init and is never
touched here. Plugins with `<MAY_CREATE>` false skip L4 entirely — retiring a shared legacy argument
twice would delete a line the first init just wrote.

## L5 — Ensure exactly one canonical line

Canonical text — two leading spaces, one trailing backslash:

```bash
  --plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/<PLUGIN_DIR_NAME>" \
```

Count the `--plugin-dir` arguments whose path's **final segment** equals `<PLUGIN_DIR_NAME>` (final
segment only, so both `…/claude_plugins/<PLUGIN_DIR_NAME>` and
`…/$PLUGINS_ROOT/claude_plugins/<PLUGIN_DIR_NAME>` count):

- **0** → insert the canonical line immediately above the `"$@"` line.
- **1** → if that line already equals the canonical text, do nothing. Otherwise replace that one line
  with the canonical text. This is what upgrades a half-migrated line to the `$PLUGINS_ROOT` form.
- **≥2** → an earlier run duplicated it. Keep the first, delete the others, report the repair.

Never touch a `--plugin-dir` line whose final segment is not `<PLUGIN_DIR_NAME>`.

## L6 — Sentinel and mode — *only when `<MAY_CREATE>` is true*

- If the invocation line has a leading `NAME=1` assignment and `NAME` is not
  `CLAUDE_PLUGINS_LOADED`, replace it, and replace every `$NAME` / `${NAME}` expansion of that same
  name elsewhere in the file. (The old name is already recorded in preflight — see L0's **sentinel**
  fact — so any step needing it reads it from there, not from here.)
- If there is no leading `NAME=1` assignment, insert `CLAUDE_PLUGINS_LOADED=1 ` at the head of the
  invocation line.
- If the file is not executable, `chmod +x`.

## L7 — Report

Report L2–L6 as fired or no-op, and print the final ordered `--plugin-dir` list.
