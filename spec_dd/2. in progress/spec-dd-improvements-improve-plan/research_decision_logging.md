# Research: Decision logging patterns for SDD subagent workflows

## 1. ADRs — light vs heavy variants

Michael Nygard's original ADR (2011) is already pretty light: **Title, Status, Context, Decision, Consequences** — five fields, no more ([cognitect.com][1], [joelparkerhenderson template][2]). It is intended for "architecturally significant" decisions and is filed under `doc/arch/adr-NNN.md`.

**MADR** (Markdown Any Decision Records) explicitly genericises this for any decision. It ships four template variants: full, minimal-with-explanations, bare, and bare-minimal — the bare-minimal template keeps only the mandatory parts ([adr.github.io/madr][3], [github.com/adr/madr][4]). Notably MADR was renamed from "Markdown Architectural Decision Records" to "Markdown **Any** Decision Records" precisely because teams were using it for non-architectural decisions ([ozimmer.ch][5]).

**Y-statements** compress an entire ADR into one sentence: *"In the context of \<X\>, facing \<concern\>, we decided for \<option\> (and against \<alternatives\>) to achieve \<quality\>, accepting \<downside\>."* ([medium.com/olzzio][6], [socadk.github.io][7]). This is the smallest format that is still useful — it forces context, alternative, and trade-off to coexist in one line.

**Verdict for plan-level decisions inside a single feature: full ADR is overkill.** A plan touches dozens of micro-decisions; a separate `adr-NNN.md` per choice would drown the audit trail. Y-statement-style one-liners (or 4-line MADR-bare-minimal blocks) are the right granularity.

## 2. Decision logging in agentic / LLM-driven workflows

- **GitHub Spec Kit** keeps decisions inline in `research.md` using a fixed three-line block: `Decision: [what] / Rationale: [why] / Alternatives considered: [what else]`. There is no separate decisions.md — the rationale lives next to the technical plan it justifies. Spec Kit also forces the agent to write `[NEEDS CLARIFICATION]` markers rather than guess silently, and its "Constitutional Gates" require explicit justification in a Complexity Tracking section when principles are violated ([spec-driven.md][8], [plan.md template][9]).
- **Aider** records every change as a Conventional Commit. Decisions are encoded in commit subjects/bodies — the audit trail is `git log`, not a markdown file. This works because Aider's unit of work is one edit, not a multi-step plan ([aider.chat/docs/git][10]).
- **Cursor Memory Bank** uses structured per-purpose files: `systemPatterns.md` for architecture decisions, `activeContext.md` for current work, `progress.md` for ongoing tasks. Decisions are **filed by topic, not chronologically** ([lullabot.com][11], [github.com/vanzan01/cursor-memory-bank][12]).
- **Claude Code subagents** typically keep an in-conversation hooks log plus markdown notes per agent; Anthropic's docs note that subagents "include memory instructions directly in the markdown file so they proactively maintain their own knowledge base" ([code.claude.com/docs][13]).

The pattern across all four: **rationale lives close to the artefact it justifies.** No serious agentic tool puts decisions in a fully separate registry.

## 3. Inline callouts vs separate file

| | Pro | Con |
|---|---|---|
| Inline (`> [!NOTE] **Decision:** …`) | reader sees the *why* next to the *what*; survives plan rewrites only if the section survives | gets lost during full plan rewrites; hard to enumerate |
| Separate `decisions.md` | enumerable, auditable as a list, survives plan rewrites | disconnected from the section it affects; tends to rot |
| Both (linked) | best of both | duplication risk |

GitHub natively renders five blockquote-based alert types (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) — these are the cheapest visual distinguisher available without leaving Markdown ([github.blog changelog][14], [docs.github.com][15]).

Production teams in agentic workflows (Spec Kit, Cursor) use **inline-near-context plus enumerable index**: decisions live inline at the point they apply, and a top-of-file or sibling index links back. Pure separate-file logs are only used when decisions span features (e.g. project-wide ADR repo) — not for plan-level micro-decisions.

## 4. Record what? Confirmed vs auto

The MADR primer notes that decision records should optionally capture *"the team agreement on the decision (including the confidence level)"* ([ozimmer.ch][5]). This is the hook for differentiating user-confirmed from auto-decided.

The cleanest distinction I found in practice is:
- **`[!IMPORTANT]` / "User-confirmed"**: user answered a question explicitly. Reviewer can skim past.
- **`[!WARNING]` / "Auto-decided"**: agent made a judgement call without asking. Reviewer must check.
- **`[!NOTE]` / "Open question"**: agent flagged it but did not decide (Spec Kit's `[NEEDS CLARIFICATION]` pattern, [spec-driven.md][8]).

This three-bucket split maps directly onto GitHub's native alert colours, so the user can scan a plan visually and see exactly what needs review.

## 5. Concrete recommendation

**Use inline callouts at point of application + an auto-generated index at the top of the plan file. No separate `decisions.md`.**

- **Where**: inline GitHub-style alert immediately under the section the decision affects. At the top of the plan, a `## Decisions index` section with one bullet per decision linking to its anchor. The index is regenerated, not hand-maintained.
- **Fields** (Y-statement-derived, MADR-bare-minimal): `id`, `kind` (user-confirmed / auto / open-question), `date`, `asker` (which subagent raised it), `context` (1 sentence), `decision`, `rationale`, optional `alternatives`, optional `revisit-if`.
- **Visual distinction**: `[!IMPORTANT]` for user-confirmed, `[!WARNING]` for auto-decided judgement calls, `[!NOTE]` for unresolved questions. The reviewer's rule: **every `[!WARNING]` must be eyeballed; `[!IMPORTANT]` can be skimmed; `[!NOTE]` must be answered before plan freeze.**
- **Override path**: user edits the callout in-place, flips `kind: auto` to `kind: user-confirmed`, optionally amends rationale. No tool ceremony.

### Concrete example

```markdown
> [!WARNING]
> **Decision D-007 (auto)** — *plan-reviewer subagent, 2026-04-27*
> **Context:** Plan needs a place to store subagent decisions so the user can audit them.
> **Decision:** Inline GitHub-alert callouts + auto-generated index at top of plan.md.
> **Rationale:** Keeps rationale next to the section it justifies; index gives auditability without a stale separate file.
> **Alternatives considered:** separate `decisions.md` (rejected: drifts), commit-message-only (rejected: not visible in plan review).
> **Revisit if:** plan files routinely exceed ~500 lines and inline density becomes noisy.
```

A `[!IMPORTANT]` block uses the same shape but reads `**Decision D-008 (user-confirmed)** — *asked by plan-reviewer, answered by user, 2026-04-27*`.

---

## Sources

- [1] [Cognitect — Documenting Architecture Decisions (Nygard, 2011)](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [2] [joelparkerhenderson — Nygard ADR template](https://github.com/joelparkerhenderson/architecture-decision-record/blob/main/locales/en/templates/decision-record-template-by-michael-nygard/index.md)
- [3] [adr.github.io/madr — About MADR](https://adr.github.io/madr/)
- [4] [github.com/adr/madr](https://github.com/adr/madr)
- [5] [ozimmer.ch — MADR Template Primer](https://www.ozimmer.ch/practices/2022/11/22/MADRTemplatePrimer.html)
- [6] [Olaf Zimmermann — Y-Statements](https://medium.com/olzzio/y-statements-10eb07b5a177)
- [7] [Design Practice Repository — ADR Y-Form](https://socadk.github.io/design-practice-repository/artifact-templates/DPR-ArchitecturalDecisionRecordYForm.html)
- [8] [github/spec-kit — spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)
- [9] [github/spec-kit — plan.md template](https://github.com/github/spec-kit/blob/main/templates/commands/plan.md)
- [10] [Aider — Git integration docs](https://aider.chat/docs/git.html)
- [11] [Lullabot — Cursor Rules and Memory Banks](https://www.lullabot.com/articles/supercharge-your-ai-coding-cursor-rules-and-memory-banks)
- [12] [vanzan01/cursor-memory-bank](https://github.com/vanzan01/cursor-memory-bank)
- [13] [Anthropic — Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [14] [GitHub Changelog — Alerts markdown extension](https://github.blog/changelog/2023-12-14-new-markdown-extension-alerts-provide-distinctive-styling-for-significant-content/)
- [15] [GitHub Docs — Basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
