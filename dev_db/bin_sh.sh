#!/bin/sh
# Opens a superuser psql shell on the dev server. It runs inside the container over the local
# socket, which the postgres image trusts, so no password is needed.
exec docker compose -f "$(dirname "$0")/docker-compose.yaml" exec postgres psql -U pguser -d postgres
