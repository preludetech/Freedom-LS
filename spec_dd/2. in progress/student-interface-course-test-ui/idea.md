We need the student interface for showing exams to look good and on spec.

Follow the designs here: /home/sheena/workspace/lms/design/computed/exam . These designs match the first-class theme. Make sure everything works for the default theme and then make customisations. Make sure everything is easy to theme, style and change

The designs we are pointing to were made by a third party tool that is not aware of our code and structures. Do not implement new features without checking first. The goal is to copy the design, not to implement all the things.

# Pages

We need to implement a few different pages, on various screen sizes: Desktop, tablet, Mobile.

## Test start screen

- This shows basic information about the test, and past attempts. Lets the user "start" the test.
- certain test attributes (number of pages etc) can be displayed
- we will add extra functionality like how many retries etc in a future specification


## Test questions page
- This displays a one FormPage's questions.
- Dont display the whole "course player" interface and side panel. Once the learner is inside the test, that is its own interface
- Show progress bar at top
- All question types need to be demonstrated in our demo content
- Allow user to go back to previous pages

On the final page:
- when the user clicks on the next button then open a dialog
- ask the user if they want to review their answers or submit


## Results page

- Once the user submits a test, redirect here
- If the test has automated marking then show the marks
- Else say that the marking is in progress
- allow them to navigate back to the course player

# Navigation

We need to be able to allow a user to launch a form, go back and forth between pages, fill in answers, retry etc

If a learner tries to navigate out of a form then use a dialog to warn them that this will submit their answers
