#!/bin/sh


python manage.py makemigrations
python manage.py migrate

python manage.py create_demo_data
python manage.py content_save  ./demo_content Demo
