# Context

We recently updated our Django and allauth versions spec_dd/3. done/2026-03-12_07:10_upgrade-to-django-6

Before this was implemented, Allauth generated emails just fine. Now it doesn't

# Bug

- run `python.manage.py runserver $PORT`
- visit the frontend and try to register with a new user
- an email gets sent (these are stored in the gitignore/emails folder)
- the link to confirm email is broken

We need to be certain that all the allauth flows (registration, reset password, add email) work fine
