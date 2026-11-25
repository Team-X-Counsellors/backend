release: python manage.py migrate --noinput --settings=core.settings.production
web: daphne -b 0.0.0.0 -p $PORT core.asgi:application
