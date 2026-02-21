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

## Do the following for each step in the plan

1. Follow the step exactly (plan has bite-sized steps)
2. Run verifications as specified
3. Use the request-code-review skill to review what was done
4. If there is no feedback, or all changes are addressed:
    - do a final test
    - make a commit
5. Mode onto the next step until there are all complete

## Double check 

1. Read through all the steps and make sure you didn't miss anything
2. If you did miss a requirement then implement it, then check again

## After all steps are complete

1. Use the request-code-review skill to review everything that was done.
2. Run all the tests 

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
