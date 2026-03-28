"""
Risk calculator — computes lot size based on account balance,
risk %, entry and stop loss for any supported pair.
"""

PIP_VALUES = {
    "XAUUSD": {"pip_size": 0.1,  "pip_value_per_lot": 10.0},   # Gold: 1 lot = 100oz
    "BTCUSDT": {"pip_size": 1.0,  "pip_value_per_lot": 1.0},    # Crypto CFD approx
    "EURUSD":  {"pip_size": 0.0001,"pip_value_per_lot": 10.0},  # Forex standard
    "GBPUSD":  {"pip_size": 0.0001,"pip_value_per_lot": 10.0},
    "USDJPY":  {"pip_size": 0.01,  "pip_value_per_lot": 9.1},   # approx at 110
    "USDCHF":  {"pip_size": 0.0001,"pip_value_per_lot": 10.0},
    "AUDUSD":  {"pip_size": 0.0001,"pip_value_per_lot": 10.0},
}


def calculate_lot_size(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
    pair: str = "XAUUSD",
) -> dict:
    if pair not in PIP_VALUES:
        pair = "XAUUSD"

    pip_info = PIP_VALUES[pair]
    pip_size = pip_info["pip_size"]
    pip_value = pip_info["pip_value_per_lot"]

    risk_amount = account_balance * (risk_percent / 100)
    sl_distance = abs(entry_price - stop_loss_price)

    if sl_distance == 0:
        return {"error": "Entry and Stop Loss cannot be the same price."}

    sl_in_pips = sl_distance / pip_size
    lot_size = risk_amount / (sl_in_pips * pip_value)
    lot_size = max(0.01, round(lot_size, 2))

    # Cap sanity check
    max_lot = account_balance / 1000
    lot_size = min(lot_size, max_lot)

    potential_loss = sl_in_pips * pip_value * lot_size
    potential_gain_tp1 = potential_loss * 1.5
    potential_gain_tp2 = potential_loss * 2.5

    return {
        "pair": pair,
        "account_balance": account_balance,
        "risk_percent": risk_percent,
        "risk_amount": round(risk_amount, 2),
        "entry": entry_price,
        "stop_loss": stop_loss_price,
        "sl_pips": round(sl_in_pips, 1),
        "lot_size": lot_size,
        "potential_loss": round(potential_loss, 2),
        "tp1_gain": round(potential_gain_tp1, 2),
        "tp2_gain": round(potential_gain_tp2, 2),
        "rr_tp1": "1 : 1.5",
        "rr_tp2": "1 : 2.5",
    }
