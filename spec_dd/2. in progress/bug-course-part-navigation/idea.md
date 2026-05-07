Fix these bugs using TDD.

# 1. "Previous" button is present when we are looking at the first item of the first course part

If there is a course with multiple course parts and we visit the first item within the first part then there is a "previous" button. There should not be.

http://127.0.0.1:8000/courses/functionality-demo-course-parts/2/
This links to the first topic in the course, there is nothing prior. but there is a "previous" button that does nothing.

# 2 "Previous" button is present but broken when looking at the first item of subsequent course parts

Eg:
http://127.0.0.1:8000/courses/functionality-demo-course-parts/5/

Here we are looking at the "Key Ideas" topic from the demo_content.

The previous button is present, but it doesn't do anything when clicked. It should redirect to the last thing from the previous course part.
