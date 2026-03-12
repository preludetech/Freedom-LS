#!/bin/sh

uv sync
npm i

claude mcp add playwright npx '@playwright/mcp@latest'

# Set up per-branch database
./dev_db_init.sh

# Apply migrations
uv run manage.py migrate

# Create demo data (all sites)
uv run manage.py create_demo_data

# Load demo content
uv run manage.py content_save ./demo_content DemoDev
