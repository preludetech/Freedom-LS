When running claude instances on multiple worktrees, the dev experience is not great. There is a lot of waiting due to:

- All worktrees making use of the same development database (specified in dev_db). This means there is a bottleneck around testing
- Sites being associated with different urls, stored in the database. By default `python manage.py create_demo_data` sets up a specific site. When we call `content_save` on the demo content then it is loaded into the database. Content can only be associated with one Site at a time.

# Proposed solution

## settings_dev.py

Update the database settings so the db name is derived from the branch name

## dev_db_init.sh

This would be a new script. It should make a new database and test database for the current branch.

It should execute sql like this:

```
CREATE DATABASE ${BRANCH_NAME};
grant all privileges on database ${BRANCH_NAME} to pguser;

CREATE DATABASE test_${BRANCH_NAME};
grant all privileges on database test_${BRANCH_NAME} to pguser;
```

If the docker composition in dev_db/ is running (even in a separate branch) then `dev_db_init.sh` should just work. And then `pytest` should connect correctly.

We don't want to have to run a separate database composition per branch. We just want to make multiple databases in the same postgres container.

also create a `dev_db_delete.sh` script to completely remove the databases associated with the current branch.

## install_dev.sh

Update this script:

Call `dev_db_init.sh`
Call `python.manage.py create_demo_data`
Call `python.manage.py content_save ./demo_content DemoDev`

## Add FORCE_SITE_NAME to settings_dev

Currently the current site is derived from the url.
If the FORCE_SITE_NAME setting is set then get the site name from there.

In settings_dev.py add `FORCE_SITE_NAME = "DemoDev"`
