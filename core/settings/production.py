from .base import *
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Railway/Render terminate TLS at their proxy. Without this header Django never sees the
# request as secure and SECURE_SSL_REDIRECT below becomes an infinite redirect loop.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ['.up.railway.app', '.railway.app']
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS', default='https://*.up.railway.app,https://jalimind.netlify.app', cast=Csv()
)
CORS_ALLOWED_ORIGINS = list(CORS_ALLOWED_ORIGINS) + ['https://jalimind.netlify.app']

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
