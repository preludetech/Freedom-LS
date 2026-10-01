# Research: is there a cheaper route than `get_file` + retype to get a Claude Design project onto disk

## 1. What export/handoff options Claude Design documents

All of this is **documented** (Anthropic's own help centre and announcement post), not inferred, unless
marked otherwise.

| Route | What it is | Source |
|---|---|---|
| **Export → Download as .zip** | "the raw assets from your design" — files, presumably including images/fonts as binary files inside the archive, not base64 text | Help Centre; AI For Developers write-up |
| **Export → standalone HTML** | "a quick shareable preview... a live interactive prototype someone can click through" | Help Centre |
| **Export → PDF / PPTX / Google Slides** (Slides is claude.ai/design only) | static document/slide formats, not source code | Help Centre, Anthropic announcement |
| **Share as organisation-scoped URL** | internal sharing, not a code artifact | Anthropic announcement |
| **Send-to-tool handoff** (Adobe Experience Manager/Adobe for Creativity/Journey Optimizer, Base44, Canva, Gamma, HubSpot, Hyperframes, Lovable, Miro, Netlify, Replit, v0, Vercel, Wix) | exports/pushes the design into a third-party tool | Help Centre |
| **Handoff to Claude Code (local or Claude Code Web)** | "Claude packages everything into a handoff bundle that you can pass to Claude Code with a single instruction" — the bundle carries the design files, the chat that produced the design, and a README/prompt including the bundle's URL; it is "addressable by URL" | Anthropic announcement (`anthropic.com/news/claude-design-anthropic-labs`); corroborated by Flowpoint's explainer |
| **`/design-sync` (Claude Code slash command)** | **documented, but for a different project type.** It imports a *design system* (tokens + component manifest) from a GitHub repo/local codebase *into* Claude Design, or, per the Help Centre's own wording, lets Claude "build with your real design system components" and "check its own output against" them. This is the tokens/components sync path, not the "read a finished mockup canvas back out" path this spec needs | Help Centre; corroborated (with caveats — see below) by third-party write-ups |
| **`/design-login`** | the auth step `register_design.md` already names, for when `DesignSync` needs re-authorisation | project's own `register_design.md`; not separately documented by Anthropic outside the tool's own error message, as far as this search found |
| **`DesignSync` (the MCP tool actually driving `register_design.md`)** | the tool used today. Its real method surface, from a leaked/extracted system-prompt repo (see caveat below): `list_projects`, `get_project`, `list_files`, `get_file` (256 KiB cap) as read methods, plus `create_project`, `finalize_plan`, `write_files` (upload, max 256 files/call), `delete_files`, `register_assets`/`unregister_assets` (legacy) as write methods for **design-system** projects. **No zip/export/screenshot/render method exists in this tool's surface at all.** | `github.com/Piebald-AI/claude-code-system-prompts` (`tool-description-designsync.md`) — see honesty caveat below |

**Honesty caveat on the DesignSync method list:** the Piebald-AI repo presents itself as extracted
Claude Code system-prompt/tool-description text, not an Anthropic-published API reference. I could not
find an official Anthropic page enumerating `DesignSync`'s methods to cross-check it against. Treat the
method list as **probably accurate** (it matches exactly the method names `register_design.md` itself
already calls — `get_project`, `list_files`, `get_file`, the 256 KiB cap, and the read-only framing) but
**not officially confirmed**. If real, it settles question 3 below firmly: this tool cannot render or
zip anything, only fetch individual file bytes into context.

## 2. Standalone HTML: does it still need the CDN?

**Documented, with one contradiction I could not resolve.** The Anthropic help centre and announcement
just say "standalone HTML," without detailing whether it inlines everything. Two independent, more
technical (but non-Anthropic, unverifiable-provenance) Japanese blog write-ups dissecting an actual
downloaded standalone-HTML export report:
- It is "truly self-contained": common libraries (their example used `marked.js`/`highlight.js`-type
  helper libraries and a syntax theme) are inlined, "no CDN, no web fonts, no network access required."
- Fonts are inlined too, but wastefully: ~1,027 `@font-face` rules, because the export embeds every
  weight × Unicode-range subset a Google-Fonts-style delivery would ship, not just the glyphs used —
  hence one such export is reportedly ~17.6 MB despite being visually simple. It behaves like a
  "self-extracting archive" (one HTML file, but JS unpacks embedded asset blobs at load time) rather
  than a normal single-page HTML file with a `<link>` to a stylesheet.
- One write-up also noted the export process itself pulls from an Anthropic-internal CDN for the font
  files at *export time*, but the resulting downloaded file needs no network access to *view*.

This is consistent with what the project's own design canvas comment says ("Reads go via plain
`fetch()`... visible anywhere the HTML + sidecar are served together") for the *editable, multi-file*
canvas form, and is a materially different, already-flattened artifact: the "-standalone.html" files
already present in this design project's file listing (`Course Index - All Views (standalone).html`,
etc., alongside `... -standalone-src.html`) are very likely this export, already sitting inside the
project as a file `DesignSync.get_file` can read — meaning it may already be reachable through the
existing tool without needing the browser-only Export button at all. **Not confirmed**: whether the
in-project "-standalone.html" file is byte-identical to what the Export button produces, or a
lighter/different variant the designer saved by hand; and whether it still resolves the React 18 UMD /
ReactDOM / Babel-Standalone `<script src="https://unpkg.com/...">` tags the entry canvas file uses (the
non-standalone entry file definitely still hits `unpkg.com` per the project's own evidence — a real,
external CDN dependency, separate from the font-CDN question above).

## 3. Can Claude Design render/export artboards as PNG itself?

**No native PNG/image export exists in the product**, per multiple independent write-ups (a Chrome-store
listing's own pitch is exactly "PNG exporter" as an add-on, which wouldn't be a product if the native
export covered it; a How-to piece states outright "Claude Design does not have a direct export button
for image formats"). The two documented ways people get PNGs today:
1. A **third-party, unofficial Chrome extension** ("Claude Design PNG Exporter") that runs in the
   browser against the open project and renders/saves a PNG per page — requires a human with the
   extension installed, driving the browser UI. Not something Claude Code can trigger.
2. **Route it through the Claude Code handoff**: the "hand off to Claude Code" button generates a
   prompt; pasted into Claude Code, the agent is meant to open/render each artboard itself (implicitly
   via a browser-automation tool it already has, e.g. Playwright) and produce the PNGs. This matches
   this project's own `register_design.md`/QA convention of using Playwright MCP for screenshots, and
   matches the earlier `research_design_fidelity_practices.md` finding (recommendation 4) that a locally
   served static copy + Playwright is plausible but unverified for *this* project's canvas format.

So: no built-in render/screenshot API exists to call from outside a browser; every documented path to a
PNG still ends in "a browser (real or Claude-Code-driven-via-Playwright) opens the HTML and something
takes a screenshot."

## 4. Can any of this be done by Claude Code without a user click in the browser?

- **`DesignSync`'s read methods (`get_file`/`list_files`) — yes, already automatic.** This is exactly
  what `register_design.md` does today: no browser, no user click, but the cost is retyping via `Write`
  and the 256 KiB cap.
- **The Export button (zip/standalone HTML/PDF/PPTX/Slides) — documented only as a browser UI action** (Help
  Centre describes it as a button in the project's "..." menu). No search result showed this exposed
  through the MCP tool or any CLI/API the agent can call directly; the DesignSync method list above has
  no export/download/zip method. **This must be user-clicked**, then the resulting file dropped
  somewhere Claude Code can `Read` it (e.g. the user's Downloads folder, or pasted into the repo) —
  exactly the "user has to click an export and drop the file into the repo" case the question anticipated.
- **The "handoff to Claude Code" bundle — ambiguous, leaning toward still needing a browser click.**
  Anthropic's own description says a *user* clicks "hand off to Claude Code" in the design UI, which
  generates a prompt (including the bundle's URL) for the user to paste into Claude Code. Nothing found
  says Claude Code can request that bundle unprompted, or that the bundle's URL is fetchable without the
  claude.ai session (unlike DesignSync's authenticated MCP calls, a plain URL fetch would need the
  browser's cookies unless it is a signed/pre-authenticated link — **not confirmed either way**). Even
  once pasted, whether Claude Code fetches the bundle over plain HTTP with `curl`/`WebFetch` (cheap, no
  retyping) or is still expected to call it through an MCP tool (subject to the same context-size
  economics as `get_file`) is not stated anywhere found. Given `register_design.md`'s own hard rule that
  the claude.ai page needs the user's login and must never be opened by `WebFetch`/browser/`curl`, the
  safe assumption is that a handoff-bundle URL carries the same restriction until proven otherwise.
- **`/design-sync` — real, but the wrong direction/project type for this need.** It documented moves a
  *design system's* tokens and component manifest between a repo and Claude Design, largely repo → design
  and design-conformance-checking back, not "pull this finished mockup canvas's arbitrary files to disk."
  It is also gated to "design-system" type projects (`get_project`/`create_project` in the DesignSync
  method list distinguish project types), and this repo's registered designs are the other kind (a
  canvas of artboards, per `design.md`'s own "Made of" file lists).

## 5. Recommendation, ranked

**Ranked cheapest-and-most-reliable first, for getting (a) source files and (b) rendered artboard
images into a spec directory:**

1. **Keep `get_file` + `Write` for source, but only for what fits it and only once, into a permanent
   `design_extract/` (as `research_design_fidelity_practices.md` recommendation 1 already proposes).**
   This is the only route this research can **confirm** works end-to-end without a user click, today,
   with this project's actual tool. It costs roughly 2x tokens per file (read once, write once) and a
   256 KiB/file cap, but it is deterministic and needs no new integration. **Established fact, not
   inference** — it's exactly what `register_design.md` already does; the only change is persisting the
   output instead of letting it evaporate at the end of the depth-0 session.
2. **If the design project already contains a `*-standalone.html` file for a screen (as this project's
   own listing shows for several), `get_file` *that* file instead of the multi-file source.** One file,
   already self-contained (per §2), likely renders correctly from a plain local static server without
   needing the other `.jsx`/`.css` siblings or a live `fetch()` of them — which sidesteps the CORS/
   `file://` and module-format risks `research_design_fidelity_practices.md` recommendation 4 flagged for
   the raw canvas source. Still costs the same retype-via-`Write` toll as anything from `get_file`, and
   still risks the 256 KiB cap on a large, font-bloated standalone file (one dissected example was
   ~17.6 MB — **far** over the cap, so a truncation check is mandatory, and a large standalone export may
   simply not fit through `get_file` at all). **Inference**, building on the (unverifiable-provenance but
   internally consistent) dissection write-ups plus the project's own file-naming evidence.
3. **Ask the user to click Export → zip (or standalone HTML) once in the browser and drop the result
   into the repo, then have Claude Code `Read` it from disk.** This is the only route to a byte-exact
   copy of binary assets (fonts, PNG logos) without any base64-in-context detour, and the only documented
   way to get the *whole* bundle (not per-file, not capped at 256 KiB) — at the cost of a manual step the
   user has to perform, which is exactly the trade-off the research question anticipated. **Documented**
   as an available export, but the "drop it in the repo, then Read it" mechanics are this research's own
   proposal, not something Anthropic documents as a Claude-Code workflow.
4. **The "handoff to Claude Code" bundle — plausible but unverified; do not build on it yet.** If its URL
   turns out to be fetchable without the browser session (unconfirmed), this would be strictly better
   than option 1 (no per-file retyping, no 256 KiB cap, includes binary assets natively) while still
   needing a user click to generate the bundle in the first place (per §4, not fully automatic either).
   Worth a cheap manual spike — have the user hand off one design once and see what the bundle actually
   is — before relying on it in a command.
5. **Rendering artboards to PNG — no native/automatable export exists (§3).** The only two documented
   routes are a third-party Chrome extension (manual, browser-only, unofficial) or Claude Code itself
   opening the (locally saved, per option 1/2/3 above) HTML with a browser-automation tool it already has
   (Playwright, per this project's own QA conventions) and screenshotting it. The latter is the
   recommended route **if** option 2's standalone HTML renders without a live server (best case: open
   directly, still subject to the `file://` CORS caveat `research_design_fidelity_practices.md` already
   flagged) or via a throwaway static server otherwise. This still needs the bounded, one-screen spike
   that file already recommended — nothing found here removes that uncertainty.

**Compared with "the model re-types each `get_file` result":** every route above except #3 (manual
zip/HTML drop) and the unverified #4 (handoff bundle) is a variation on that same mechanism — this
research did not find a documented way for Claude Code to pull a whole project or a binary asset out of
Claude Design **without** either (a) a human clicking Export in the browser once, or (b) the model paying
the read-then-retype token cost per file through `DesignSync.get_file`. The standalone-HTML shortcut
(#2) reduces *how many* files need that retype-toll (one instead of several), not the toll itself, and
only helps if the file fits the 256 KiB cap.

## What this research could not confirm

- Whether the `DesignSync` method list (§1) is accurate and current — sourced from an unofficial,
  extracted-system-prompt repo, not an Anthropic API reference.
- Whether the in-project `*-standalone.html` files (already visible in this design's file listing) are
  identical to what the Export button produces, or a designer-saved variant.
- Whether a "handoff to Claude Code" bundle URL is fetchable by `curl`/`WebFetch` without the user's
  claude.ai session, and whether Claude Code is meant to fetch it directly or via another MCP call
  subject to the same per-file economics as `get_file`.
- Whether this project's own multi-file canvas source (the non-standalone `.jsx`/`.css` files) would
  render at all from a local static server (module format, CORS) — carried over unresolved from
  `research_design_fidelity_practices.md`.
- Real file sizes/byte layout of a zip export for *this specific* project — no export was performed as
  part of this research (no browser access to the user's claude.ai session).

## References

- [Get started with Claude Design — Claude Help Center](https://support.claude.com/en/articles/14604416-get-started-with-claude-design)
- [Introducing Claude Design by Anthropic Labs — Anthropic](https://www.anthropic.com/news/claude-design-anthropic-labs)
- [How to Actually Use Claude Design — AI For Developers (Substack)](https://aifordevelopers.substack.com/p/how-to-actually-use-claude-design)
- [Claude Design to Claude Code: The Handoff Bundle Explained — Flowpoint](https://flowpoint.ai/blog/claude-design-to-claude-code)
- [Claude Design: The Handoff Is the Feature — Ready Solutions AI](https://readysolutions.ai/blog/2026-04-24-claude-design-handoff-not-canvas/)
- [Claude Design to Claude Code: the handoff bundle explained — moodspec.app](https://moodspec.app/guides/claude-design-to-claude-code)
- [tool-description-designsync.md — Piebald-AI/claude-code-system-prompts (unofficial, extracted; not an Anthropic reference)](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-designsync.md)
- [Claude Code and Claude Design Now Sync Both Ways with /design-sync — pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/5308/claude-code-claude-design-two-way-sync-design-sync)
- [Claude Design + /design-sync: The Two-Way Bridge Between Design and Code — skills-hub.ai](https://skills-hub.ai/blog/claude-design-sync-code-handoff-2026)
- [Claude Design's `/design-sync` Makes Claude Design and Claude Code a Two-Way Workflow — AI Catchup](https://aicatchup.com/news/claude-design-sync-claude-code-two-way)
- [\[Claude Design\] Dissecting the contents of a standalone HTML — 真夜中のまるさん (note.com)](https://note.com/marumaru_blog/n/n9c0916caf8a2?hl=en)
- [claude-design-mcp — unofficial third-party MCP server, not Anthropic's; mentions "screenshot rendering" as a feature it adds (github)](https://github.com/Evilander/claude-design-mcp)
- [Claude Design PNG Exporter — Chrome Web Store (unofficial, browser-only, manual)](https://chromewebstore.google.com/detail/claude-design-png-exporte/ogdpeekalogggfdbmbhigmmjoheogocj)
- [How to Export Designs and Generate PNGs with Claude Code — PandaiTech](https://pandaitech.my/alpha/how-to-export-designs-and-generate-pngs-with-claud-2731eb70)

## Sources read directly in this repo (not web)

- `claude_plugins/sdd/commands/register_design.md`
- `spec_dd/1. next/user-communication/design.md`
- `spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`
- `spec_dd/2. in progress/better-looking-notifications/research_design_fidelity_practices.md`
- `spec_dd/2. in progress/better-looking-notifications/research_design_fidelity_forensics.md`

status: ok
