# Research: codebase (what the register_design rework touches, reuses or conflicts with)

Paths are relative to the repo root. Platform facts: `.sdd-work/spec_from_idea_platform_facts.md`.

## 1. The command itself: `claude_plugins/sdd/commands/register_design.md`

Frontmatter: `allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill, ToolSearch`; `argument-hint: [spec-dir] <handoff prompt, prompt file, or claude-design-url> [notes ...]`. Depth 0; spawns `sdd:sdd-mechanic` for screenshots and commit.

Sections and what in each is now stale:

- **Intro**: says a design "lives in claude.ai", lists outputs `design_prompt.md`, `design_source/`, `design_screenshots/`, `design.md`. Kept ideas worth reusing: "visual reference, never a source of scope", current-branch-only commit, no rebase.
- **Inputs paragraph**: names "the design-login answer" and `mode: hook`.
- **Step 1 (Resolve inputs)**: `<spec-dir>` resolution (feature branch = dir named after branch under `spec_dd/2. in progress/`; on main the user names it or a cut effort's parent via roadmap `Parent:` line) is platform-independent and reusable. The design input is a Claude Design handoff prompt (project id and entry file parsed from `https://claude.ai/design/p/<project-id>?file=<file>`, "Focus on these files", "Also read these files"), written verbatim to `design_prompt.md`; or a bare `claude.ai/design/p/...` link. Anything else stops. Notes handling and the "re-registration: rewrite design.md whole, delete old `design_scope.md`" rule are reusable. The hook-mode special case (design input is `<spec-dir>/design_prompt.md` itself) depends on that file name.
- **Step 2 (Sync)**: `ToolSearch select:DesignSync`, `get_project`, `get_file` (256 KiB cap), `list_files`, recursive scan for `@import`/`<link href>`/`<script src>`, write into `design_source/<project path>`. Never WebFetch/browser/curl. Auth fallback: `/design-login`, then register with coverage table "not yet read". This whole step is what breaks: DesignSync is design-system-only, `list_projects` lists only design-system projects, standalone Claude Design closes 2026-12-14, and designs are now Design-type Artifacts read with the `Artifact` tool (`read`/`list`, `scope: files|assets`, `out_dir`). Artifact tool is not in `allowed-tools` (only ToolSearch, which could load it if it is deferred; confirm). Binaries ("fonts, images are not synced") now become `/_blob/<id>` asset-store uploads.
- **Step 3 (design.md template)**: fixed fields `Link`, `Project id`, `Entry file`, `Made of`, `Registered`; text "This is a **Claude Design** design, drawn in claude.ai"; "How to read it" wording tells later steps to use `DesignSync` only to re-register and `/design-login` on auth; "How to treat it" (theme/scope rules) and "What it covers" table (Screen or state | Brief section | Built by) are platform-neutral and should be kept. `Entry file` is machine-read (see 2).
- **Step 4 (Screenshot)**: mechanic runs `<PLUGINS_ROOT>/claude_plugins/sdd/scripts/design_screenshots.sh "<spec-dir>"`; `PLUGINS_ROOT` resolution by `claude_plugins/sdd/commands/init.md` "The `PLUGINS_ROOT` rule". Non-zero exit does not block the commit. Mentions the three screen shapes (canvas artboard, `.dc.html` frames, whole page).
- **Step 5 (Point consumers)**: edits `idea.md` and `1. spec.md` "Resources" bullet (text hardcodes "the Claude Design design"), design brief, and `spec_dd/1. next/roadmap.md` lines waiting on mockups. Platform-independent apart from wording.
- **Step 6 (Commit)**: uses `claude_plugins/sdd/resources/commit_and_push.md`, summary `register the Claude Design design`; main/master variant commits without push. Reusable.

## 2. Screenshot script: `claude_plugins/sdd/scripts/design_screenshots.sh` and `.py`

`.sh` is a thin wrapper: `uv run --with playwright playwright install chromium` then `exec uv run --with playwright python design_screenshots.py "$@"`. All logic is in `design_screenshots.py`.

How it works today (symbols):
- `read_entry_file(spec_dir)`: requires `<spec-dir>/design.md` with a line matching `ENTRY_FILE_LINE = ^\s*-\s*Entry file:.*?\`([^\`]+)\``. Errors (exit 1) if design.md or that line is missing. So the design.md `- Entry file: \`...\`` line is a contract with the script.
- `capture(spec_dir)`: reads `design_source/`, requires `design_source/<entry>` to exist, deletes stale `design_screenshots/*.png`, copies source into a temp dir (`prepare_copy`), serves it with `ThreadingHTTPServer` on 127.0.0.1, renders with Chromium (viewport 1600x1000).
- `list_pages(source, entry)`: only `source.iterdir()` files with suffix `.html` at the TOP LEVEL, entry first. It does NOT recurse. Files under `project/` (the new layout, `project/<path>.dc.html`) would not be found; entry `project/Main.dc.html` would be treated as a path under source (works for `is_file`, but other boards would be missed).
- Three capture modes in `capture_page`: (1) `[data-artboard]` elements (design-canvas.jsx projects) named `<section>__<artboard>.png`; (2) `FRAMES_JS` finds elements with inline px width/height >= 320x480 and `overflow:hidden` (the old `.dc.html` style: fixed frame per screen), named `<page>__<screen>.png`; (3) whole page: `read_preview` parses `data-props` `$preview` from a `data-dc-script` block, else widths `FALLBACK_WIDTHS = (1280, 375)`.
- `.dc.html`: handled only as a rendered page (page_id strips `.dc`). It relies on the page loading its own `<script src="./support.js">` from the copied source. Old projects synced `support.js` into `design_source/` (e.g. design_prompt.md for bulk-action lists `support.js`). New canvases serve `artifact-type/dc-runtime.js` and `SKILL.md`/`index.html` as fixed type files that are NOT in `project/`; the script has no knowledge of them, so a `project/` export would 404 on the runtime unless the register step also reads `artifact-type/**`.
- `project/canvas.json` boards (x/y/w/h, `expand: "fill"`, `page`, `order`): NOT read anywhere. The script never parses canvas.json; sizes come from inline styles or `$preview`. Board w/h (and phone 390x844, page 1280-1440) are the natural way to size fluid `expand:"fill"` boards, which mode (2) would miss and mode (3) captures at 1280 and 375 instead.
- `/_blob/<id>` asset URLs: NOT handled. The static server would 404 them (images/fonts blank). `load()` uses `wait_until="networkidle"` and only raises on the page's own non-OK response, so 404 blobs fail silently. Would need the assets fetched (Artifact `read` with `scope: "assets"` / `paths`) and either saved under `design_source/` and rewritten, or routed by Playwright `page.route`.
- `uses_design_canvas` / `STAND_IN`: when any page text contains `design-canvas.jsx`, the script overwrites `design-canvas.jsx` in the served copy with `claude_plugins/sdd/resources/design_canvas_flat.jsx` (lays artboards out 1:1, no pan/zoom). The new Design type uses `dc-runtime.js` and `canvas.json` rather than `design-canvas.jsx`, so this stand-in is likely irrelevant for new designs (keep it for the old registered ones). The new runtime's own canvas pan/zoom may reproduce the "scaled and offscreen" problem the stand-in solved for the old format.
- Exit codes: `DesignScreenshotError` -> stderr `design_screenshots: <msg>`, exit 1. Stdout lists PNG paths. Stderr per-page lines: `N artboards`, `N screens`, `no screens drawn, captured whole` (register_design Step 4 refers to these).

Permissions in `.claude/settings.json` lines 113, 122, 131: `Bash(claude_plugins/sdd/scripts/design_screenshots.sh:*)`, `Bash(bash ...)`, `Bash(./...)`. There is NO DesignSync or Artifact permission entry anywhere in `.claude/settings.json` (grep for `DesignSync|Artifact` found nothing). If the Artifact tool is used by the command, a permission entry may be needed (the tool asks the user when saving outside the default scratchpad folder).

`.pre-commit-config.yaml` lines 9, 13, 29: three hooks `exclude: '(^|/)design_source/'`. Any new vendored folder name (e.g. `project/` or a new export dir) must be added or the hooks will rewrite/lint it. Keeping `design_source/` as the destination avoids this.

## 3. Resources

- `claude_plugins/sdd/resources/design_canvas_flat.jsx`: only consumer is `design_screenshots.py` (`STAND_IN`) and `tests/test_design_screenshots.py::test_prepare_copy_swaps_in_flat_canvas_for_the_copy_only`. Generic, no FLS names.
- Other shared resources used by the command: `writing_standard.md`, `commit_and_push.md`, `roadmap_format.md`.

## 4. Callers and mentions of the flow (all under `claude_plugins/`)

- `sdd/commands/start.md`:
  - Header (line ~13): continue-hint `/sdd:register_design <spec-dir>/design_prompt.md` when Step 6 did not finish.
  - Step 3 bullet (lines 63-67): when `design_prompt.md` exists and `design.md` does not, loads `DesignSync`, takes project id "the way `register_design.md` Step 1 does", calls `get_project`, on auth error asks "Run `/design-login` now, then choose Done (Recommended)" / "Register the design without reading it". The answer is passed on to Step 6.
  - Step 5: `answers.md` records the design-login answer.
  - Step 6 (lines 98-103): reads `register_design.md` and follows it with `mode: hook`, `<spec-dir>`, design input `<spec-dir>/design_prompt.md`, no notes, and the design-login answer. The trigger condition is the file `design_prompt.md` existing. A new human procedure that has no handoff prompt (e.g. an artifact link) needs a new trigger file/shape here.
- `sdd/commands/spec_from_idea.md` lines ~93-101: "A `design.md` ... registers a Claude Design design (see `/sdd:register_design`). Read the design itself the way that file says". Only needs a wording check, no DesignSync.
- `sdd/commands/plan_from_spec.md` line 44: reads `design_source/` and `design_screenshots/` from the dir holding `design.md`; "Load `DesignSync` (`ToolSearch` with `select:DesignSync`) only when those files are missing". Has a stale DesignSync fallback to change.
- `sdd/commands/implement_plan.md` (line ~54-59, `**Design states:**` slices) and `do_qa.md` (Rule 5, "Design comparison" ~426-445, `## Design check` ~574): pass/consume design screenshot paths only; no DesignSync. Unaffected unless screenshot naming/location changes. `do_qa` does not wipe `design_screenshots/` (it wipes `screenshots/`).
- `sdd/commands/init.md` lines 135-136, 173-175, 256-258, 350: the `## Design Hooks` / `Design check` config key in `.claude/sdd/config.md`; generic, no DesignSync.
- `sdd/commands/protected/pre_step_rebase.md` line 7: notes `register_design` never rebases.
- `sdd/skills/capture-feedback/SKILL.md` lines 98-99: tells it to leave `design_screenshots/`, `design_source/`, `design.md` untouched.
- `sdd/README.md` line 16 (command list) and lines 39-43 (register_design paragraph: "how to read it through the Claude Design integration rather than the web", "handoff prompt or claude-design-url"); line 72 lists `design_screenshots.sh` (+ `.py`).
- `sdd/commands/README.md` line 15 (start registers a design when `design_prompt.md` is present) and a long line 35 (workflow table, mentions register_design / design.md).
- `fls-dev/commands/protected/design_check.md`, `fls-dev/commands/init.md`, `fls-dev/README.md`: the Design check hook. grep found no `design_source`, `DesignSync` or `Claude Design` strings in `claude_plugins/fls-dev`, so they only consume screenshots of the running app against `design_screenshots`; likely no change.
- `spec_dd/1. next/roadmap.md`: rows/lines that wait on mockups (user-communication, educator-interface-full-polish); register_design Step 5 rewords them.

## 5. Tests

- `tests/test_design_screenshots.py` (marker `dev_tooling`, no browser): `test_missing_design_md_exits_1_naming_design_md`, `test_design_md_without_entry_file_line_exits_1_naming_entry_file`, `test_entry_file_missing_from_design_source_exits_1_naming_path`, `test_prepare_copy_swaps_in_flat_canvas_for_the_copy_only`. They pin the `Entry file` line and `design_source/<entry>` contracts.
- `tests/playwright/test_design_screenshots.py` (`dev_tooling` + `playwright`): `test_artboards_written_as_pngs_and_stale_ones_removed`, `test_canvas_page_that_renders_no_artboards_exits_1`, `test_page_without_artboards_gets_two_whole_page_screenshots`. Use a static `[data-artboard]` page.
- No tests for `.dc.html` frame detection, `$preview`, `/_blob/`, `support.js`, `canvas.json`, or for the register_design command itself (markdown). Any script change (recursing into `project/`, reading canvas.json, blob handling) needs new tests in these two files; existing tests must keep passing for old-format designs.

## 6. Existing registered designs (migration question)

`design.md` files: `spec_dd/1. next/user-communication/design.md`, `spec_dd/2. in progress/learner-facing-ux-refinements/design.md`, and in `spec_dd/3. done/`: `2026-10-01_20:38_better-looking-notifications`, `2026-10-02_07:10_new-content-type-articles`, `2026-10-05_08:22_article-images`, `2026-10-08_06:54_educator-interface-looks-good`, `2026-10-22_20:02_user-communication-4-direct-messaging` (two projects, two Link/Project id/Entry file blocks), `2026-10-30_19:36_design_learner_course_organisations`, `2026-11-08_09:13_design_educator_interface_audit_log`.

Shape (all): H1 `# Design: <name>`; "This is a **Claude Design** design, drawn in claude.ai ..."; bullets `Link` (`claude.ai/design/p/<uuid>?file=...`), `Project id`, `Entry file`, `Made of`, `Registered`; "How to read it" (mentions `DesignSync` + `/design-login` for re-registration); "How to treat it"; optional notes; "What it covers" table. Two project ids appear: `019df696-b642-74bb-a97b-ad6a760b0491` (learner) and `34ae8997-bfe5-4536-9ac7-46f01d3a12ff` (educator). `user-communication/design.md` (older) has a different "How to read it" (lines 18-22) that tells the reader to read via DesignSync directly.

Migration view: these are historical records with synced `design_source/` and `design_screenshots/` committed alongside; they are readable as-is by later steps and the script. The only stale parts are the "Use `DesignSync` only to re-register ... `/design-login`" sentence and the claude.ai link (dead after 2026-12-14). Re-registration of an old design would need the new procedure. `spec_dd/3. done/` files should not be edited (capture-feedback and `do_qa` Rule 5 treat done specs as historical). The only live ones that matter: `learner-facing-ux-refinements` (in progress) and `user-communication` (next). A back-compat requirement: the new `design.md` should keep `- Entry file: \`...\`` and `design_source/` + `design_screenshots/` so existing consumers and the script work unchanged.

Old `design_source` layout: flat, top-level `*.dc.html` plus `support.js` and `_ds/...` (e.g. `spec_dd/3. done/2026-10-08_06:54_educator-interface-looks-good/design_source/Educator Dashboard.dc.html`, `Sidebar.dc.html`). `.dc.html` files exist in 12 `design_source` folders under `spec_dd/3. done/`. So the script already renders `.dc.html` pages when `support.js` is present at the top level; the new layout differs (files under `project/`, runtime in `artifact-type/`, canvas index in `project/canvas.json`).

Pending handoff prompts in live specs (these use the OLD form and are the in-flight inputs that `/sdd:start` hook mode will try to register):
- `spec_dd/2. in progress/design_educator-interface-bulk-action/design_prompt.md`: "Use the claude_design MCP (https://api.anthropic.com/v1/design/mcp, auth via /design-login) to import this project: https://claude.ai/design/p/34ae8997-...?file=Educator+Learners.dc.html", "Focus on these files", "Also read these files" (includes `support.js`, `_ds/.../_ds_bundle.js`), "Implement: ...". So the "handoff prompt" form also names the claude_design MCP, which Step 1 does not mention.
- `spec_dd/2. in progress/learner-facing-ux-refinements/design_prompt.md` (already registered; design.md exists).
- `spec_dd/2. in progress/educator-interface-design-learner-csv-upload-design-fix/prompt.md` mentions design strings (2 hits); not examined in detail.

## 7. Constraints and conflicts

- `CLAUDE.md` "Plugins": `claude_plugins/sdd` stays generic. No FLS names, paths or apps in command text, script or resources; project values only via `.claude/sdd/config.md`. Everything above in `sdd/` is currently generic (it uses `<spec-dir>`, `spec_dd/`). `spec_dd/` is an SDD-wide convention already used in sdd. Project-specific procedure text (our two project ids, our org) must not enter `register_design.md`; a human-procedure doc should live in `claude_plugins/sdd` as generic text (e.g. a resource or README section) and project values, if any, in `.claude/sdd/config.md`.
- The `.claude/sdd/config.md` file exists as the per-project config; it has no design keys beyond `Design check` (see `init.md` ~173-175, 256).
- Script runs outside Django; `uv run --with playwright` pattern must be kept (no project-level install).
- Git/commit rules: commit via `sdd:sdd-mechanic` with `commit_and_push.md`; pre-commit excludes `design_source/` only (section 2).
- `design.md` and `design_prompt.md` file names are relied on by `start.md` (trigger), `plan_from_spec.md`, `spec_from_idea.md`, `capture-feedback`, `do_qa`. Renaming them forces edits across all of those.
- Ordering risk: standalone Claude Design closes 2026-12-14, DesignSync refuses design projects now; in-flight `design_prompt.md` files (bulk-action) will need either the new human procedure or a "not yet read" registration.

## Open points for the spec

1. Does the Artifact tool (deferred? needs `ToolSearch select:Artifact`) need adding to `register_design.md` `allowed-tools` and `.claude/settings.json`?
2. Where should the human procedure live (generic sdd README/resource) and what trigger replaces `design_prompt.md` in `start.md` Step 3/6 (an artifact link file)?
3. Script change scope: recurse into `project/`, read `canvas.json` (x/y/w/h, order, expand:fill), supply `dc-runtime.js` / `support.js`, resolve `/_blob/<id>` assets, keep old-format behaviour and tests.
4. Whether `Link` / `Project id` fields become `Artifact link` / artifact id, while keeping the `Entry file` line the script parses.

status: ok
