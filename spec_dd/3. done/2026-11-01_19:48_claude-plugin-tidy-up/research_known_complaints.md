# Research: known complaints (claude-plugin-tidy-up)

Evidence is from web search summaries only; I did not open the pages, and figures conflict across sources. Verify against current Claude Code docs and changelog before relying on any number.

## Complaints found

### 1. Skill description budget silently truncates routing info
- When the total skill listing exceeds a budget, descriptions are dropped or shortened with no warning. Some skills show as names only, so they never route.
- Cited budgets conflict: about 8,000 characters (1% of context, `skillListingBudgetFraction = 0.01`) versus a 15,000-character cap in blogs.
- Per-description cap is also reported inconsistently: 250 characters in one GitHub issue, 1,536 in a blog.
- Overlapping descriptions let one skill outrank another.
- Implication here: moving about 40+ skills into plugins adds to the same listing. The `fls-dev` "Use alongside ds:X ..." descriptions are long, near-duplicate, and front-load boilerplate ("FreedomLS-specific extension of the ds:X skill"). Put the distinguishing trigger words early and keep each description short.
- Sources:
  - https://claudeissues.com/issue/64606-skill-description-budget-silently-truncates-routing-information-causing-skill-ro
  - https://claudefa.st/blog/guide/mechanics/skill-listing-budget
  - https://github.com/anthropics/skills/issues/881
  - https://dev.to/dev_encyclopedia/claude-code-skill-not-triggering-here-are-the-5-actual-causes-laj

### 2. Plugin skills not discovered or loaded
- anthropics/claude-code#44120 (closed May 2026): a `.claude/` directory inside a plugin makes discovery ignore the plugin's `skills/` root. Symlinks did not help.
- #36646: `/reload-plugins` reported 0 skills despite valid SKILL.md files (v2.1.80).
- #20993: with `CLAUDE_CONFIG_DIR` set, plugin skills fail to load, including via `--plugin-dir`, while commands still work.
- Typical fixes: clear the marketplace cache, check that SKILL.md exists, check `enabledPlugins`.
- Implication: after the move, check each new skill with `--plugin-dir` and `/reload-plugins` or `/skills`. Make sure no plugin directory contains a `.claude/` directory.
- Sources:
  - https://github.com/anthropics/claude-code/issues/44120
  - https://claudeissues.com/issue/36646-bug-plugin-skills-not-loaded-despite-correct-directory-structure-new-telegram-pl
  - https://claudeissues.com/issue/20993-skills-not-loaded-when-using-claude-config-dir-environment-variable
  - https://skills.cat/skills/daymade/claude-code-skills/claude-skills-troubleshooting

### 3. Namespacing (`plugin:skill`) and project-vs-plugin precedence
- Plugin skills are invoked as `plugin:skill`. Anything that refers to a moved skill by bare name (commands, agents, other skills, CLAUDE.md, `skills:` frontmatter) is a likely breakage.
- I found no concrete issue on duplicate or precedence behaviour between `.claude/skills/` and plugin skills. This is a gap, so it needs a test in the spec rather than an assumption.
- Safest approach: delete the project copy when moving it, and grep the repo for old bare names afterwards.
- Source: https://pypi.org/project/claude-skills-doctor/0.6.0/ (mentions the namespace only; no evidence on its effect on triggering).

### 4. Verbose CLAUDE.md and skills waste context and lower adherence
- The docs reportedly suggest about 200 lines per CLAUDE.md. Longer files use more context and get lower adherence, and deep rules get dropped.
- A common cycle: Claude disobeys a rule, the user adds a louder version, the file grows, and more rules get ignored.
- Test per line: would removing it cause mistakes? If not, cut it.
- CLAUDE.md is advisory. Hard rules belong in hooks.
- Sources:
  - https://dev.to/eliran_kotzero_e1781dc487/why-your-long-claudemd-gets-ignored-and-how-to-fix-it-3hog
  - https://dev.to/aicoding-guide/how-long-should-claudemd-be-the-200-line-target-and-what-it-costs-you-5a2e
  - https://tianpan.co/blog/2026-02-14-writing-effective-agent-instruction-files
  - https://www.mindstudio.ai/blog/context-rot-claude-code-skills-bloated-files
  - https://futureagi.com/blog/claude-md-instruction-governance/

### 5. Over-compression and bulk AI rewrites
- The search returned nothing specific, so this is unverified. The risk is inferred from the "slop" and regression concerns already in the idea. Likely failure modes:
  - Gotchas, "never X" rules and examples get cut as "wordy".
  - Rewritten descriptions lose their trigger phrases.
  - Cross-references and paths drift.
- Mitigation for the spec: tighten file by file with a diff review, keep a before/after word count, preserve every rule and trigger phrase, and spot-test a few triggers.

## Evidence in this repo
- The code already treats descriptions as routing text. Every `claude_plugins/fls-dev/skills/*/SKILL.md` description follows "FreedomLS-specific extension of the ds:X skill ... Use alongside ds:X when ...". That repeats about 15 words per skill, which is exactly the budget cost described in complaint 1.
- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md` records how skills auto-trigger by description. `.../resources/model_tiering.md:45` says to push instructions into skills (load on trigger) rather than inline them in commands. So the repo already holds the principle that load-on-trigger beats inlined text.
- `claude_plugins/sdd/resources/writing_standard.md` exists, which is relevant prior art for tightening.
- A grep of `spec_dd` found no QA or review report about skill triggering, budget or truncation. The repo has no recorded incident of this pain.

## Recommendations for the spec
1. Add an acceptance check that lists loaded skills (with `--plugin-dir` and normally) and confirms each moved skill appears once, with no leftover project duplicate.
2. Grep for bare references to moved skills (`answer`, `unslop`, `writing-for-agents`, `domain-glossary`, `notifications`, `code_comments`) and update them to the namespaced form.
3. Measure total description characters before and after, and shorten the longest descriptions while keeping trigger terms early.
4. Make the rewrite non-lossy by review. Compare rule counts or diffs per file, and do not compress descriptions or examples blindly.
5. Confirm there is no `.claude/` directory inside any plugin.

status: ok
