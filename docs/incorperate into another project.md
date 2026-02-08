# How to use this in another project 

This Learning System is designed to be extended and overwritten.  You can run it as a standalone project and it will work, but the real power is that you can build your own student interfaces on top of it.

## Set up 

```
uv init
```


```
git submodule add git@github.com:preludetech/Freedom-LS.git submodules/Freedom-LS
```










### Install dependencies 

uv add... TODO 

### settings.py 

TODO:

INSTALLED_APPS 
make sure to add contrib.sites 

MIDDLEWARE 
TEMPLATES 

STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files (User uploaded files)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)


MARKDOWN_ALLOWED_TAGS = {
    "c-youtube": {"video_id", "video_title"},
    "c-picture": {"src", "alt", "caption"},
    "c-callout": {"level", "title"},
    "c-content-link": {"path"},
}

MARKDOWN_TEMPLATE_RENDER_ON = True
COTTON_SNAKE_CASED_NAMES = False

HEADLESS_CLIENTS = ("app",)
ACCOUNT_SIGNUP_FIELDS = ["email*", "email2*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_ADAPTER = "accounts.allauth_account_adapter.AccountAdapter"

### urls.py 

TODO


### Tailwind set up 

copy `package-lock.json` and `package.json` and `tailwind.input.css` into your own project root.

run `npm i` 

Add this to your gitignore:

```
node_modules/
static/vendor/
```

Run `npm run tailwind_watch`

You can now edit `tailwind.input.css` to make it do what you want.


### Conftest: 
copy it across 

### playwright 

run playwright install 

## Dev dependencies
install manually