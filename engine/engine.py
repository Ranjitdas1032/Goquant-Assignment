# engine/engine.py
from collections import deque, defaultdict
from bisect import bisect_left, bisect_right, insort
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Trade

DEC = Decimal

def utcnow():
    return datetime.now(tz=timezone.utc).isoformat()

class PriceLevel:
    def __init__(self):
        self.orders = deque()  # [(order_dict)]
        self.qty = DEC("0")

    def add(self, order):
        self.orders.append(order)
        self.qty += order["qty_remaining"]

    def pop_front(self):
        o = self.orders.popleft()
        self.qty -= o["qty_remaining"]
        return o

    def __bool__(self): return len(self.orders) > 0

class SideBook:
    """
    price-sorted keys + map: price -> PriceLevel
    bids: descending; asks: ascending
    """
    def __init__(self, is_bid):
        self.is_bid = is_bid
        self.prices = []      # list of Decimal prices (sorted)
        self.levels = {}      # price -> PriceLevel

    def best_price(self):
        if not self.prices: return None
        return self.prices[-1] if self.is_bid else self.prices[0]

    def _ins_price(self, p):
        if p in self.levels: return
        insort(self.prices, p)
        self.levels[p] = PriceLevel()

    def _del_price_if_empty(self, p):
        lvl = self.levels.get(p)
        if lvl and not lvl:
            del self.levels[p]
            idx = bisect_left(self.prices, p)
            if idx < len(self.prices) and self.prices[idx] == p:
                self.prices.pop(idx)

    def add_order(self, order):
        p = order["price"]
        self._ins_price(p)
        self.levels[p].add(order)

    def iter_prices(self):
        return reversed(self.prices) if self.is_bid else iter(self.prices)

class OrderBook:
    def __init__(self, symbol="BTC-USDT"):
        self.symbol = symbol
        self.bids = SideBook(is_bid=True)
        self.asks = SideBook(is_bid=False)
        self.channel_layer = get_channel_layer()

    # ---------- Public API ----------
    def submit(self, order):
        """
        order: dict {type, side, qty, price?, id}
        """
        order = dict(order)
        order.setdefault("id", str(uuid4()))
        order["qty_remaining"] = DEC(str(order["quantity"]))
        order["price"] = DEC(str(order.get("price", "0")))

        if order["order_type"] == "market":
            self._match_marketable(order)
        elif order["order_type"] in ("limit", "ioc", "fok"):
            self._handle_limit_family(order)
        else:
            raise ValueError("Unsupported order_type")

        self._broadcast_l2_and_bbo()
        return order["id"]

    # ---------- Matching ----------
    def _handle_limit_family(self, o):
        # Check immediate matchability
        marketable = self._is_marketable(o)
        if o["order_type"] == "fok":
            # Ensure full fill possible; else cancel
            if not self._can_fully_fill(o):
                o["qty_remaining"] = DEC("0")
                return
            # If yes, fall through and execute
        if marketable:
            self._match_marketable(o)

        # If anything remains:
        if o["qty_remaining"] > 0:
            if o["order_type"] == "ioc":
                # cancel the rest
                o["qty_remaining"] = DEC("0")
                return
            # Resting limit
            (self.bids if o["side"] == "buy" else self.asks).add_order(o)

    def _is_marketable(self, o):
        bp = self.bids.best_price()
        ap = self.asks.best_price()
        if o["side"] == "buy":
            if ap is None: return False
            return (o["order_type"] == "market") or (o["price"] >= ap)
        else:
            if bp is None: return False
            return (o["order_type"] == "market") or (o["price"] <= bp)

    def _can_fully_fill(self, o):
        need = o["qty_remaining"]
        if o["side"] == "buy":
            for p in self.asks.iter_prices():
                if o["order_type"] == "limit" and p > o["price"]: break
                need -= self.asks.levels[p].qty
                if need <= 0: return True
            return False
        else:
            for p in self.bids.iter_prices():
                if o["order_type"] == "limit" and p < o["price"]: break
                need -= self.bids.levels[p].qty
                if need <= 0: return True
            return False

    def _match_marketable(self, o):
        if o["side"] == "buy":
            book = self.asks
            price_ok = (lambda p: True) if o["order_type"] == "market" else (lambda p: p <= o["price"])
        else:
            book = self.bids
            price_ok = (lambda p: True) if o["order_type"] == "market" else (lambda p: p >= o["price"])

        for p in list(book.iter_prices()):
            if o["qty_remaining"] <= 0: break
            if not price_ok(p): break
            lvl = book.levels[p]

            # FIFO within level
            while o["qty_remaining"] > 0 and lvl:
                maker = lvl.orders[0]  # peek
                qty = min(o["qty_remaining"], maker["qty_remaining"])
                self._execute_trade(price=p, qty=qty, maker=maker, taker=o)

                maker["qty_remaining"] -= qty
                o["qty_remaining"] -= qty
                lvl.qty -= qty

                if maker["qty_remaining"] <= 0:
                    lvl.orders.popleft()

            if not lvl:
                # remove empty price level
                book._del_price_if_empty(p)

    # ---------- Events ----------
    def _execute_trade(self, price, qty, maker, taker):
        trade = Trade.objects.create(
            symbol=self.symbol,
            price=price,
            qty=qty,
            aggressor_side=taker["side"],
            maker_order_id=maker["id"],
            taker_order_id=taker["id"],
        )
        payload = {
            "timestamp": utcnow(),
            "symbol": self.symbol,
            "trade_id": trade.trade_id,
            "price": str(price),
            "quantity": str(qty),
            "aggressor_side": taker["side"],
            "maker_order_id": maker["id"],
            "taker_order_id": taker["id"],
        }
        async_to_sync(self.channel_layer.group_send)(
            "trades", {"type": "emit.message", "data": payload}
        )

    # ---------- Market Data ----------
    def _l2_snapshot(self, depth=10):
        asks = []
        for p in self.asks.prices[:depth]:
            asks.append([str(p), str(self.asks.levels[p].qty)])
        bids = []
        for p in reversed(self.bids.prices[-depth:]):
            bids.append([str(p), str(self.bids.levels[p].qty)])
        return {
            "timestamp": utcnow(),
            "symbol": self.symbol,
            "asks": asks, "bids": bids,
        }

    def _bbo(self):
        bp = self.bids.best_price()
        ap = self.asks.best_price()
        return {
            "timestamp": utcnow(),
            "symbol": self.symbol,
            "best_bid": str(bp) if bp is not None else None,
            "best_offer": str(ap) if ap is not None else None,
        }

    def _broadcast_l2_and_bbo(self):
        snap = self._l2_snapshot()
        bbo = self._bbo()
        async_to_sync(self.channel_layer.group_send)(
            "marketdata", {"type": "emit.message", "data": {"type": "l2", **snap}}
        )
        async_to_sync(self.channel_layer.group_send)(
            "marketdata", {"type": "emit.message", "data": {"type": "bbo", **bbo}}
        )

# single global book for assignment
BOOK = OrderBook(symbol="BTC-USDT")
