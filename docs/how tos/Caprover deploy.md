# Deploying to CapRover

Once you have a running Capover instance set up, you can deploy simply with:


```
caprover deploy --caproverUrl $CAPROVER_URL --caproverApp $CAPROVER_APP  --branch main
```

- `CAPROVER_URL` will be something like `https://captain.whatever.domain.com`
- It's important to make sure that the `CAPROVER_APP_TOKEN` environmental variable is set

## Tailwind build is required

The Tailwind CSS bundle is **not** committed to the repo. Your image build (Dockerfile / `captain-definition`) must run:

```
npm ci
npm run tailwind_build
```

before `collectstatic` / before the image is finalised. This step:

- generates `tailwind.active_theme.css` at the project root (gitignored), and
- compiles `static/vendor/tailwind.output.css` (also gitignored) — the file Django/whitenoise actually serves.

Skip it and you will either get a build error (missing `tailwind.active_theme.css`) or ship stale CSS.

`FLS_THEME` (default `default`) selects which theme tokens get baked into the bundle. It is read by `scripts/write-active-theme.mjs` **at build time**, so it must be present as a build arg / build-time env var — setting it only at runtime is too late for the CSS. Node and npm must be available in the build stage (they are not needed at runtime).


## Set up the database

```
CONTAINER=$(docker ps --filter name=srv-captain--$CAPROVER_APP -q)
```

```
docker exec -it $CONTAINER /bin/sh
python manage.py migrate
```

## Add Content

In a prod environment you would want to add real content. This is how you can add the demo content:

First, get the content onto the container:

```
gh repo clone preludetech/Freedom-LS
cd Freedom-LS
git pull
docker cp demo_content $CONTAINER:/app/content
```

Then open a shell into the container, create a Site and save the content.

```
python manage.py create_site Demo freedom-ls.staging.freedomlearningsystem.org
python manage.py content_save  /app/content Demo

# delete the content from disk when done
rm -rf /app/content
```
