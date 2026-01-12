# Deploying to CapRover

Once you have a running Capover instance set up, you can deploy simply with:


```
caprover deploy --caproverUrl $CAPROVER_URL --caproverApp $CAPROVER_APP 
```

- `CAPROVER_URL` will be something like `https://captain.whatever.domain.com`
- It's important to make sure that the `CAPROVER_APP_TOKEN` environmental variable is set


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
docker cp Freedom-LS/demo_content $CONTAINER:/app/content 
```

Then open a shell into the container, create a Site and save the content. 

```
python manage.py create_site Demo freedom-ls.staging.freedomlearningsystem.org
python manage.py content_save  /app/content Demo

# delete the content from disk when done
rm -rf /app/content
```