#!/bin/sh

rm db.sqlite3
rm -rf media
python manage.py makemigrations
python manage.py migrate

python manage.py create_demo_data
python manage.py content_save  ./demo_content Demo

# migrate the Bloom stuff 
python manage.py makemigrations --settings concrete_apps.bloom_student_interface.config.settings_dev
python manage.py migrate --settings concrete_apps.bloom_student_interface.config.settings_dev
python manage.py content_save  ../bloom_content/Content Bloom

