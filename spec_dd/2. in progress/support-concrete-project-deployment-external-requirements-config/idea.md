We will need to integrate with certain third-party services in production.

We will need to set things up for staging and prod.
We will need to make sure our conventions around settings using AppSettings to be followed.

Either this should go in the freedom_ls base app or in a new "production" app.

# Context

This should support the work being done in spec_dd/2. in progress/support-concrete-project-deployment/

That spec has been broken down into multiple specs

# services

## posthog
We already have a system in place for getting it installed, but it just grabs the posthog_api_key from environmental variables. It should use the AppSettings machinery.

## Sentry
Not yet implemented.
Production deployments will need: `uv add "sentry-sdk" `

in settings.py we need:

```
import sentry_sdk

sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)
```

Urls.py will need this so we can test it

```
from django.urls import path

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('sentry-debug/', trigger_error),
    # ...
]
```

## Cloudflare R2
This is S3-compatable

## Others

See: spec_dd/2. in progress/support-concrete-project-deployment/third-party-services.md
