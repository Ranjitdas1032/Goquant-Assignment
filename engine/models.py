# engine/models.py
from uuid import uuid4
from django.db import models
from django.utils import timezone

class Trade(models.Model):
    trade_id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    ts = models.DateTimeField(default=timezone.now, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    price = models.DecimalField(max_digits=30, decimal_places=10)
    qty = models.DecimalField(max_digits=30, decimal_places=10)
    aggressor_side = models.CharField(max_length=4)  # "buy" or "sell"
    maker_order_id = models.CharField(max_length=64)
    taker_order_id = models.CharField(max_length=64)
