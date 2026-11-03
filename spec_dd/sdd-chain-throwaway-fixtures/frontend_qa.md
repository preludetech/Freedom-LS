# Frontend QA: two small display helpers

Throwaway QA plan for proving that `/sdd:implement_plan` chains into `/sdd:do_qa`. The helpers
have no page of their own, so this is a short smoke pass: the branch still serves pages.

## §0 Setup

1. `PORT=$(.claude/ds/scripts/find_available_port.sh)`. Use that number literally from here on.
2. `uv run python manage.py runserver $PORT`, backgrounded.
3. Base URL: `http://127.0.0.1:$PORT`. Check that `#debug-branch-badge`, bottom left, names the
   current branch.

## §1 Health endpoint

1. Visit `/health/liveness/`.
2. Expect a 200 response.

## §2 Signed-in home page

1. Log in with the admin email and password from `## QA Login` in `.claude/sdd/config.md`.
2. Visit `/`.
3. Expect the learner home page to render with the header, and no error page.
