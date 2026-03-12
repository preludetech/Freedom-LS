If we create demo data and then run `python manage.py runserver 8001` then visit the home page then the Bloom site is active.

But FORCE_SITE_NAME is equal to DemoDev. So the DemoDev site should be active.

Fix this bug using TDD
1. Write a test to expose the bug
2. Fix the code
3. The test should now pass
