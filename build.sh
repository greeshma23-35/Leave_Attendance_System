#!/usr/bin/env bash
set -o errexit
python manage.py makemigrations accounts attendance leaves --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput
