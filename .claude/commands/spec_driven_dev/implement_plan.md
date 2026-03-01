---
name: implement-plan
allowed-tools: Read, Glob, Write
---

# Executing Plans

## Overview

Load plan, review critically, execute tasks in batches, report for review between batches.

**Core principle:** Batch execution with checkpoints for architect review.

## The Process

1. Read plan file
2. Review critically - identify any questions or concerns about the plan
3. If concerns: Raise them with your human partner before starting
4. If no concerns: Begin implementing the plan

### Implementing the plan

1. Separate the tasks into batches
2. Each batch should be implemented by a sub agent

### The sub agent should do the following for its batch of tasks

1. Follow the step exactly (plan has bite-sized steps)
2. Run verifications as specified
3. Mode onto the next step until there are all complete
4. Use the request-code-review skill to review what was done
5. Implement any needed changes
6. Run the tests and make sure everything works

**IMPORTANT** ALL tests need to pass. If there are broken tests fix them!

### After all steps are complete

1. Use the request-code-review skill to review everything that was done.
2. Run all the tests in a sub agent, make sure all functionality works
3. Make sure all the steps were completed and review the success criteria for the plan. If the success criteria are not being met then use subagents to develop any missing or broken functionality. Then go back to `1. Use the request-code-review skill to review everything that was done.`
4. If there is no feedback, or all changes are addressed, commit the changes


## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker mid-step (missing dependency, test fails, instruction unclear)
- Plan has critical gaps
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

## Remember
- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Between steps: just report and wait
- Stop when blocked, don't guess
- Never start implementation on main/master branch without explicit user consent
