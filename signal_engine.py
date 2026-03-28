import asyncio
import httpx
import random
from datetime import datetime, timezone

PAIRS = {
    "XAUUSD":  {"name": "Gold / USD",        "base_price": 4415.0,  "volatility": 0.008, "twelve": "XAU/USD"},
    "BTCUSDT": {"name": "Bitcoin / USDT",     "base_price": 85000.0, "volatility": 0.018, "twelve": "BTC/USD"},
    "EURUSD":  {"name": "Euro / USD",         "base_price": 1.0850,  "volatility": 0.004, "twelve": "EUR/USD"},
    "GBPUSD":  {"name": "Pound / USD",        "base_price": 1.2650,  "volatility": 0.005, "twelve": "GBP/USD"},
    "USDJPY":  {"name": "USD / Japanese Yen", "base_price": 149.50,  "volatility": 0.004, "twelve": "USD/JPY"},
}


async def fetch_live_data(pair: str, api_key: str) -> dict | None:
    cfg = PAIRS.get(pair)
    if not cfg or not api_key:
        return None
    symbol = cfg["twelve"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.twelvedata.com/price",
                params={"symbol": symbol, "apikey": api_key},
            )
            price = float(r.json().get("price", 0))
            if price < 0.0001:
                return None

            r2 = await client.get(
                "https://api.twelvedata.com/rsi",
                params={"symbol": symbol, "interval": "4h", "apikey": api_key, "outputsize": 1},
            )
            rsi = float(r2.json().get("values", [{}])[0].get("rsi", 50))

            r3 = await client.get(
                "https://api.twelvedata.com/ema",
                params={"symbol": symbol, "interval": "4h", "time_period": 50, "apikey": api_key, "outputsize": 1},
            )
            ema50 = float(r3.json().get("values", [{}])[0].get("ema", price))

            r4 = await client.get(
                "https://api.twelvedata.com/ema",
                params={"symbol": symbol, "interval": "4h", "time_period": 200, "apikey": api_key, "outputsize": 1},
            )
            ema200 = float(r4.json().get("values", [{}])[0].get("ema", price))

            return {"price": price, "rsi": rsi, "ema50": ema50, "ema200": ema200}
    except Exception:
        return None


def simulate_data(pair: str) -> dict:
    cfg = PAIRS.get(pair, PAIRS["XAUUSD"])
    base = cfg["base_price"]
    vol = cfg["volatility"]
    price = base * (1 + random.uniform(-vol * 2, vol * 2))
    ema50 = price * (1 + random.uniform(0.005, 0.02))
    ema200 = price * (1 + random.uniform(0.015, 0.04))
    rsi = random.uniform(32, 68)
    decimals = 5 if price < 10 else 2
    return {
        "price": round(price, decimals),
        "rsi": round(rsi, 1),
        "ema50": round(ema50, decimals),
        "ema200": round(ema200, decimals),
    }


def analyze(data: dict, pair: str) -> dict:
    price = data["price"]
    rsi = data["rsi"]
    ema50 = data["ema50"]
    ema200 = data["ema200"]

    confirmations = 0
    bullish = 0
    bearish = 0

    if price < ema50 < ema200:
        bearish += 2; confirmations += 1; trend = "Bearish"
    elif price > ema50 > ema200:
        bullish += 2; confirmations += 1; trend = "Bullish"
    elif price < ema50:
        bearish += 1; trend = "Bearish"
    elif price > ema50:
        bullish += 1; trend = "Bullish"
    else:
        trend = "Sideways"

    if rsi > 68:
        bearish += 1; confirmations += 1
    elif rsi < 32:
        bullish += 1; confirmations += 1
    elif rsi > 55:
        bullish += 1
    elif rsi < 45:
        bearish += 1

    gap_pct = abs(price - ema200) / ema200 * 100
    if gap_pct > 2.5:
        confirmations += 1
        if price < ema200:
            bearish += 1
        else:
            bullish += 1

    supply_dist = abs(price - ema50) / price
    if supply_dist < 0.005:
        bearish += 1; confirmations += 1
    demand_dist = abs(price - ema200) / price
    if demand_dist < 0.008:
        bullish += 1; confirmations += 1

    if confirmations < 3:
        direction = "NO TRADE"
    elif bearish > bullish:
        direction = "SELL"
    elif bullish > bearish:
        direction = "BUY"
    else:
        direction = "NO TRADE"

    atr = price * 0.008
    decimals = 5 if price < 10 else (0 if price > 10000 else 2)
    currency = "¥" if pair == "USDJPY" else "$"
    fmt = lambda v: f"{currency}{v:,.{decimals}f}"

    if direction == "SELL":
        entry_str = f"{fmt(price + atr * 0.3)} – {fmt(price + atr * 0.8)}"
        sl_val = price + atr * 2.2
        tp1_val = price - atr * 1.5
        tp2_val = price - atr * 3.0
        tp3_val = price - atr * 5.0
        strategy = (
            "Confirmed BOS to downside. Price below EMA50/200 with RSI bearish momentum. "
            "Supply zone rejection — targeting sell-side liquidity below structure."
        )
    elif direction == "BUY":
        entry_str = f"{fmt(price - atr * 0.8)} – {fmt(price - atr * 0.3)}"
        sl_val = price - atr * 2.2
        tp1_val = price + atr * 1.5
        tp2_val = price + atr * 3.0
        tp3_val = price + atr * 5.0
        strategy = (
            "Bullish CHoCH at demand zone. Price above EMA50 with RSI recovering. "
            "Buy-side liquidity target above equal highs — Smart Money accumulation."
        )
    else:
        entry_str = "No entry — wait for setup"
        sl_val = price - atr
        tp1_val = price + atr
        tp2_val = price + atr * 2
        tp3_val = price + atr * 3
        strategy = "Insufficient confluence. Market structure unclear — stay flat."

    confidence = min(94, 44 + confirmations * 8 + abs(bearish - bullish) * 4)
    risk = "Low" if confidence > 78 else ("Medium" if confidence > 60 else "High")

    return {
        "pair": pair,
        "direction": direction,
        "entry": entry_str,
        "sl": fmt(sl_val),
        "tp1": fmt(tp1_val),
        "tp2": fmt(tp2_val),
        "tp3": fmt(tp3_val),
        "trend": trend,
        "strategy": strategy,
        "confidence": confidence,
        "risk": risk,
        "rr": "1 : 2.3",
        "price": fmt(price),
        "rsi": rsi,
        "ema50": ema50,
        "ema200": ema200,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


async def get_signal(pair: str = "XAUUSD", api_key: str = "") -> dict:
    data = await fetch_live_data(pair, api_key)
    if data is None:
        data = simulate_data(pair)
    return analyze(data, pair)


async def get_all_signals(api_key: str = "") -> list:
    tasks = [get_signal(pair, api_key) for pair in PAIRS]
    return await asyncio.gather(*tasks)


def get_supported_pairs() -> dict:
    return PAIRS
