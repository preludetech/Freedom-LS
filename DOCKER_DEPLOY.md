# Docker Deployment Guide

This guide covers deploying the FreedomLS application using Docker Compose with nginx serving static and media files.

## Architecture

The deployment consists of three containers:
- **web**: Django application running with Gunicorn
- **db**: PostgreSQL database
- **nginx**: Reverse proxy serving static/media files and proxying requests to Django

## Setup

### 1. Create Environment File

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your production values


### 2. Build and Start Services

```bash
# Build the Django container
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps
```

### 3. Run Migrations

```bash
docker compose exec web python manage.py migrate
```

### 4. Set up some initial data

We need a Site in the database for everything to run. 

Replace the site name, domain and content path with something realistic.

```bash
# create the site
# docker compose exec web python manage.py create_site Demo 127.0.0.1
docker compose exec web python manage.py create_site Demo staging.freedomlearningsystem.org

# copy the content into the container
docker compose cp  ./demo_content  web:/app/content 

# save the content to the db
docker compose exec web python manage.py content_save  /app/content Demo

# cleanup
docker compose exec web rm -rf /app/content
```

## File Serving

- **Static files** (CSS, JS, images):Served using whitenoise from `/staticfiles/` (built during Docker build)
- **Media files** (uploads): Served by nginx from `/media/` (shared volume)

nginx configuration:
- Static files: 30-day cache
- Media files: 7-day cache
- Max upload size: 100MB

## Managing the Application

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f nginx
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart web
```

### Run Management Commands

```bash
docker-compose exec web python manage.py <command>
```

### Open an interactive shell 

```bash
docker compose exec -it web /bin/sh
```

### Stop Services

```bash
# Stop but keep containers
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

## Health Checks

All services have health checks configured:
- **web**: Checks `/health/` endpoint
- **db**: Checks PostgreSQL readiness
- **nginx**: Checks nginx is responding

View health status:
```bash
docker-compose ps
```

## Production Considerations

For true production deployment:

1. **SSL/TLS**: Add SSL certificate configuration to nginx
2. **Domain**: Update `ALLOWED_HOSTS` in staging settings
3. **Secrets Management**: Use Docker secrets or external secret management
4. **Backups**: Configure PostgreSQL backups
5. **Monitoring**: Add application monitoring (e.g., Sentry, New Relic)
6. **Log Aggregation**: Forward logs to a centralized logging system
