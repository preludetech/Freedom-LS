SENTRY_RELEASE needs to be filled in if SENTRY is used at all. If it is blank, while there is a SENTRY_DSN then we need to see the problem quickly.

Update the template repo dockerfile. SENTRY_RELEASE should be set at build time, it belongs to the image. This should be done in the concrete template repo, and any other concrete repos.
