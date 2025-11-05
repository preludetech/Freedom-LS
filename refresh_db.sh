#!/bin/sh

rm db.sqlite3
rm -rf media
python manage.py makemigrations
python manage.py migrate
python manage.py setup_demo_data


python manage.py content_save  ../tutorial-getting-git Prelude
python manage.py content_save  ../bloom_content Bloom          