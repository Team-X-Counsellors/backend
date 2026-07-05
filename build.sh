#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input --settings=core.settings.production
python manage.py migrate --settings=core.settings.production
