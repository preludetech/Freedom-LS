There are a few UI/UX obvious issues on the Educator interface.

# Course details view
/educator/organisations/{org}/courses/{uuid}

- Course content panels: All parts are expanded by default. Make them unexpanded
- too much stuff in first tab. Rather:
    - tab 1:
        - details
        - cohort registrations
        - direct registrations
    - tab 2: content
- cohort registrations panel should allow adding/removing registrations
- direct registrations should allow adding/removing registrations

This should be captured in our skills:
If the educator interface has a panel that lists a thing that the educator is supposed to be able to act on, let them act on the thing. And link to the thing.

# Button text misalignment

Looking at concrete project First Class: There seems to be sopmething wrong with the theme in play. I dont know if this problem is in the concrete project repo, or the theme here.

Button text is misaligned inside buttons.
![alt text](image.png)
![alt text](image-1.png)
![alt text](image-2.png)

# Course content preview
Have a "next" and "previous" button  on modal so educator user can quickly skip through content
Put these buttons in the modal footer instead of close button

For the Quiz top level preview: Give quiz stats and settings.
