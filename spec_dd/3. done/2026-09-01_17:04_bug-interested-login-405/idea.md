
Scenario:
- An anon user navigates to a "coming soon" course, eg "http://127.0.0.1:8000/courses/content-widgets-demo-reference/detail/"
- fill in the sign-in form with good credentials, click "sign in"
- Redirected to http://127.0.0.1:8000/interest/courses/content-widgets-demo-reference/express-interest/ with HTTP error 405

Requirement:

1. Fix the bug:

    1. Write a test that fails because of this bug
    2. Fix the bug so the test passes

2. Harden:
    1. Explore all other auth situations to do with expressing interest in courses, applying for courses and signing up for courses.
    Make sure they are properly tested and bug free
    2. QA should check all authentication flows to do with course signup/apply/express-interest
