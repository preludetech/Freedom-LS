The page that lists all the current courses needs some improvements

1. Simplify the widget: Each course will have the "icon" area on the left and then on the right it will say the course title
2. If a course is in progress, registered for or complete then display that, but dont show "next up"
3. If displaying the progress bar on a course adds an N+1 query then DO NOT display it. Only display it if it is cheap
4. Clicking on an unstarted course works the same as usual
5. Clicking on a course where the user is registered

[icon][details]

Don't add any new functionality

Make sure that the course status is correctly calculated everywhere. We need to show:
- Registered (the user is registered, but progress is 0)
- In progress
- not registered
- complete
