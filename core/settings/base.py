from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

DJANGO_APPS = [
    'daphne',  # must be before django.contrib.staticfiles for Channels ASGI server
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'django_celery_beat',
    'channels',
]

LOCAL_APPS = [
    'api',
    'apps.users',
    'apps.counselors',
    'apps.sessions',
    'apps.shadow_chat',
    'apps.jalibot',
    'apps.library',
    'apps.circle',
    'apps.assessments',
    'apps.referrals',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

AUTH_USER_MODEL = 'users.CustomUser'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Argon2 first (OWASP recommended, ~20x faster than PBKDF2 at equal strength for signup).
# PBKDF2 stays listed so existing users' hashes still verify and upgrade on next login.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'auth': '20/min',            # login / register / google sign-in
        'shadow_start': '10/hour',   # opening anonymous chats (blocks queue flooding)
        'shadow_message': '60/min',
    },
}

# ---- Video / voice calls -------------------------------------------------------------
CALL_JOIN_EARLY_MINUTES = config('CALL_JOIN_EARLY_MINUTES', default=10, cast=int)
CALL_JOIN_LATE_MINUTES = config('CALL_JOIN_LATE_MINUTES', default=30, cast=int)
# STUN is free. Add a TURN server (CALL_TURN_URL/USERNAME/CREDENTIAL) for students behind
# strict campus/mobile NATs; without TURN roughly 10-15% of calls cannot connect.
CALL_ICE_SERVERS = [{'urls': ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302']}]
_turn = config('CALL_TURN_URL', default='')
if _turn:
    CALL_ICE_SERVERS.append({
        'urls': [u.strip() for u in _turn.split(',')],
        'username': config('CALL_TURN_USERNAME', default=''),
        'credential': config('CALL_TURN_CREDENTIAL', default=''),
    })

# Where the web app (and its /workbooks/*.pdf downloads) is served. Set to the Netlify URL in prod.
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000').rstrip('/')

WHATSAPP_NUMBER = config('WHATSAPP_NUMBER', default='')  # digits only, e.g. 254700000000

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'apps.users.serializers.CustomTokenObtainPairSerializer',
}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000', cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-shadow-token',  # required for anonymous Shadow Chat sessions
]

CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TIMEZONE = 'Africa/Nairobi'

try:
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'cleanup-expired-shadow-sessions': {
            'task': 'shadow_chat.cleanup_expired_sessions',
            'schedule': crontab(minute='*/15'),
        },
    }
except ImportError:
    pass

# Live chat + calls fan out through the channel layer. Use Redis whenever REDIS_URL is set
# (required once you run more than one process/instance); otherwise fall back to in-memory,
# which is correct for a single Daphne process but silently breaks across multiple ones.
_redis_url = config('REDIS_URL', default='')
if _redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_redis_url]},
        },
    }
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
CLAUDE_API_KEY = config('CLAUDE_API_KEY', default=config('ANTHROPIC_API_KEY', default=''))
CLAUDE_MODEL = config('CLAUDE_MODEL', default='claude-sonnet-5-5')
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4o-mini')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-2.5-flash')
SHADOW_SESSION_TTL_HOURS = config('SHADOW_SESSION_TTL_HOURS', default=24, cast=int)
JALIBOT_MAX_OUTPUT_TOKENS = config('JALIBOT_MAX_OUTPUT_TOKENS', default=160, cast=int)
SHADOW_AI_FALLBACK_SECONDS = config('SHADOW_AI_FALLBACK_SECONDS', default=45, cast=int)
SHADOW_AI_SYNC = False  # tests flip this so the AI reply is generated inline
# Accepts GOOGLE_CLIENT_ID, or the shorter CLIENT_ID already used in this project's .env.
# Only the client ID is needed for Sign in with Google (ID-token flow); the client secret
# is never used and must never be sent to the browser.
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default=config('CLIENT_ID', default=''))
JALIBOT_RATE_LIMIT = config('JALIBOT_RATE_LIMIT', default=30, cast=int)
JALIBOT_CONVERSATION_TIMEOUT_MINUTES = config('JALIBOT_CONVERSATION_TIMEOUT_MINUTES', default=45, cast=int)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True
