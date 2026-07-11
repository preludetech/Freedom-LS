I recently tried to demo the project and email verification did not work.

# scenario

- Visited site as an unauthenticated user
- navigted to a "free" course
- chose to enroll for free
- was asked to login/create an account
- I tried registering with an email that was already on the system
- got a password reset email
- followed the email link and it asked me to fill in a form to reset my password
- filled it in
- kept trying to verify email, but it just didn't work

# instructions

Fix this using TDD

- use playwright to find the bugs. Do a thorough review of all pathways for signing in/up. Consider all situations, include:
    - accessing the sign up page directly (not through a course cta)
        - sign up with new user
        - trying to sign up, but use if already on they system
    - accessing sign-up page through a course CTA (eg course reg attempt while not signed in)
        - sign up with new user
        - sign up but user email already in the system
- write tests to expose the bug (RED)
- get the tests to pass (GREEN)
- Dont forget to refactor
