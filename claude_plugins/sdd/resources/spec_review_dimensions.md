# Spec review dimensions

`/sdd:spec_from_idea` and `/sdd:spec_review` spawn one `sdd:sdd-worker` per row, each writing
`.sdd-work/spec_review_<id>.md`. A worker reads the spec, the idea and every sibling `*.md` in the
spec directory, checks its one dimension, and writes one finding per line:

    <spec section>: <what is wrong>: clear fix: <the exact replacement> | judgement call: <the options, recommended first>

followed by the `status:` footer. No findings is `status: ok` with the line `no findings`.

A **clear fix** is mechanical or has exactly one reading, is backed by a quotable line in the idea,
a sibling file, a vocabulary source or a plugin README, and does not add, remove or reorder a
requirement. Everything else is a judgement call.

| id | checks | evidence it may cite | clear fixes |
| --- | --- | --- | --- |
| `completeness` | contradictions and gaps against the idea, its sibling files and the user's recorded answers | lines of those files | a contradiction where the idea's settled decision names the winner; a missing section the shape requires; a broken cross-reference |
| `feasibility` | project norms in `${CLAUDE_PLUGIN_ROOT}/resources/` and the skills the spec touches; whether each requirement can be built as written | those files and the code | none; all judgement |
| `vocabulary` | every noun and identifier against the `## Vocabulary Sources` in `.claude/sdd/config.md` (`config.local.md` wins) | the source that holds the term | a term replaced by the source's term |
| `generic_plugin` | no project name, path, app or value in a plugin whose README says it is generic | the plugin README and the project's config file | moving a project value into the project's config section |
| `cut_list` | the list below | the spec line | none; cuts are always judgement |

The `feasibility` worker's brief passes the `SKILL.md` paths of the skills the spec touches, since a
worker reads files and cannot load a skill by name.

## Never write these in a spec

- **The idea's argument, re-run.** The approach was settled upstream. State the outcome and cite the
  idea by filename. Do not reproduce the reasoning that got there.
- **A decisions table that repeats the body.** A decision explained where it is implemented does not
  also get a table row. A decision in the table is not re-explained in the body.
- **Rejected alternatives at paragraph length.** One sentence naming the alternative and why not, or
  nothing.
- **Reasoning about the spec's own drafting.** No "an earlier draft", no "two notes survive from
  that draft", no "the implementer should not tidy this away".
- **Success criteria that restate sections.** If you cannot say how someone would check it, it is
  not a criterion.
- **Implementation sequencing and work lists.** Ordering constraints belong in the spec only where
  getting them wrong breaks something; everything else is the plan's job.
