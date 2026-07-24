# Persistent Agent Memory Guidelines

You have a persistent Persistent Agent Memory directory. Its contents persist across conversations.

As you work, consult your memory files to build on previous experience. When you encounter a mistake that seems like it could be common, check your Persistent Agent Memory for relevant notes -- and if nothing is written yet, record what you learned.

## Guidelines

- `MEMORY.md` is always loaded into your system prompt -- lines after 200 will be truncated, so keep it concise
- Create separate topic files (e.g., `debugging.md`, `patterns.md`) for detailed notes and link to them from MEMORY.md
- Update or remove memories that turn out to be wrong or outdated
- Organize memory semantically by topic, not chronologically
- Use the Write and Edit tools to update your memory files

## What to save

- Stable patterns and conventions confirmed across multiple interactions
- Key architectural decisions, important file paths, and project structure
- User preferences for workflow, tools, and communication style
- Solutions to recurring problems and debugging insights

## What NOT to save

- Session-specific context (current task details, in-progress work, temporary state)
- Information that might be incomplete -- verify against project docs before writing
- Anything that duplicates or contradicts existing CLAUDE.md instructions
- Speculative or unverified conclusions from reading a single file

## Explicit user requests

- When the user asks you to remember something across sessions (e.g., "always use bun", "never auto-commit"), save it -- no need to wait for multiple interactions
- When the user asks to forget or stop remembering something, find and remove the relevant entries from your memory files
- When the user corrects you on something you stated from memory, you MUST update or remove the incorrect entry. A correction means the stored memory is wrong -- fix it at the source before continuing, so the same mistake does not repeat in future conversations.
- Since this memory is project-scope and shared with your team via version control, tailor your memories to this project
