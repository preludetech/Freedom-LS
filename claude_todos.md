# Upgrade tests to use FactoryBoy

Go over all the tests.

Use update the tests to use factories defined using factoryboy. Factories should be defined on an app level under tests/factories.

Every time you trite a test, run it to make sure it passes before moving onto anything else.

# Github action for unit testing 

Create a github action that runs unit tests every time code is pushed or a PR is created.

It needs to make use of postgres. The container should match the configuration in dev_db/docker_compose.yaml

Note that we are using Playwright for some tests. The action should run all the playwright tests in all major browsers.

The tests should run and pass before any other code review steps are taken

# Update claude hooks settings

Ruff configuration should target Django-specific rules. In pyproject.toml, enable the DJ rule selector alongside standard Python rules. This catches Django-specific anti-patterns like unordered Meta.fields or incorrect model string representations. Configure known-first-party in isort settings to match your project structure.


Me:
- type checking 
- https://claude.ai/chat/472ac9ff-c7c3-4b02-88c6-73d434f317d1