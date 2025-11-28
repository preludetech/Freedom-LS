# The Learning System with no Name 

The basic idea of this system is to build out all the functionality that would be needed in an LMS, it should work out of the box and have minimal opinions about how things should be done. 

Folks who want to use this as a base for their own projects should be able to make use of this repo as a base and then add their own Django app to make things work the way they want it to. 

This means that it should be built with extensibility in mind! 

## Installation for development

We are using uv to handle dependencies. Use `uv sync` to install the lot into a new virtual environment.

There are also some node dependencies: `npm i`

You'll also need to run tailwind to generate the css for the project:

```
npm run tailwind_build  # this simply builds the css files
```

## More on Tailwind

If you are writing some frontend-related code then it is likely that you will change some css on some pages. In this case it will be necessary to re-build the tailwind css. 

Instead of having to remember to do this all the time, you can use `npm run tailwind_watch`.




## Database setup 

Currently we are using Sqlite. Get the database set up like so:

```
python manage.py migrate
```

Once that is done, you can create some data to play with using:

```
python manage.py create_demo_data
```

Feel free to add more things to the create_demo_data script if it will make your dev-life easier. 

## Running the development server 

This is a multi-tenant application. You can decide which tennant is running by choosing the port to use.

- `python manage.py runserver` will use port 8000 
- `python manage.py runserver 8001` will use port 8001

We are using the Django site framework to allow multi-tenant functionality. If you take a look at the `create_demo_data` script then you will see that there are a few different sites set up.




# Project layout

This is a Django project, the layout is as follows:

- `apps/` all core Django apps are in there 
- `config/` main project configuration (created using `django-admin startproject config .`)
- `concrete_apps/` This is for concrete implementations of the platform. The stuff in here will largely not be open source in the long term!  We are building out concrete implementations early on in order to make a proof of concept to show how the functionality can be extended.
- `demo_course_content/` This contains some fake learning content to demonstrate major functionality

When writing app code: 

- If something is generally useful as an LMS feature, it should live inside the `apps` directory
- If something has to do with a concrete implementation of the LMS (eg a custom version for a specific organisation), it should be in the `concrete_apps` directory.

To see which apps are in use, take a look at the `base_settings.py` file. Not all the apps are in use.


## Tests

To run the tests, run `pytest`. 

Currently the test coverage is not as high as it should be. This is not ideal and it's important to change that. 

### Bug fixes

When fixing bugs, it's useful to follow a TDD approach. This proves that you understand the bug, and it makes sure that the bug wont come back.

Step 1 - RED: Write a test that fails because the bug exists 
Step 2 - GREEN: Fix the bug so the test passes
Step 3 - Refactor: Tidy things up as needed 

## Testing frontend functionality 

Playwright can be used to test frontend interactions. Playwright is powerful so it is often tempting to use it to test ALL the things that touch the frontend. This is not ideal because it makes the tests really really slow.

Use Playwright to test things when Playwright is the only thing that will do the job.

# Making PRs 

Please make sure your PRs are as small as possible and cover one thing. Big PRs that cover lots of things end up being very hard to merge and very frustrating. 

Before making a PR:

- Rebase to make sure you have the latest code 
- Make sure all the tests pass 
- Look over the file changes in the PR yourself. Self-review the code before asking someone else to review. 

## On LLM-generated code 

LLMs write shitty, terrible code by default. It takes some skill to make them useful. A lot of the code in this repo was co-authored by an LLM with a LOT of guidance and iteration. You can use these tools, but only make PRs you personally trust.

LLMs are terrible at writing useful tests, will often break useful tests instead of fixing bugs, will often make code that is repetitive (as opposed to DRY), will introduce all sorts of unnecessary complexity, and a whole lot more!

So be careful. 

If you make a PR based on terrible code produced by an LLM, then it's your terrible code. Take personal responsibility for the quality of the work you produce.  

# Content Management 

This part is NOT OBVIOUS. We are doing something unusual here. 

Generally, LMSs allow users to manage content through some kind of CMS function - users interact with a bunch of fancy forms, and the content is stored in the database.

This is somewhat limiting because:

- It locks people into using a specific UI. If they wanted to use some kind of personal LLM workflow to help with the code then they would need to export and import the content. Pretty forms are pretty handcuffs 
- It prevents different kinds of collaboration and version control 

The way things work is: 
- Content is created using perfectly normal markdown files stored in perfectly normal directories 
- Yaml is used for content configuration
- The LMS can then ingest those directories to save them to the DB 

The downside of this is that people need to be comfortable working with Markdown and YAML. This isn't exactly difficult, but there is space for human error, especially when editing the markdown. 

It also means it's hard for people to see how the content will look as they edit it, they need to ingest it first, then look on the live system. 

One major upside of this approach is that content can be open-sourced. We will be creating some open-source courses, it would be good if people were able to access and edit the content for those courses. Git based collaboration is a must!

## Content admin interface 

Currently the admin panel contains waaaay more functionality than we would need in the final system. It's there to help with development. We should not be editing content through the admin interface.

