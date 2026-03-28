import json
import os
from datetime import datetime, timezone
from collections import defaultdict

HISTORY_FILE = "signal_history.json"


def _load() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save(data: list):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_signal(signal: dict):
    history = _load()
    record = {
        "id": len(history) + 1,
        "pair": signal.get("pair", "XAUUSD"),
        "direction": signal["direction"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp1": signal["tp1"],
        "tp2": signal["tp2"],
        "tp3": signal["tp3"],
        "confidence": signal["confidence"],
        "trend": signal["trend"],
        "risk": signal["risk"],
        "timestamp": signal["timestamp"],
        "result": "OPEN",  # OPEN / WIN / LOSS / BREAKEVEN
    }
    history.append(record)
    _save(history)
    return record["id"]


def get_stats(pair: str = None) -> dict:
    history = _load()
    if pair:
        history = [h for h in history if h.get("pair") == pair]

    total = len(history)
    if total == 0:
        return {"total": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0, "by_pair": {}}

    wins = sum(1 for h in history if h["result"] == "WIN")
    losses = sum(1 for h in history if h["result"] == "LOSS")
    open_trades = sum(1 for h in history if h["result"] == "OPEN")
    closed = wins + losses
    winrate = round((wins / closed * 100) if closed > 0 else 0, 1)

    by_direction = defaultdict(lambda: {"total": 0, "wins": 0})
    by_pair = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})
    for h in history:
        by_direction[h["direction"]]["total"] += 1
        if h["result"] == "WIN":
            by_direction[h["direction"]]["wins"] += 1
        by_pair[h.get("pair", "XAUUSD")]["total"] += 1
        if h["result"] == "WIN":
            by_pair[h.get("pair", "XAUUSD")]["wins"] += 1
        if h["result"] == "LOSS":
            by_pair[h.get("pair", "XAUUSD")]["losses"] += 1

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "open": open_trades,
        "winrate": winrate,
        "by_direction": dict(by_direction),
        "by_pair": dict(by_pair),
        "last_5": history[-5:][::-1],
    }


def get_history(limit: int = 10, pair: str = None) -> list:
    history = _load()
    if pair:
        history = [h for h in history if h.get("pair") == pair]
    return history[-limit:][::-1]


def update_result(signal_id: int, result: str):
    """result: WIN / LOSS / BREAKEVEN"""
    history = _load()
    for record in history:
        if record["id"] == signal_id:
            record["result"] = result
            break
    _save(history)
