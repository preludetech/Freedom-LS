---
description: Check that the spec makes sense
allowed-tools: Read, Glob, Grep, Edit, Skill
---

You are helping to refine a feature spec. The spec might have problems. You are doing a final check to make sure it can be implemented.

# Output

- Edit the spec document to overcome all the problems, then tighten it
- Print a short summary of what you did, including the spec's line and word counts before and after

# Step 1

Read over the spec and look for contradictions. Handle one contradiction at a time.

For each contradiction:
- Clearly describe the contradiction, ask for input
- Edit the spec file to fix the contradiction

Keep repeating this process until there are no more contradictions.

# Step 2

Read over any implementation details mentioned in the spec and make sure that they adhere to project norms, and that they are technically feasible.

Read through all the documentation in ${CLAUDE_PLUGIN_ROOT}/resources/ and make sure the spec does not go against any project norms defined there.

Check the spec's names against `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`, running the checks it describes on the **Terminology** section, and adding that section where the spec coins or narrows a term and says so nowhere.

Read any mentioned source code files and any related code and look for inconsistencies and problems.

For each problem you find:
- Clearly describe the problem, ask for input if the solution if needed
- Edit the spec file to fix the problem

# Step 3

Return to Step 1 and make sure no new problems were introduced. Repeat the whole process until the spec has no unaddressed problems

# Step 4: Tighten the spec

Correctness is settled by this point, so no effort goes into tightening text that was about to be
rewritten. Now make the spec say what it says once.

A spec reaches this command by more than one route. `/spec_from_idea` writes the first draft, but
it is also hand-edited and amended by `/threat-model`, so this is the last gate before planning
whichever way it arrived.

Apply `${CLAUDE_PLUGIN_ROOT}/resources/writing_standard.md` and the spec cut-list in
`${CLAUDE_PLUGIN_ROOT}/commands/spec_from_idea.md` under "Never write these in a spec".

**Cutting must not lose a requirement.** Run the completeness pass first: read the idea file and
every sibling `*.md` beside the spec, and confirm each decision and constraint has exactly one home
in the spec. Only then cut. If you cannot say where something went, you lost it. Put it back.

The usual finds, in rough order of how much they cost the reader:

- The idea's argument reproduced inside the spec. Cite the idea by filename instead, keeping any
  sentence that states a requirement rather than a justification.
- A decision stated in a table, in the section that implements it, and again in the success
  criteria. Keep one.
- Drafting history: "an earlier draft", "two notes survive", "the implementer should not tidy this
  away".
- Rejected alternatives at paragraph length. A sentence each is enough.
- Paragraphs proving a point nobody would dispute.

Finish with the two passes from the writing standard: `unslop`, then a re-read.

# Step 5: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/spec_review` to sanity-check the spec"`
- For each unresolved question you raised that the user still needs to decide, pass `add:"Spec|user|Decide how to handle <short description of the question>"`. If everything was resolved during the review, omit `add:`.

# Out of scope

- Do not add technical implementation details to the spec. Just check the ones already included.
- If there are any technical concerns then raise them in a high level way, don't write unnecessary code
- Step 4 removes text. It never adds design, and it never resolves an open question by deleting it.
