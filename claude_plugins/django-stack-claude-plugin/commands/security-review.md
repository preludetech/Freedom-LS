Perform a security review of the current changes:
1. Run `uv run bandit -r . -x ./tests` and analyze results
2. Run `uvx pip-audit` for dependency vulnerabilities
3. Run `detect-secrets scan` for hardcoded secrets
4. Review all new/modified views for auth decorators and ownership checks
5. Check all ORM queries for raw SQL or injection risks
6. Verify CSRF protection on all state-changing views
7. Run `uv run python manage.py check --deploy`
Focus areas: $ARGUMENTS
