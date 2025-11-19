import time
import logging
from kalshi_python import Configuration, KalshiClient

# Kill the annoying docstring/help printing forever
logging.getLogger("kalshi_python").setLevel(logging.ERROR)

# ================== CONFIG ==================
IS_DEMO = True
HOST = "https://demo.api.kalshi.com/trade-api/v2" if IS_DEMO else "https://api.kalshi.com/trade-api/v2"

TARGET_EVENT_PREFIXES = ["NBA-", "NFL-", "NHL-", "MLB-", "CFB-", "CBB-", "WNBA-", "SOCCER-"]
SPREAD_CENTS = 2
ORDER_SIZE = 20
REFRESH_SECONDS = 45
MIN_VOLUME = 50_000
# ===========================================

config = Configuration(host=HOST)
client = KalshiClient(config)

print("Kalshi Sports Market Maker Bot STARTED (Demo Mode)" if IS_DEMO else "LIVE TRADING")

while True:
    try:
        balance = client.get_balance().balance / 100
        print(f"\n=== {time.strftime('%H:%M:%S')} | Demo Balance: ${balance:,.2f} ===")

        markets = []
        cursor = None
        while True:
            resp = client.get_markets(limit=500, cursor=cursor, status="open")
            for m in resp.markets:
                if any(m.event_ticker.startswith(p) for p in TARGET_EVENT_PREFIXES):
                    if m.volume >= MIN_VOLUME:
                        markets.append(m)
            cursor = resp.cursor
            if not cursor:
                break

        print(f"Found {len(markets)} liquid sports markets")

        for market in markets:
            ticker = market.ticker
            try:
                ob = client.get_market_orderbook(ticker).orderbook
                if not ob.yes_bid or not ob.yes_ask:
                    continue

                best_bid = max(b.price for b in ob.yes_bid)
                best_ask = min(a.price for a in ob.yes_ask)
                if best_ask - best_bid > 20:  # Skip insane spreads
                    continue

                mid = (best_bid + best_ask) // 2
                my_bid = max(mid - SPREAD_CENTS, 1)
                my_ask = min(mid + SPREAD_CENTS, 99)

                # Cancel old orders
                open_orders = client.get_orders(status="open", ticker=ticker).orders
                for o in open_orders:
                    client.cancel_order(o.order_id)

                # Position
                pos = 0
                for p in client.get_positions().positions:
                    if p.ticker == ticker:
                        pos = p.position
                        break

                if abs(pos) < 1000:
                    client.create_order(ticker=ticker, side="buy", type="limit", price=my_bid, count=ORDER_SIZE)
                    client.create_order(ticker=ticker, side="sell", type="limit", price=my_ask, count=ORDER_SIZE)

                print(f"{ticker[:35]:<35} {mid:>3}¢ → {my_bid}-{my_ask}¢ | Pos {pos:+4}")

            except Exception:
                pass  # Silent per-market fail

        print(f"Sleeping {REFRESH_SECONDS}s...\n")
        time.sleep(REFRESH_SECONDS)

    except Exception as e:
        print("Global error:", e)
        time.sleep(60)
