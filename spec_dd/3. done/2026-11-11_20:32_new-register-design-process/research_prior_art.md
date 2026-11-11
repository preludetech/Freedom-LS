# Research: prior art for registering Claude Design designs

Question: what has already been tried for registering Claude Design designs, here or elsewhere, and
what happened? Scope: the repo's spec history (git log is not available to this worker, so the
evidence is the done and in-progress specs under `spec_dd/`) and web reports on the move into Claude.

## Verdict up front

1. The current `/sdd:register_design` path (handoff prompt, then `DesignSync` `get_project` /
   `get_file`, then local render, then `design.md`) was chosen **after** a deliberate comparison with
   every export route Claude Design offered in 2026-09. It won because it is the only route that needs
   no human click in the browser. The comparison is
   `spec_dd/3. done/2026-10-01_20:38_better-looking-notifications/research_claude_design_export.md`.
   That file also records the routes rejected then, which are now the routes to reconsider: **Export
   to .zip / "Project archive"** and the **handoff bundle to Claude Code**.
2. The path has been used for at least **9 registrations** (list below) and worked. Its recurring
   costs were: every byte passes through the model (read, then retype with `Write`), binaries do not
   come through, and the render needs a flat stand-in for the design canvas.
3. Nothing in the repo anticipates the 2026 move. No spec, QA report or feedback file mentions the
   move, the Artifact tool, `moveState`, or a "Design" artifact. This spec is the first.
4. On the web, Anthropic's help centre now documents a **free project archive zip** ("Share >
   Project HTML > Project archive > Export") and a **move to Claude** (project becomes an artifact).
   Both are human-in-the-browser steps. Public links stop working at close; chats and comments do not
   move. Claude Code access to moved designs is not covered by that article.

## 1. Registrations done with the current command

Every one of these has a `design_prompt.md` (the handoff prompt), `design.md`, and usually
`design_source/` and `design_screenshots/`. The prompt always begins "Use the claude_design MCP
(https://api.anthropic.com/v1/design/mcp, auth via /design-login) to import this project:" followed by a
`https://claude.ai/design/p/<project-id>?file=<file>` link, "Focus on these files", "Also read these
files the selection imports", sometimes "Implement: `<file>`".

| Spec directory (under `spec_dd/`) | Design shape | Outcome |
|---|---|---|
| `3. done/2026-09-08_17:31_better-form-start-page` | first design; read by hand, before the command existed (`research_design_source.md`) | worked; produced the token-mapping table the later specs lacked |
| `1. next/user-communication` (consumed by `3. done/2026-09-27_00:24_user-communication-1-notifications-core`) | canvas (`User Communication.html` + `design-canvas.jsx`) | built to the design's structure; looked plainer than the mockup; see section 2 |
| `3. done/2026-10-01_20:38_better-looking-notifications` | same canvas, re-registered with source and screenshots | 10 artboard PNGs; QA compared each against them, all pass (`qa_report.md` rows `1.1-design` to `4.1-design`) |
| `3. done/2026-10-02_07:10_new-content-type-articles` | design_prompt + design.md | used in QA |
| `3. done/2026-10-05_08:22_article-images` | design.md | used in QA |
| `3. done/2026-10-08_06:54_educator-interface-looks-good` | project `34ae8997-...`, seven `.dc.html` pages plus `Sidebar.dc.html` and `support.js`; index page links to a `Blog.dc.html` "that the project no longer holds" | QA design rows: some pass, 3 fail on detail (header label colour, nav icon mapping, muted secondary line); then a `human_qa_report.md` said "The implementation does not match the design" and gave per-screen design-vs-built notes |
| `3. done/2026-10-22_20:02_user-communication-4-direct-messaging` | `.dc.html` | used in QA |
| `3. done/2026-10-30_19:36_design_learner_course_organisations` | `.dc.html` screens named `cards__b`, `index__ig2`, `detail__d1`, `detail__d6`, `stack__s1/s2` | QA design rows all pass at desktop, mobile and tablet |
| `3. done/2026-11-08_09:13_design_educator_interface_audit_log` | `Educator Audit History v2.dc.html` + `Sidebar.dc.html`, registered 2026-11-03; same project id as the educator interface design | QA design rows record misses (leading chevron vs plan, untinted detail panel, When cell wraps at 768), all traced to deliberate commit `22cd0717e` |
| `2. in progress/learner-facing-ux-refinements` | canvas (`Dashboard - Applications Entry Points.html`, `design-canvas.jsx`, `browser-window.jsx`, `ios-frame.jsx`) | QA design rows pass (`strip__strip-states.png`, `phone__p-dash.png`) |
| `2. in progress/design_educator-interface-bulk-action`, `2. in progress/educator-interface-design-learner-csv-upload-design-fix` | prompts only so far (`Educator Learners.dc.html`, `Educator Learner Import.dc.html`, same project `34ae8997-...`) | not yet registered; these are the live cases the new procedure must serve |

Two project shapes exist in practice: **canvas** projects (`DesignCanvas` / `DCSection` / `DCArtboard`
from `design-canvas.jsx`, artboard PNG named `<section-id>__<artboard-id>.png`) and **`.dc.html`**
projects (one Design Component page per file, fixed frames per screen, runtime `support.js`, PNG named
`<page>__<screen>.png`). This matches the platform facts file: the new "Design" Artifact type is the
`.dc.html` shape (`project/canvas.json` + `project/<path>.dc.html`), so `.dc.html` knowledge carries over
and the canvas-`jsx` knowledge is legacy.

## 2. What went wrong, and what was learned (with the source)

### 2.1 Fidelity failure on the first canvas registration
Source: `spec_dd/3. done/2026-10-01_20:38_better-looking-notifications/research_design_fidelity_forensics.md`.
- Claude Code **could** read the design at depth 0 (`register_design`, `spec_from_idea`,
  `plan_from_spec`). The tool is available in the main session but not to spawned subagents
  (`sdd-worker`, `qa-bugfixer`, probably the `general-purpose` implementation batches).
  Consequence for any new procedure: anything that must read the design live has to run at depth 0.
  **Reading the design from files in the repo removes that constraint**, which is the point of
  `design_source/` and `design_screenshots/`.
- The break was downstream: no step compared the built UI to the design; the "existing tokens win"
  policy had no worked method for keeping density and polish. Fix taken: register the source and
  screenshots, and add `*-design` rows to QA (`3. frontend_qa.md` "Design state: ..."), which now exist
  in every later QA report above.

### 2.2 Export routes were compared, and the browser-click routes lost
Source: `research_claude_design_export.md` (same spec). Findings, with their stated confidence:
- Documented: Export to .zip, standalone HTML, PDF/PPTX/Google Slides, send-to-tool, **handoff to
  Claude Code** (bundle "addressable by URL"). Not documented as agent-callable.
- `DesignSync` method surface (read: `list_projects`, `get_project`, `list_files`, `get_file`,
  256 KiB cap; write methods only for design-system projects). **No zip, export or render method.**
  Sourced from the unofficial Piebald-AI extraction, flagged "not officially confirmed".
- A standalone-HTML export reportedly inlines everything but can be about 17.6 MB (1,027 `@font-face`
  rules), far over the 256 KiB `get_file` cap.
- No native PNG export; only an unofficial Chrome extension or rendering locally with Playwright.
- Recommendation taken: keep `get_file` + `Write`, persist the output in the repo. Recommendation
  deferred and never spiked: "have the user hand off one design once and see what the bundle actually
  is". **That spike was never run**, so what a handoff bundle or a zip of a project contains is untested
  in this repo.

### 2.3 Rendering spike: what works and what does not
Source: `spec_dd/3. done/2026-10-01_20:38_better-looking-notifications/research_design_render_spike.md`
(2026-09-27). It became `claude_plugins/sdd/scripts/design_screenshots.sh` + `design_screenshots.py` and
`claude_plugins/sdd/resources/design_canvas_flat.jsx` (the script docstring says it replaces
`design-canvas.jsx` in the served copy, because the real canvas "pans and zooms, which leaves artboards
scaled and offscreen").
- Works: local `http.server`, Playwright element screenshot by selector, about 40 s for 10 artboards,
  PNGs 1x, about 830 KB total (under the 1 MB `check-added-large-files` limit).
- `file://` does not work (Babel-standalone fetches `text/babel` scripts by URL), so a local server is
  mandatory.
- React, ReactDOM, Babel and the icon font loaded from unpkg at render time, so rendering needs network.
- **Binary assets do not come through `DesignSync`**: `get_file` on a PNG returned base64 flagged
  `truncated: true`; the logo 404s and TTF fonts were not synced, so screenshots are not pixel-exact.
  Accepted, because FLS takes neither the design's fonts nor its logo.
- Rendering shows what reading code misses (a `.uc h2` rule beat `.uc-day`, so day headings render
  18px not 12px). Rationale for shipping screenshots, not only source.
- Every byte passes through the model (roughly 2x file size in tokens; a subtle copy error would not
  show). Rule that followed, now in `register_design.md` Step 2: write each file "whole and unedited".
- Non-canvas designs: fallback is a whole-page capture at 1280 and 375. Now implemented as
  `<page>__<width>.png`, plus `.dc.html` frame capture driven by each component's `$preview` props.

### 2.4 Pipeline-level decisions about the command
- `3. done/2026-10-12_20:53_sdd-improve` (`research_where_the_pipeline_stalls.md`): the only genuine
  stop in `register_design` is `/design-login` authorisation, "a human act"; kept as a question.
  The command was excluded from the "remove questions" fan-out changes.
- `3. done/2026-11-01_19:48_claude-plugin-tidy-up`: `design_screenshots.sh` moved from `fls-dev` to
  `sdd` (generic); `register_design.md` is among the longest command files (201 lines).
- `3. done/2026-11-08_12:35_sdd-improvements-combine-steps`: added `mode: hook`. `/sdd:start` registers a
  design when `<spec-dir>/design_prompt.md` exists and `design.md` does not; it loads `DesignSync`,
  calls `get_project`, and on an authorisation error asks "Run `/design-login` now, then choose Done" or
  "Register the design without reading it" (answer saved in `.sdd-work/`, a design registered "not yet
  read" with the coverage table so marked). Its research flagged: a chained command must also work
  standalone; a re-run must not re-register (step checks its own output); subagents cannot ask
  questions (`AskUserQuestion`), so the command stays at depth 0.
- Standing rules baked into `design.md` (identical across all registrations, "followed literally by
  later commands"): the design is a visual reference and never a source of scope; the project's theme
  wins over the design's; read repo copies first; use `DesignSync` only to re-register; never open the
  link with WebFetch, browser, Playwright or curl.

### 2.5 Smaller observations recorded in registrations
- The registered project can drift: the educator interface index links to `Blog.dc.html`, "a file the
  project no longer holds". The reference scan (Step 2.4) found and synced the real dependencies
  (`Sidebar.dc.html` via `<dc-import>`, `_ds/<design-system-id>/colors_and_type.css`,
  `_ds/.../_ds_bundle.js`, `support.js`).
- One Claude Design project id (`34ae8997-bfe5-4536-9ac7-46f01d3a12ff`) serves several specs (educator
  interface looks-good, audit log, bulk action, learner CSV upload fix), each registering a different
  file. Re-registration against a changed project is common (audit log is "v2").
- Design systems appear inside project files as `_ds/first-class-design-system-3-<uuid>/`, i.e. a design
  system is copied into the project. In the new Design artifact this corresponds to
  `project/ds/<folder>/tokens.json` and `designSystems[]` in `canvas.json` (platform facts file).

## 3. What the web says (as of 2026-11-08)

All of the following is Anthropic's own help article unless marked.

Source: [Migrate from standalone Claude Design to Claude](https://support.claude.com/en/articles/17440474-migrate-from-standalone-claude-design-to-claude)
- Standalone Claude Design (claude.ai/design) **closes 2026-12-14**; read-only afterwards, no new
  projects. Designs, design systems and decks "created in Claude become artifacts".
- **Design systems** move once for the whole organisation, from the Artifacts page. **Projects** move
  "gradually to paid plans". Only the project owner can move one. Flow: open project, start review from
  the pop-up or banner, read what moves/changes/stays (a .zip copy can be downloaded first), confirm and
  keep the tab open, open the project in Claude where it is an artifact. Team/Enterprise owners get
  "Move everything".
- After a move, the standalone copy is read-only for everyone and this cannot be undone.
- **Not moved:** chats with Claude, and comments on projects and design systems; empty and starter-theme
  design systems; public links stop working at close. Chats and comments are deleted "some time after"
  close. ZDR organisations cannot move projects (download first); HIPAA-ready configuration cannot move
  projects for now; artifacts must be enabled for Team/Enterprise.
- **Manual download of one project:** open it, Share, "Project HTML" (decks: "More formats and apps"),
  keep "Project archive" selected, Export. Result: a .zip of all project files, free, not counted toward
  usage. A full download of all owned projects is "rolling out" on the standalone home page, files only.
- The article does **not** cover Claude Code access to Claude Design or to migrated designs.

Secondary sources (third-party, treat as corroboration only):
- [How to Export Claude Design Projects Before December 14 (Hostsmith)](https://hostsmith.net/blog/claude-design-export/):
  same zip route; "Send to local coding agent" / "Send to Claude Code Web" in the Export menu; a `/design`
  command in Claude Code imports a design into a codebase; whether Export still works after 2026-12-14 is
  "undocumented"; the archive can include uploaded briefs and screenshots; chat is a loss, mitigated by
  asking Claude in the project to write a decision-log file into the archive.
- [Move the Design System Before December 14 (Tygart Media)](https://tygartmedia.com/?p=23600): written when
  projects had no migration path yet ("More details... coming soon"); no bulk download; Claude Design has
  no version history.
- Web search also returned [memorylake.ai on the site closing](https://www.memorylake.ai/blogs/claude-design-standalone-site-closing)
  and [layer3labs guide, updated 2026-10-11](https://www.layer3labs.io/guides/claude-design), not read in full.
  The latter reportedly says projects stay in standalone until 2026-12-14, which is now out of date
  against the Anthropic article; project moves are rolling out and not yet on every account.
- Older routes, from the 2026-09 research, still cited there: Anthropic announcement
  [Claude Design by Anthropic Labs](https://www.anthropic.com/news/claude-design-anthropic-labs), help
  article [Get started with Claude Design](https://support.claude.com/en/articles/14604416-get-started-with-claude-design),
  unofficial tool description [Piebald-AI tool-description-designsync.md](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-designsync.md),
  [Flowpoint handoff bundle explainer](https://flowpoint.ai/blog/claude-design-to-claude-code).

No web report was found of anyone registering a moved project into a repo via the Artifact tool; the
Artifact tool facts come only from the platform facts file.

## 4. Implications for the new procedure

- The repo's contract downstream is stable and should not change: `design.md` plus `design_source/`
  plus `design_screenshots/` (names `<page>__<screen>.png`), read at any depth, offline of claude.ai.
  Only the **intake** (how files reach `design_source/`) is broken.
- Candidate intakes, with what is already known:
  - **Artifact `read`/`list` by artifact URL** (platform facts): no browser click for the files, files
    saved locally, up to 256 paths per call, works for a design the user can read; for someone else's
    artifact only a summary is returned. Untested in this repo. Uploaded assets are separate (`/_blob/<id>`),
    which would fix the old "binaries do not come through" gap if `scope: "assets"` returns real bytes.
  - **Project archive zip** (Anthropic documented, human click, free, all files incl. binaries): a human
    drops the zip in the repo. Never tried here; the 2026-09 research ranked it option 3.
  - **`DesignSync get_project`** returns `moveState` and a `notice` for moved projects; per the tool text,
    quote the notice and stop. Keep as the fallback for projects not yet moved, until 2026-12-14.
  - **Handoff bundle / "Send to local coding agent"**: still unspiked, still unknown whether the bundle
    URL needs the browser session.
- The prompt format changes: the handoff prompt mentions the old `claude_design` MCP and
  `claude.ai/design/p/<id>` links, which stop working at close. Registrations already in the repo are
  unaffected (their files are local), but the two pending prompts (bulk action, CSV upload fix) are
  project `34ae8997-...` and need registering before 2026-12-14 or via the new route.
- Keep the lessons: write files whole and unedited; require network for unpkg at render time or vendor
  the runtime; screenshots must come from a local server, not `file://`; copy-errors are invisible, so a
  byte-exact route (zip, Artifact `read` saving to disk) beats retyping through the model.
- `.dc.html` knowledge (`$preview` sizes, `<dc-import>`, `support.js`) is already in
  `design_screenshots.py`. New Design artifacts keep `.dc.html` boards but add `project/canvas.json` as
  the index (boards, pages, order); the screenshot script currently finds screens from the HTML, so it may
  gain from reading `canvas.json`, and `support.js` is served by the platform from
  `artifact-type/dc-runtime.js` (not a project file), so a copied artifact may be missing the runtime the
  current script expects at `design_source/support.js`. Both are open questions for the spec, not
  findings.

## 5. Not confirmed

- Exact commit-level history of the three files (no `git log --follow`); the narrative above is from
  specs, not commits. Only commit `22cd0717e` and the 2026-09-26 commits quoted in the forensics file
  are named.
- Whether Artifact `read` on a Design artifact returns raw files for an artifact the user owns but that
  was moved from standalone Claude Design (needs a live test by the spec).
- Whether the project-move feature is available on this user's plan today.
- Whether `/design` in Claude Code (Hostsmith) exists and what it does; one third-party source only.

status: ok
