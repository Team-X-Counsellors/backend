import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')

django_asgi_app = get_asgi_application()  # must run before importing consumers (app registry)

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402
from core.routing import websocket_urlpatterns  # noqa: E402

# The frontend lives on a different origin from the API, so validate against the same list
# CORS uses (ALLOWED_HOSTS would wrongly reject it). Auth is per-consumer (token/JWT in the
# query string, no cookies), so this origin check is the CSRF-equivalent guard for sockets.
_origins = ['*'] if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False) else list(settings.CORS_ALLOWED_ORIGINS)

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': OriginValidator(URLRouter(websocket_urlpatterns), _origins),
})
