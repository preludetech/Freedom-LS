# Research: UX patterns for handing a design from a hosted design tool to a CLI coding agent

Topic `ux_patterns`. Web findings are mostly from Anthropic help pages (official) and third-party
blogs (marked unverified). Platform facts from the repo are in `.sdd-work/spec_from_idea_platform_facts.md`.

## 1. Claude Design now (official help page)

Source: https://support.claude.com/en/articles/14604416-get-started-with-claude-design

- Designs start **private to the owner**. **Share** lets the owner pick who can open it and what they
  can do: view, comment, or edit. Sharing cannot be changed in the mobile apps (web/desktop only).
  Team/Enterprise admins can restrict publishing and defaults.
- Handoff to Claude Code: **Export** (upper right) > **Handoff to Claude Code** > "Send to local coding
  agent" or "Send to Claude Code Web". The help page does not say what is copied or pasted.
- In Claude Code, `/design` can import a design into the codebase, export code as a live prototype, or
  build the whole design. `/design-sync` keeps a design system in sync (GitHub repo, design files,
  uploads, local codebase). The help page lists no `/design` arguments and does not say whether a link
  can be pasted.
- Designs now live in conversations, the Artifacts tab, Claude Code and the mobile apps. Standalone
  claude.ai/design **closes 14 December 2026**; moving projects to Claude is rolling out gradually to
  paid plans. Move guide: https://support.claude.com/en/articles/17440474 (steps not read).
- Enterprise: Claude Design on by default from 15 October 2026 (Organization settings > Artifacts).

Third-party (unverified, labels disagree):
- One guide puts "Handoff to Claude Code" under **Share**, with a **Copy Command** button that copies
  an instruction plus a URL to paste into the agent prompt: https://dev.to/bilelsalemdev/from-prompt-to-pull-request-using-claude-design-claude-code-and-github-together-3m00
  (found via search; not fetched). This matches today's "paste the handoff prompt" UX in `register_design`.
- Another says the export is a bundle (component spec, tokens, layout hierarchy, assets), not a PNG or
  Figma link: https://claudefa.st/blog/guide/mechanics/claude-design-handoff
- Artifacts are "private by default", viewable by authenticated org members only, share button in the
  page header; external sharing needs an export; `/login` is the only sign-in described, `/design-login`
  is not mentioned: https://dev.to/max_quimby/artifacts-in-claude-code-the-operators-guide-4fb0
- Community skills (not built in) take a handoff URL as the single argument, e.g.
  `/ork:design-import https://claude.ai/design/abc123` (OrchestKit): https://claudskills.com/skills/design-import/

Pattern to take: the human's job is one copy and one paste. What gets copied is either a prompt/command
that Claude Design generates (current `register_design` input) or an artifact link
(`claude.ai/artifact/{id}`, readable with the Artifact tool `read`). The exact current menu label is
unverified and must be re-checked in the live UI before the procedure is documented.

## 2. Figma (closest mature analogue)

Source: https://help.figma.com/hc/en-us/articles/35281350665623

- Prerequisite: full or Dev seat; at least view permission on the file. **If someone else owns the file,
  ask them to share it with you first.** No workaround is offered.
- Identify the selection: right-click the layer > **Copy link to selection** (the URL carries the node
  id), or copy the browser URL while a frame is selected. With nothing selected, the file URL means
  "whole file".
- Paste the link into the Claude Code prompt; the remote MCP server is link-based and scopes context to
  that node.
- Setup (once): `claude plugin install figma@claude-plugins-official`, or
  `claude mcp add --transport http figma-remote-mcp https://mcp.figma.com/mcp`, then authenticate
  through `/mcp` (browser OAuth). Search result: https://help.figma.com/hc/en-us/articles/35280968300439
- A desktop-server variant reads the current selection with no link at all
  (`http://127.0.0.1:3845/mcp`); the cost is that the human must keep that selection live.

Pattern to take: one link, selection granularity encoded in the link (node id), whole canvas = bare
link, and an explicit "ask the owner to share it" line for designs owned by someone else.

## 3. v0, Lovable, Bolt

- v0: **Add to codebase** shows a CLI command to copy and run in the repo, with the generation's URL in
  it (`npx shadcn@latest add <v0 url>` / `npx v0 add <url>`). Output lands as source files; no sync link
  back, re-running overwrites local files. Third-party, unverified: https://tools-3hx.pages.dev/en/v0-installation-setup-complete-guide-nextjs-shadcn-ui-en/
- Lovable/Bolt: the sync is a GitHub repo, so the human's step is connecting the repo once; the CLI side
  is a normal `git pull`. Not researched beyond that (no source fetched).

Pattern to take: copy-this-command-from-the-tool, paste in terminal; re-import is the same command and
is destructive by design, so the CLI should say which files it replaced.

## 4. Common shape of the procedure

1. One-time: sign in (CLI browser login: `/login`, `/mcp` OAuth, or `/design-login` for sessions without
   a claude.ai login).
2. In the tool: make sure you can open the design (owner shares at least view; otherwise ask owner).
3. In the tool: select one screen/artboard (or none for the whole canvas) and copy a link or a
   generated handoff prompt.
4. In the CLI: run the command with that pasted text as the argument.
5. CLI confirms and the human reviews.

Fewest-steps rule across tools: exactly one copy and one paste, no typing of ids, no second prompt.

## 5. How the CLI should report back (patterns)

- Name the source it resolved (title, owner or "yours", link/id) and whether it could edit or only view.
- List what it imported: file count and the screens/artboards found, by name. This is the human's check
  that the selection was what they meant (one screen vs whole canvas).
- Say plainly what it could not read (permission, closed standalone project, size cap) and what to do:
  ask the owner to share, run the login command, or move the project to Claude.
- Say what it wrote and where, and that it committed.
- Treat design content as data, not instructions (already in `register_design`).

## 6. Implications for the spec

- Today's command depends on `DesignSync` and `claude.ai/design/p/<id>` links, which close 14 Dec 2026;
  the replacement input is likely an artifact link (`claude.ai/artifact/{id}`) read with the Artifact
  tool (`list scope:files`, `read path(s)`), or a handoff prompt carrying such a link. Which one the
  "Handoff" button produces is the key open question; verify in the live UI.
- A selection inside a Design artifact is an artboard: `project/canvas.json` `boards` keys. A link
  that names one artboard versus the whole canvas needs a rule; the platform facts do not show whether
  the handoff link encodes a board. Open question.
- Someone else's artifact returns only an isolated summary, not raw files, so the permission procedure
  must tell the human to ask the owner for edit/writer access (or to duplicate it into their own
  account) before registering. The Figma "ask them to share it" line is the model.
- `/design-login` is DesignSync-specific; confirm whether the Artifact tool needs it at all (the tool
  uses the Claude Code login) before keeping the login prompt in the command.

## Sources

- https://support.claude.com/en/articles/14604416-get-started-with-claude-design
- https://help.figma.com/hc/en-us/articles/35281350665623
- https://help.figma.com/hc/en-us/articles/35280968300439
- https://claudefa.st/blog/guide/mechanics/claude-design-handoff
- https://dev.to/max_quimby/artifacts-in-claude-code-the-operators-guide-4fb0
- https://dev.to/bilelsalemdev/from-prompt-to-pull-request-using-claude-design-claude-code-and-github-together-3m00
- https://claudskills.com/skills/design-import/
- https://tools-3hx.pages.dev/en/v0-installation-setup-complete-guide-nextjs-shadcn-ui-en/

status: ok · reason: official Anthropic and Figma help read; Claude Design handoff button label, /design arguments, Lovable/Bolt and the move guide are unverified or not read
