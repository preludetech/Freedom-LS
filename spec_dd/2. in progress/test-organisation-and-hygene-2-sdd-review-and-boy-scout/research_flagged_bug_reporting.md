# Research: where a flagged-but-not-fixed finding gets reported, and who decides it's not a bug

Scope: the two things `idea.md` leaves open — where the boy-scout's "obvious, genuinely broken
code" flags land so a human can see them, and who is allowed to conclude a flagged item is not a
bug (the case where a code comment is left "so it is not flagged again"). Does not repeat
`research_boy_scout_rule.md`'s Boy Scout Rule / opportunistic-refactoring material.

## 1. How SDD already surfaces agent judgement calls to the human

Five existing mechanisms, in increasing order of how firmly they force a human decision.

### 1a. A `.sdd-work/` file — transient, not a reporting channel on its own

`claude_plugins/fls-dev/commands/do_qa.md` uses `.sdd-work/qa_scratch.jsonl` and
`.sdd-work/bugfix_<slug>.md` as **working scratch**, explicitly deleted once consumed (Step 16:
"Never glob-delete and never wipe the entire `.sdd-work/` directory... stale scratch files are
harmless and already gitignored" — but they are still deleted every run). `.sdd-work/` is where
`make_pr_quickly.md` drafts `pr_body.md` before deleting it once the PR is filed. Nothing that
needs to survive past the current command invocation, let alone reach a human at PR review across
multiple `implement_plan` batches and sessions, should live only in `.sdd-work/` — it is
explicitly a scratch area, not a record.

### 1b. A spec-dir sibling file — durable, travels with the spec

`claude_plugins/sdd/commands/protected/pre_step_rebase.md` Step 5 is the closest existing
precedent to "an agent found something a human needs to judge, mid-flow." When the upstream-change
scan finds the base has moved in a way that might undercut the spec's own decisions, it:

1. Spawns one `sdd:sdd-worker` to write `.sdd-work/rebase_upstream_review.md` with its own
   reasoning (`direction: changed`, "What main gained", "Why it matters for this spec", "What to
   change").
2. **Moves** that file to `<spec-dir>/upstream_change_review.md` — a durable sibling of `1. spec.md`,
   `2. plan.md`, and the `research_*.md` files, so it survives the run and travels with the spec
   directory into `spec_dd/3. done/`.
3. Inserts a `user|` item at the very front of the unchecked `todo.md` items (`add_first:`) naming
   the file: `"Decide what to change after reading upstream_change_review.md, then edit the idea,
   spec or plan it names"`.
4. Returns `status: paused` — the caller (`/sdd:next`) will not dispatch the next `(cmd)` item until
   that `user|` item is ticked, and its own Pause condition (Step 0) re-checks for it on every future
   call so the workflow cannot silently slide past it.

This is a two-part pattern: a **durable sibling file carrying the agent's own reasoning**, plus a
**`todo.md` `user|` item that blocks the automated flow** until a human acts. `qa_report.md`
(`do_qa.md` Step 12) is the same shape for QA: a spec-dir sibling file, not `.sdd-work/`, that
survives to PR review.

### 1c. `do_qa`'s green-lane/red-lane split — a closed decision boundary, not agent discretion

`do_qa.md` Step 13's triage gate is the sharpest precedent for "when may the agent decide this
itself, and when must a human decide." Green lane (agent auto-fixes) is permitted **only when all
five conditions hold** — clear functional defect, provable by a pytest test, no product/UX
judgement call, no migration, not security-adjacent. Any one condition failing routes to red lane —
"record `UNRESOLVED`... The recorded reason must name the specific decision or risk that needs a
human." Two matching conventions:

- **"An observation with no action attached... goes in `qa_report.md` under General notes. It does
  not go in `todo.md`."** Not every finding needs a blocking `user|` item — only one that turns on an
  actual decision does (Step 15's closed `add:` list, category 4: "A product or UX decision a bug
  turns on").
- The report's `## Bug status` section is rewritten with a final verdict (`FIXED` / `UNRESOLVED`
  with reason) — the report is the single place a reviewer looks, not scattered across inline
  comments.

### 1d. The PR body — a mechanical transcription, and where deferred items are already meant to land

`make_pr_quickly.md` builds the PR body from `todo.md`'s ticked/unticked state ("SDD status...is
what earns the PR its review: it tells the reviewer at a glance that, say, the security review and
the QA pass have not run yet") — it makes **no judgement call**, only transcribes. This spec's own
`idea.md` has already settled that boy-scout deferrals-over-budget get reported this way: "What it
tidied and what it deferred gets reported in the spec's PR." That's about the budget-exceeded case
specifically; the open question here is whether the *flagged-broken-code* case (distinct from the
test-organisation deferral case) uses the same channel.

### 1e. `address_pr_review.md` — the existing "propose, then get confirmation" shape for exactly
this judgement call

Step 4 of `address_pr_review.md` is the most directly analogous precedent for *deciding something a
human raised isn't worth fixing*: "If you think it should NOT be addressed: explain why and ask the
user for confirmation before skipping." This is a human-raised finding rather than an
agent-raised one, but the shape — agent proposes a disposition with reasoning, human confirms before
the disposition becomes final — is exactly the "boy-scout proposes, human confirms" option below.

### 1f. `qa-bugfixer`'s "note it but do not fix it" convention

Step 5 of `claude_plugins/fls-dev/agents/qa-bugfixer.md`: "either your fix broke something... or the
test was already broken before you started (**note it but do not fix it — that is a separate
bug**)." The agent has no separate report-location convention for this beyond its own structured
report file — it goes in the same `.sdd-work/bugfix_<slug>.md` report the orchestrator already
reads, under whichever section fits ("Suite result"). This is a smaller-scale version of the same
problem this research is about, and it resolves it by putting the observation in the **one file the
orchestrator already reads**, not by inventing a second channel.

## 2. What `code-comments` says about a "not a bug because…" comment

`.claude/skills/code-comments/SKILL.md`'s single rule: **"a comment must explain *why*, not
*what*."** An "intentional, not a bug" comment is squarely in the skill's "good comment" category —
it is exactly the shape of "Edge-case rationale" and "Why-not-the-obvious-thing" the skill lists as
what a comment should capture (e.g. "why we redirect instead of dereferencing `None` and 500ing").
So the *comment itself*, if it carries the actual reasoning, is not a bad comment by this skill's
standard.

Two things the skill would flag if a boy-scout wrote this kind of comment carelessly:

- **"Don't narrate implementation history."** The comment must state *why the code is correct*, not
  *that a boy-scout agent looked at it on such-and-such date and decided it was fine*. `# Flagged by
  boy-scout, judged not a bug` is exactly the "describes the change, not the code" anti-pattern the
  skill bans — it would rot the moment anyone wants to know *why*, and it's gone stale the instant
  the surrounding code changes, because it records a process event, not a property of the code.
- **"If you can't articulate a *why*, the line probably doesn't need a comment."** A boy-scout
  agent that can't produce the substantive reasoning shouldn't write a suppression comment at all —
  the same bar the skill sets for humans applies.

The skill does not discuss suppression-comment *governance* (who is allowed to write one, whether it
needs review) at all — it is about comment *content*, not comment *authority*. That gap is exactly
what this research's "who decides" half needs to fill, and the skill offers no precedent either way.

## 3. External precedent: suppression comments in linters, SAST and secret scanners

### 3a. The universal pattern: a suppression needs a *reason*, and the reason is checked

- **`# noqa: <code>` with a trailing reason** is the recommended shape over a bare `# noqa` —
  specific error codes so the suppression doesn't blanket-silence unrelated issues, plus "a short
  trailing comment [that] can explain the rationale," with suppressions treated as "a last resort"
  and periodically audited by count. [What does 'noqa' mean in Python comments? — Codemia](https://codemia.io/knowledge-hub/path/what_does__noqa_mean_in_python_comments)
- **`nosemgrep`** requires the suppression to sit on the line directly above (or same line as) the
  match — "the full rule id rather than a bare `# nosemgrep`, and a rationale at the site" — and a
  real-world audit found gosec suppressions added across 12 files *without justification* hid an
  actual path-traversal vulnerability (`os.ReadFile`/`os.WriteFile` on unvalidated CLI-derived
  paths), later fixed once someone actually checked the suppressed finding.
  [fullsend-ai/fullsend#2062](https://github.com/fullsend-ai/fullsend/issues/2062)
- **SonarQube** gates "Won't Fix" and "False Positive" resolutions behind the **"Administer
  Issues" permission** specifically — not every contributor can mark their own finding resolved,
  and issues marked that way persist across PR analysis and re-scans, meaning the decision is meant
  to be made once, by someone with that authority, not re-litigated by whoever next reads the code.
  [Mark "Won't fix" and "False positive" — Sonar Community](https://community.sonarsource.com/t/mark-wont-fix-and-false-positive/24118),
  [Is there a maker/checker feature for won't-fix — Sonar Community](https://community.sonarsource.com/t/is-there-any-feature-in-sonarqube-to-have-a-maker-and-checker-for-wont-fix-or-false-positive/95113)
- **`detect-secrets`** (this repo's own `.secrets.baseline`, visible in the current git status as
  `UU .secrets.baseline`) ships an explicit **interactive audit** step: `detect-secrets audit` walks
  every entry in the baseline and asks a human to label it a true or false positive one at a time;
  the workflow's documented discipline is that "baseline changes should be treated as code review
  requiring PR approval." [detect-secrets — Yelp](https://github.com/Yelp/detect-secrets),
  [How to Implement Secret Detection — OneUptime](https://oneuptime.com/blog/post/2026-01-30-secret-detection/view)

The common thread across all four: a suppression is allowed, but it is not a private act. Either a
*different* actor from the one raising the finding has to hold a permission to close it (SonarQube),
or the suppression is subject to periodic audit / re-justification (noqa, `.secrets.baseline`), or a
downstream reviewer is expected to independently re-check the suppressed finding rather than trust
the comment (`nosemgrep`'s gosec case). None of the four treat "the tool that raised the finding also
gets to silently close it, unchallenged" as sound practice.

### 3b. AI agents specifically: self-suppression is a documented failure mode, in both directions

- **Over-flagging then self-contradicting**: a review agent that reasons through a concern,
  concludes the code is fine, but still emits it as a finding — "3 of 6 distinct findings were
  self-dismissed LOWs — a 50% noise rate," diluting genuinely actionable findings. The fix proposed
  there is the opposite direction from this spec's problem: suppress *before* reporting, when the
  agent's own analysis is confident nothing is wrong.
  [fullsend-ai/agents#1106](https://github.com/fullsend-ai/agents/issues/1106)
- **Blind trust in existing suppressions**: a review agent that treats an existing `nosemgrep`/
  `nolint` annotation as settled fact rather than re-checking whether the underlying finding is
  real — the gosec/path-traversal case above is the concrete instance where that trust hid a real
  vulnerability. [fullsend-ai/fullsend#2062](https://github.com/fullsend-ai/fullsend/issues/2062)
- **Justified suppressions still need someone to see them**: a suppression can carry a perfectly
  good inline reason and still be invisible to whoever needs to notice it exists at all — a tooling
  report elsewhere flagged 126 "stale" suppressions that actually *did* carry justification, because
  nothing surfaced the justification to a reviewing human in a form they'd check.
  [bjcoombs/ai-native-toolkit#335](https://github.com/bjcoombs/ai-native-toolkit/issues/335)

These are the same risk from two directions: (1) an agent that closes its own finding with no
independent check can be wrong, and wrong silently, because the mechanism that would normally catch
that (a second reviewer, a permission gate, a periodic audit) never runs; (2) even a properly
justified suppression does nothing for review quality unless something *forces* it in front of a
human at the point where they could disagree.

### 3c. Comment rot: the "not a bug because…" comment is exactly the kind that goes stale silently

- "A stale comment is not a documentation problem — it is a dangerous lie... when someone later sees
  a comment and code that disagree, they have no way to know which is the truth, and may pick the
  comment and revert the code change." This is the general comment-rot risk, and it applies with
  extra force to a suppression comment specifically: its entire job is to stop a reviewer or a future
  boy-scout pass from looking again, so if the code around it changes in a way that invalidates the
  reasoning, **nothing re-triggers a re-check** — the comment's own purpose is to prevent exactly the
  scrutiny that would catch its own staleness.
  [The Shocking Truth About Code Comments — Sohail Saifi, Medium](https://medium.com/@sohail_saifi/the-shocking-truth-about-code-comments-why-theyre-making-your-codebase-worse-52a62ded6f67)

## 4. Options

### (a) Report location

| Option | What it gives | What it misses |
|---|---|---|
| **PR body section** (`make_pr_quickly.md`'s mechanical shape, or a new section) | Guaranteed human eyeball at the one point every SDD spec already funnels through; matches `idea.md`'s already-settled convention for budget-exceeded deferrals ("reported in the spec's PR") | Only exists once a PR is opened — a boy-scout flag from an early batch has nowhere to live in the meantime unless it's also written somewhere durable first; PR body is regenerated by `make_pr_quickly.md` from `todo.md` + commit log, so anything not captured in one of those two inputs by the time that command runs is lost |
| **`.sdd-work/` file** | Cheap, consistent with `do_qa`'s scratch-then-consume pattern | Explicitly transient — every SDD command that uses it deletes it once consumed (`do_qa.md` Step 16, `make_pr_quickly.md` Step 5). Wrong shape for something that must survive to PR review across multiple `implement_plan` batches/sessions |
| **Spec-dir sibling file** (e.g. `boy_scout_findings.md`, alongside `qa_report.md`, `upstream_change_review.md`, `research_*.md`) | Durable — survives the run, travels with the spec into `spec_dd/3. done/`; can be appended to across batches the way `qa_report.md` is rewritten across `do_qa`'s Step 12/13; exactly the shape `pre_step_rebase.md` already uses for "an agent found something a human should judge" | One more file convention to teach; needs an explicit step (in `make_pr_quickly.md` or the boy-scout's own return contract) to guarantee it actually reaches the PR body, or it risks becoming a file nobody opens |
| **`todo.md` `user|` item** | The heaviest guarantee: `/sdd:next`'s Pause condition (via `pre_step_rebase.md`) blocks the automated flow until it's ticked, and ticking requires the user to affirmatively say "yes" per `next.md` Step 3's `(user)` branch | Disproportionate for most flags — `pre_step_rebase.md` reserves this for a base-change that can undercut the spec's own decisions, a much higher-stakes event than "boy-scout noticed something odd while tidying a test file." Blocking `implement_plan`'s batch loop on every flag would fight the spec's own "no big-bang, small budget" framing |
| **Inline comment only** | Zero extra machinery — the comment *is* the artifact `idea.md` already settled on for the "not a bug" case | Not a reporting channel to a human at all — it's addressed to the next reader of that code (human or agent), not to whoever reviews the PR. Nothing forces a reviewer to see it before merge, which is the exact failure mode `nosemgrep`/gosec and the comment-rot research above describe: a suppression that sails through unexamined |

### (b) Decider

| Option | What it gives | What it risks |
|---|---|---|
| **Boy-scout decides itself, comment stands unchallenged** | Fastest, no added flow; matches nothing being blocked mid-`implement_plan` | This is the precise anti-pattern flagged by `fullsend-ai/fullsend#2062` (agent trusting/authoring a suppression with no independent check hid a real path-traversal bug) and by SonarQube's design (closing a finding needs a *permission* the raiser doesn't automatically hold). Combined with §3c's comment-rot point — the comment's job is to prevent re-examination, so a wrong call here is not self-correcting. Given the effort's own framing that a missed real bug is a worse outcome than a few extra comments for a human to skim, self-decide is the weakest option on the actual risk it's meant to guard against |
| **Human decides at PR review** | Matches where SDD already concentrates review effort (`setup_todo_list.md`'s "(user) Review the QA report", "(user) Spot-check the changes", the whole PR-review section); reuses `address_pr_review.md`'s existing "explain why, ask for confirmation before skipping" shape, just applied to an agent-raised finding instead of a human-raised one | Only works if the finding is actually *visible* at PR review — i.e. this option is not independent of the location choice above. A flag that only exists as an inline comment, with no PR-body/spec-dir surface, gives the human nothing to react to unless they read every touched file's diff line by line |
| **Boy-scout proposes, human confirms** (two-step) | Directly precedented twice in this codebase already: `pre_step_rebase.md`'s upstream-change review (agent writes reasoning to a durable sibling file, human decision required before flow resumes) and `do_qa.md`'s red-lane pattern (agent names the specific decision a human must make, rather than making it). Keeps the disposition provisional until a human has actually looked, closing the self-suppression gap `fullsend-ai/fullsend#2062` describes, without requiring the heaviest `todo.md`-pause machinery for every flag | Costs one more round-trip than self-deciding; needs the report location to actually carry the boy-scout's reasoning (not just "flagged, see comment") so the human has something to agree or disagree with, which most naturally means the spec-dir sibling file or PR body, not the inline comment alone |

## 5. Recommendation

Use the **spec-dir sibling file + PR body** for location, and **boy-scout proposes, human
confirms** for the decider — combining rows already precedented separately in this codebase, at a
size proportionate to the boy-scout's own small budget (§5 of `research_boy_scout_rule.md`), not the
heavier `todo.md`-pause machinery `pre_step_rebase.md` reserves for base-changing events:

1. Every time the boy-scout flags something and judges it not a bug, it writes both the flag *and*
   its own reasoning to a durable, appendable spec-dir sibling file (parallel to `qa_report.md` and
   `upstream_change_review.md`) — not `.sdd-work/`, which is deleted before a PR is ever opened. The
   inline comment stays exactly as `idea.md` already settled — it is the code-level artifact that
   stops a future boy-scout pass re-flagging the same spot — but it is not asked to also be the
   human-facing report. Per the `code-comments` skill, the comment must carry the actual "why," never
   a note that a boy-scout made the call or when.
2. `make_pr_quickly.md`-shaped tooling (or the boy-scout's own return contract feeding into it, the
   same way `idea.md` already settled deferred-budget items get "reported in the spec's PR") surfaces
   that file's contents as a PR-body section, so the disposition is provisional, not final, until a
   human has actually seen it — closing the exact gap `fullsend-ai/fullsend#2062`'s gosec case and
   the comment-rot research in §3c describe: a suppression that never crosses a human's eyes.
3. Treat this the way `address_pr_review.md` Step 4 already treats a human-raised issue the agent
   thinks shouldn't be fixed: state the finding, state the "not a bug because…" reasoning, and let the
   human confirm or override — reusing a pattern this project already runs, rather than inventing a
   new one.
4. Reserve the heavier `todo.md` `user|`-pause pattern (§1b) for a future escalation only if this
   effort later decides some class of flagged finding is too high-stakes to wait for ordinary PR
   review — mirroring how `pre_step_rebase.md` reserves it for base-changes, not routine review
   comments.

This keeps the low-stakes, high-volume case (a plausibly-fine flag) cheap and non-blocking, while
making sure the mechanism this spec explicitly worries about — an agent quietly deciding its own
finding isn't a bug — always has a human checkpoint before the "don't flag me again" comment becomes
the last word, which is the one property every external precedent in §3 converges on and the one
property a purely self-decided, comment-only suppression cannot provide.

---

status: ok
