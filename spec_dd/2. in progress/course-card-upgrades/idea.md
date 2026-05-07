When a learner logs in they land on their home page. This is a dashboard from which they can navigate to courses. We need to update it in many ways.

# 1. Icons as thumbnails - Data structure

Courses can have thumbnail Icons.

When we make use of the management script freedom_ls/content_engine/management/commands/content_save.py then, if an icon is defined, save it in the database.

Update one of the demo_content courses to demonstrate this functionality.

If a course does not have a thumbnail icon, it needs a default.

# 2. Dashboard Course Card

For in progress courses display only:
- the icon in a theme color on a background
- "in progress" if it is in progress
- a progress bar and percentage

If the course is in progress:
- Clicking on the card should take the learner to the next portion of the course

If the course has not started yet:
- Clicking on the card should bring up an overlay/modal with basic details and a table of contents.
- If the learner can start the course, have a "start" button on the modal

If the course is complete:
- Clicking on the card should go to a "Course is complete" page

# Resources

There is a file called card/in-progress-card.html in this spec directory. Base you r work on that.
This file makes use of the first_class theme colors, use the theme token colors instead
This file also adds too much information, eg deadlines. Only include what was requested. If you think something more should be there then ask.
