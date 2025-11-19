import time
import os
from kalshi_python import Configuration, KalshiClient

# ================== CONFIG ==================
IS_DEMO = True  # Keep True until you're 100% ready for real money
HOST = "https://demo.api.kalshi.com/trade-api/v2" if IS_DEMO else "https://api.kalshi.com/trade-api/v2"

# Only these leagues/events right now (add/remove as you wish)
TARGET_EVENT_PREFIXES = [
    "NBA-", "NFL-", "NHL-", "MLB-", "CFB-", "CBB-", "WNBA-", "SOCCER-"
]

SPREAD_CENTS = 2          # How many cents away from mid you quote
ORDER_SIZE = 20           # Contracts per order (demo is unlimited fake money)
REFRESH_SECONDS = 45      # How often to refresh quotes
MAX_POSITION_PER_MARKET = 1000
# ===========================================

config = Configuration(host=HOST)
client = KalshiClient(config)

if not IS_DEMO:
    # Only needed for live trading later
    config.api_key_id = os.getenv('KALSHI_API_KEY_ID')
    with open("private_key.pem", "r") as f:
        config.private_key_pem = f.read()

def get_active_sports_markets():
    markets = []
    cursor = None
    while True:
        resp = client.get_markets(
            limit=1000,
            cursor=cursor,
            status="open",
            event_ticker=None  # All events
        )
        for m in resp.markets:
            if any(m.event_ticker.startswith(p) for p in TARGET_EVENT_PREFIXES):
                if m.volume > 50000:  # Only reasonably liquid ones
                    markets.append(m)
        cursor = resp.cursor
        if not cursor:
            break
    return markets

while True:
    try:
        print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} | Scanning for sports markets ===")
        sports_markets = get_active_sports_markets()
        
        print(f"Found {len(sports_markets)} liquid sports markets")
        
        for market in sports_markets:
            ticker = market.ticker
            try:
                ob = client.get_market_orderbook(ticker).orderbook
                if not ob.yes_bid or not ob.yes_ask:
                    continue
                    
                best_bid = max([x.price for x in ob.yes_bid]) if ob.yes_bid else 0
                best_ask = min([x.price for x in ob.yes_ask]) if ob.yes_ask else 100
                if best_bid == 0 or best_ask == 100:
                    continue
                    
                mid = (best_bid + best_ask) // 2
                my_bid = max(mid - SPREAD_CENTS, 1)
                my_ask = min(mid + SPREAD_CENTS, 99)
                
                # Cancel old orders
                open_orders = client.get_orders(status="open", ticker=ticker).orders
                for o in open_orders:
                    client.cancel_order(o.order_id)
                
                # Check position
                pos_resp = client.get_positions()
                pos = 0
                for p in pos_resp.positions:
                    if p.ticker == ticker:
                        pos = p.position  # positive = long YES
                        break
                
                if abs(pos) < MAX_POSITION_PER_MARKET:
                    client.create_order(ticker=ticker, side="buy",  type="limit", price=my_bid, count=ORDER_SIZE)
                    client.create_order(ticker=ticker, side="sell", type="limit", price=my_ask, count=ORDER_SIZE)
                    
                print(f"{ticker} | Mid {mid}¢ | Quote {my_bid}-{my_ask}¢ | Pos {pos}")
                
            except Exception as e:
                print(f"Error on {ticker}: {e}")
                
        print(f"Sleeping {REFRESH_SECONDS}s...")
        time.sleep(REFRESH_SECONDS)
        
    except Exception as e:
        print("Global error:", e)
        time.sleep(60)
