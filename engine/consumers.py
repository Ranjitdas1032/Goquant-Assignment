# engine/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .engine import BOOK  # singleton order book

class _BaseJsonConsumer(AsyncWebsocketConsumer):
    group = None

    async def connect(self):
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def emit_message(self, event):
        await self.send(text_data=json.dumps(event["data"]))

class MarketDataConsumer(_BaseJsonConsumer):
    group = "marketdata"

    async def connect(self):
        await super().connect()
        # send initial snapshots so UI shows something immediately
        await self.send(text_data=json.dumps({"type": "bbo", **BOOK._bbo()}))
        await self.send(text_data=json.dumps({"type": "l2",  **BOOK._l2_snapshot()}))

class TradesConsumer(_BaseJsonConsumer):
    group = "trades"
