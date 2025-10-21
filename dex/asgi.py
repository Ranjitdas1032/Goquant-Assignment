# dex/asgi.py
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

# 1) Configure settings first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dex.settings")

# 2) Initialize Django (app registry) before importing anything that touches models
django_asgi_app = get_asgi_application()

# 3) Now it's safe to import consumers (they import engine/models)
from engine.consumers import MarketDataConsumer, TradesConsumer  # noqa: E402

# 4) Build the ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("ws/marketdata/", MarketDataConsumer.as_asgi()),
        path("ws/trades/", TradesConsumer.as_asgi()),
    ]),
})
