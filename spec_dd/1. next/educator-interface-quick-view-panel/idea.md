# Feature: Right hand overlay on course progress click

eg: http://127.0.0.1:8000/educator/cohorts/06bcd30b-8072-4f1a-bc62-a2355392f8d8
When clicking on a block representing topic progress or form progress in the course progress table then open up a right-hand side panel
- The side panel mechanism will be used for different hings in different parts of the application so it should be reusable. Call it "quick view" or something like that.
- it should not hinder use of the rest of the page. Eg a user might click on a topic progress instance then click on a form after that

When the quick-view is opened we'll need to show info about what was clicked:
- For Topics display at least when it was started and finished
- for forms show info about each attempt.
