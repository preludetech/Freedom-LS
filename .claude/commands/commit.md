Make a Git commit.

1. Run `uv run pytest` to make sure all tests pass before committing
2. Run `git status` and `git diff` to review what will be committed
3. Stage relevant files individually (don't use `git add .`)
4. Write a short, lowercase commit message describing what changed
5. Don't commit files containing secrets (.env, credentials, etc.)