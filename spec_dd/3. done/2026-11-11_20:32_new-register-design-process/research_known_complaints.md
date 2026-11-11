# Research: known complaints about getting AI-tool designs into a codebase for coding agents

Scope: Claude Design (and its move into Claude as Artifacts), plus brief notes on Figma MCP, v0,
Lovable, Figma Make. Platform baseline is `platform_facts.md`.

Evidence quality: the claudeissues.com pages are mirrors of anthropics/claude-code issues; only #51980
was confirmed on github.com (search tool output). I could not open claudeissues.com directly (DNS
failure), so issue details below come from search summaries. No maintainer fixes were seen. Many
blog and Reddit results are vendor marketing or low quality; treated as anecdotal.

## 1. Complaints with direct impact on `/sdd:register_design`

| # | Complaint | Evidence | What it means for the command |
| --- | --- | --- | --- |
| 1.1 | A design link is not fetchable by plain web tools. Share URLs return "not found" to unauthenticated clients; `claude.ai/design/p/...` returns only a login-walled app shell via WebFetch. | anthropics/claude-code #52292, #69239 (mirror). | The command must read artifacts only with the `Artifact` tool (`action: read`), never WebFetch or curl. The platform facts file states this rule too. Workers cannot call it, so reading stays at depth 0. |
| 1.2 | The generated handoff prompt assumes a "Claude Design connector" that local Claude Code lacks. It falls back to WebFetch and gets nothing. | #69246 (mirror). | Do not depend on the pasted handoff prompt. Take a link, then read through the tool. |
| 1.3 | "Send to Claude Code Web" opens a session with the design bundle but no way to connect a GitHub repo; also no GitHub MCP tools, so it can push a branch but not open a PR. | anthropics/claude-code #51980 (github.com), #84665, #90238 (mirrors). | The cloud handoff path is poor for a repo like this one. The documented human procedure should be "copy the artifact link into local Claude Code", not "Send to Claude Code Web". |
| 1.4 | Handoff bundle is one-time. Later design edits do not flow to code. Designs drift after handoff. | Search summary of the #69246 area; Reddit and blog anecdotes (see section 4). | Registration should snapshot the design (files plus screenshots) into the spec directory and record the artifact URL and date. State that later edits in Claude need a re-registration. |
| 1.5 | The standalone site closes 2026-12-14 and goes read-only. Public project links stop working then. Chats and comments are not migrated and are deleted afterwards. Moved projects become artifacts. | Anthropic help centre article 17440474. | Existing `claude.ai/design/p/<id>` links in `design.md` files will break. The command needs a clear message and a path for old registrations (open the moved artifact, or use the server's `notice`). Design intent held in chats and comments is lost, so the snapshot should include any design notes the user wants kept. |
| 1.6 | Migration rolls out gradually. HIPAA-ready orgs and ZDR orgs cannot move projects. Projects that cannot move stay in standalone, with reasons. Design systems that fail to move can be re-moved, but a later move does not update one already moved. | Help centre 17440474; tygartmedia.com summary. | The procedure must say which side a design is on (standalone project vs Artifact) and what to do if it will not move (export "Project HTML" zip). |
| 1.7 | No version history in Claude Design yet. Inline comments sometimes fail to appear. | tygartmedia.com summary of the help centre article. | Cannot rely on the platform to give a stable version. Record a copy date and, where possible, a content hash or file list in `design.md`. |
| 1.8 | `DesignSync` only lists design-system projects the user can write to, and `get_file` is capped at 256 KiB. Binaries (logo, fonts, images) come back truncated. | Platform facts file; the earlier idea (`better-looking-notifications/idea.md`) recorded the 256 KiB truncation. | The old path is not just closing but already narrow. Artifact assets live in an asset store and are fetched by id or path with `Artifact`, which has a different shape. A Design artifact allows 512 files / 256 MB, so size can still matter for a whole copy. |
| 1.9 | Artifact content owned by someone else comes back only as an isolated summary, not raw files. Only "writer" access gives full reads. | Platform facts file. | The user registering must have edit access to the artifact, or the command can only get a summary. State this as a prerequisite in the human procedure. |
| 1.10 | Private-by-default sharing. Private projects stay private after the move; sharing "carries over where Claude supports it". Oversharing risk: publishing a design system makes it visible to the whole org. | Help centre 17440474; tygartmedia.com. | Registration should not ask people to make a design public to get it read. Reading with the user's own login is enough. Warn against publishing as a workaround. |

## 2. Fidelity and "agent copies the design" complaints

- Handoff output forgets colours, shades or sizes in places (React Native example) and exports can omit
  screenshots or other items. A Reddit user reported "damn near perfect" results once the prompt given to
  Design was revised, and that having Claude Code ask clarifying questions first helped. Source: Reddit
  snapshots via reddit.sentinel-team.org (below). Anecdotal.
- Generated mockups carry their own spacing, radii and blue because the tool does not know the project's
  design system. Lovable and Claude "guess" at the system rather than respecting it. Sources: howaiworks.ai,
  UXPin, a LinkedIn post. Vendor-flavoured.
- AI-built frontends "look close but never match", leaving manual fixes to spacing, fonts and colours.
  Source: hunted.space listing (marketing for a diff tool).
- v0 defaults to shadcn/ui and can be pointed at a custom registry. That is the case where it works:
  the design system already exists as code. Source: howaiworks.ai.
- I found no sourced complaint specifically about invented scope from mockups for v0, Lovable or Figma
  Make. The search returned nothing on it. Do not claim it is documented externally; the evidence for
  invented scope is this repo's own (section 3).

## 3. Complaints found in this repo's own history

Sources are under `spec_dd/3. done/`.

1. Design chain did not break at reading; it broke at checking. Nothing after the plan compared the
   built UI to the design, and QA was behavioural only (`2026-10-01_20:38_better-looking-notifications/research_design_fidelity_forensics.md`).
2. The "existing tokens win" rule produced a correct structure that looked plainer than the mockup. There
   was no worked method (token mapping table, a "cannot be reproduced" list) to reconcile faithfulness with
   "never copy a raw value". The earlier `better-form-start-page/research_design_source.md` did that ad hoc
   (same forensics file).
3. Designers do not know the project's features, plans or theme, so the design invents controls, screens and
   data and styles them in another theme. Decision recorded: anything no spec asks for is left out, and the
   design is a visual reference only (`better-looking-notifications/idea.md`, section "Registration syncs the
   design, screenshots it and settles its scope").
4. `DesignSync` could not carry binaries (logo cut off at 256 KiB), so fonts and images were dropped and
   renders used fallbacks (same `idea.md`).
5. Copying files through the model is slow and costly, and exporting by hand each time was rejected as a
   burden (`research_claude_design_export.md`, `research_design_render_spike.md` in the same spec).
6. The tools needed to read the design are only available at depth 0. Subagents (research workers, QA
   bug-fixer, implementation batches) could not load them. So snapshots on disk (source plus screenshots)
   are what later steps can actually use (forensics file; `sdd-worker.md` tool list).
7. `implement_plan.md` and `do_qa.md` did not mention the design. The later work added screenshot
   comparison; any new design.md format must keep the paths those steps read.
8. Hook-mode conventions from the last spec: `AskUserQuestion` is unavailable in subagents, so the
   registration step must return `blocked` plus `needs` rather than ask; scratch answers go under
   `.sdd-work/` (`2026-11-08_12:35_sdd-improvements-combine-steps/research_known_complaints.md`, rows 2.1, 2.4, 6.1).

## 4. Other tools (brief)

- Figma MCP: rate limits are the most common complaint on Figma's forum, including paid Dev and Full
  seats still seeing starter-level limits, and "try again tomorrow" after an agent repeatedly called
  `get_screenshot`. Claude Code caps MCP tool output at 25,000 tokens by default, so `get_design_context`
  can fail on large frames. Advice: call `get_metadata` first, then fetch sub-nodes. Large whole-file reads
  without `nodeId` return megabytes. Also: auth errors ("this figma file could not be accessed"),
  "Claude MCP stopped working on Pro plan" forum threads.
- Nothing sourced on Figma Make export limits or hardcoded values in generated code (not found).
- Lesson that transfers to registration: fetch designs in small pieces by id, avoid whole-project reads, and
  save files to disk once rather than re-fetching (rate and size limits).

## 5. Implications for the spec (summary)

1. Read via the `Artifact` tool only; never WebFetch, curl, or the pasted handoff prompt.
2. Requires the user to have edit ("writer") access and to give a `claude.ai/artifact/...` link.
3. Snapshot to disk at registration (files via `read` with `paths`, or `list` then `read`), because
   subagents cannot read artifacts and the source is the only stable thing (no version history).
4. Record artifact URL, copy date, and file list in `design.md`; say re-registration is needed after edits.
5. Handle the old URL form and the closure date gracefully, with the server message given as written.
6. Never publish or make a design public to make it readable.
7. Keep the "visual reference only, project theme wins, no invented scope" policy and screenshot
   comparison already built; the complaints above (fidelity drift, invented scope) support keeping it.
8. Screenshots must be produced by the command itself (bundles may omit them).
9. Guard against size: a canvas can hold 512 files / 256 MB; fetch only the boards the spec owns.

## References

- https://support.claude.com/en/articles/17440474-migrate-from-standalone-claude-design-to-claude.md
- https://tygartmedia.com/?p=23600
- https://claudeissues.com/issue/52292-claude-design-share-urls-return-not-found-to-unauthenticated-clients-blocks-clau
- https://claudeissues.com/issue/69246-bug-claude-design-send-to-local-coding-agent-handoff-fails-generated-prompt-reli
- https://claudeissues.com/issue/69239-claude-design-links-claude-ai-design-p-no-longer-resolve-natively-in-claude-code
- https://github.com/anthropics/claude-code/issues/51980
- https://claudeissues.com/issue/84665-bug
- https://claudeissues.com/issue/90238-bug-claude-code-on-the-web-claude-design-handoff-session-can-push-a-branch-but-h
- Reddit snapshots: https://reddit.sentinel-team.org/posts/1tm9ogt/snapshots/2026-05-30T02%3A41%3A26.708778Z , https://reddit.sentinel-team.org/posts/1t7d5ln/snapshots/2026-05-09T02%3A30%3A12.086538Z
- https://www.forgenex.com/en/blog/anthropic-redise-a-claude-design-para-cerrar-la-brecha-entre-dise-o-y-c-digo-soluci-n-o-espejismo
- https://howaiworks.ai/use-cases/ai-for-ui-mockups
- https://www.uxpin.com/studio/blog/ai-design-tool-enterprise-design-systems/
- https://hunted.space/product/visdiff
- https://forum.figma.com/report-a-problem-6/figma-mcp-rate-limit-exceeded-please-try-again-tomorrow-51927
- https://forum.figma.com/report-a-problem-6/mcp-error-this-figma-file-could-not-be-accessed-54505
- https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/
- https://camoa.github.io/dev-guides/ai-tooling/figma-mcp/limitations-and-workarounds
- Repo: `spec_dd/3. done/2026-10-01_20:38_better-looking-notifications/{idea.md,research_design_fidelity_forensics.md,research_claude_design_export.md}`;
  `spec_dd/3. done/2026-11-08_12:35_sdd-improvements-combine-steps/research_known_complaints.md`

status: ok · reason: complete; claudeissues.com pages not directly fetched (DNS), details from search summaries
