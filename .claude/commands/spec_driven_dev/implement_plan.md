---
name: implement-plan
allowed-tools: Read, Glob, Write, Skill
---

# Executing Plans

## Step 1: Read and Review the Plan

1. Read the plan file
2. Before implementing anything, check for:
   - Missing or ambiguous steps
   - Steps that depend on things not covered earlier in the plan
   - Unclear success criteria
   - Missing dependencies or prerequisites
3. If you find issues: raise them with the user before starting
4. If the plan is clear: proceed to Step 2

## Step 2: Batch and Execute

Split the plan's tasks into batches of related steps. Each batch should be a coherent unit of work (e.g. "add model + migration", "add views + templates + urls").

For each batch, delegate to a **sub-agent** that does the following:

1. Implement each step exactly as written in the plan
2. Run any verifications the plan specifies after each step
3. After all steps in the batch are done, run `uv run pytest` — all tests must pass
4. Use the `request-code-review` skill to review the batch's changes
5. Fix any issues raised by the review
6. Re-run tests after fixes

**All tests must pass before moving to the next batch.**

### NO NOT run the final QA verification while implementing the plan
If there is a frontend_qa_plan.md file: DO NOT RUN IT
If the plan mentions running the frontend_qa_plan.md. IGNORE THAT STEP. DO NOT RUN IT


## Step 3: Final Verification

After all batches are complete:

1. Use the `request-code-review` skill to review all changes end-to-end
2. Run `uv run pytest` in a sub-agent to confirm everything passes
3. Check each success criterion from the plan — is it met?
4. If any criterion is unmet: fix it with a sub-agent, then repeat from step 1
5. Once everything passes and review feedback is addressed: commit the changes


## When to Stop and Ask

**Stop immediately when:**
- A step is unclear or ambiguous
- A test fails and the cause isn't obvious
- You hit a missing dependency or prerequisite
- The plan has a gap that blocks progress

**Ask for clarification rather than guessing. Don't force through blockers.**

## Branch Safety

Never start implementation on main/master branch without explicit user consent.
