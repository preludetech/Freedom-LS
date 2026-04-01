Make a Git commit.

0. Check you're not on main/master: `git branch --show-current`. If on main/master, warn the user and ask for confirmation before proceeding.
1. Run `uv run pytest` to make sure all tests pass before committing
2. Run `git status` and `git diff` to review what will be committed
3. Stage relevant files individually (don't use `git add .`)
4. Write a short, lowercase commit message describing what changed
5. Use `uv run git commit` to commit the changed. This is needed because of pre-commit hooks
6. Don't commit files containing secrets (.env, credentials, etc.)
