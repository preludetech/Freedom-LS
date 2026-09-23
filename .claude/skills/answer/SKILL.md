---
name: answer
description: Answer the user's question and do nothing else. No edits, no tests, no side effects.
disable-model-invocation: true
argument-hint: <question>
---

# Answer

The user has a question. Answer it. That is the whole job.

Question: $ARGUMENTS

## Rules

- **Do not change anything.** No Edit, Write, NotebookEdit, git commits, file moves, migrations,
  installs, or any Bash command that modifies files, the database, or git state.
- **Do not run tests**, linters, type checkers, builds, or the dev server.
- **Do not spawn agents or workflows** that would do any of the above.
- Reading is fine. Use Read, Grep, Glob, and read-only Bash (`git log`, `git diff`, `ls`, `cat`)
  when you need facts from the codebase to answer accurately. Look only as far as the question needs.
- Do not offer to make changes, suggest next steps, or ask follow-ups unless the question can't be
  answered without clarification.

## Output

- Lead with the direct answer. First sentence should answer the question.
- Be concise. Add only the detail needed to support the answer.
- Reference code as `path:line` where it helps.
- Use a short code snippet or list only if it's clearer than prose.
- No preamble, no recap of what you looked at, no closing summary.
