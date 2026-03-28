import io
import random
import math
from datetime import datetime, timedelta, timezone

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyArrowPatch
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def _generate_candles(current_price: float, n: int = 48, pair: str = "XAUUSD") -> list:
    """Generate realistic-looking OHLC candles ending at current_price."""
    candles = []
    price = current_price * 0.98
    volatility = current_price * 0.004

    for i in range(n):
        body = random.gauss(0, volatility * 0.6)
        wick_up = abs(random.gauss(0, volatility * 0.4))
        wick_down = abs(random.gauss(0, volatility * 0.4))
        open_ = price
        close = price + body
        high = max(open_, close) + wick_up
        low = min(open_, close) - wick_down
        candles.append({"open": open_, "high": high, "low": low, "close": close})
        price = close

    # nudge last close to current_price
    diff = current_price - candles[-1]["close"]
    for c in candles[-8:]:
        for k in ["open", "high", "low", "close"]:
            c[k] += diff * 0.8
    return candles


def generate_signal_chart(signal: dict) -> bytes | None:
    if not MATPLOTLIB_AVAILABLE:
        return None

    pair = signal.get("pair", "XAUUSD")
    direction = signal["direction"]
    confidence = signal["confidence"]

    # Parse price
    try:
        price_str = signal.get("price", "$4415").replace("$", "").replace(",", "")
        current_price = float(price_str)
    except Exception:
        current_price = 4415.0

    # Parse levels
    def parse_price(s):
        try:
            return float(str(s).replace("$", "").replace(",", "").split("–")[0].strip())
        except Exception:
            return current_price

    sl = parse_price(signal["sl"])
    tp1 = parse_price(signal["tp1"])
    tp2 = parse_price(signal["tp2"])
    tp3 = parse_price(signal["tp3"])
    entry = current_price

    candles = _generate_candles(current_price, n=40, pair=pair)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")

    x = list(range(len(candles)))
    for i, c in enumerate(candles):
        color = "#26a641" if c["close"] >= c["open"] else "#f85149"
        ax.plot([i, i], [c["low"], c["high"]], color=color, linewidth=0.8, alpha=0.7)
        rect = plt.Rectangle(
            (i - 0.3, min(c["open"], c["close"])),
            0.6,
            abs(c["close"] - c["open"]) or current_price * 0.001,
            color=color, alpha=0.9
        )
        ax.add_patch(rect)

    last_x = len(candles) - 1

    # SL zone
    ax.axhline(sl, color="#f85149", linewidth=1.2, linestyle="--", alpha=0.85)
    ax.text(last_x + 0.5, sl, f" SL {sl:,.0f}", color="#f85149", va="center", fontsize=8.5, fontweight="bold")

    # TP levels
    tp_colors = ["#3fb950", "#58d68d", "#a9dfbf"]
    for tp_val, label, col in zip([tp1, tp2, tp3], ["TP1", "TP2", "TP3"], tp_colors):
        ax.axhline(tp_val, color=col, linewidth=1.0, linestyle=":", alpha=0.8)
        ax.text(last_x + 0.5, tp_val, f" {label} {tp_val:,.0f}", color=col, va="center", fontsize=8.5)

    # Entry line
    ax.axhline(entry, color="#f0b429", linewidth=1.5, linestyle="-", alpha=0.9)
    ax.text(last_x + 0.5, entry, f" Entry {entry:,.0f}", color="#f0b429", va="center", fontsize=9, fontweight="bold")

    # Shade risk zone
    ax.axhspan(min(entry, sl), max(entry, sl), alpha=0.08, color="#f85149")
    # Shade reward zone TP1-TP2
    ax.axhspan(min(tp1, tp2), max(tp1, tp2), alpha=0.06, color="#3fb950")

    # Signal arrow
    arrow_color = "#3fb950" if direction == "BUY" else "#f85149"
    dy = current_price * 0.012
    ax.annotate(
        "",
        xy=(last_x, entry + (dy if direction == "BUY" else -dy)),
        xytext=(last_x, entry + (-dy if direction == "BUY" else dy)),
        arrowprops=dict(arrowstyle="->", color=arrow_color, lw=2.5),
    )

    # EMA lines (simulated)
    ema50 = signal.get("ema50", current_price * 1.01)
    ema200 = signal.get("ema200", current_price * 1.03)
    ax.axhline(ema50, color="#9b59b6", linewidth=1.0, linestyle="-", alpha=0.5)
    ax.axhline(ema200, color="#e67e22", linewidth=1.0, linestyle="-", alpha=0.5)
    ax.text(0.5, ema50, "EMA50", color="#9b59b6", fontsize=7.5, alpha=0.8)
    ax.text(0.5, ema200, "EMA200", color="#e67e22", fontsize=7.5, alpha=0.8)

    # Title
    sig_emoji = "▲ BUY" if direction == "BUY" else ("▼ SELL" if direction == "SELL" else "— NO TRADE")
    ax.set_title(
        f"{pair}  |  {sig_emoji}  |  Confidence: {confidence}%  |  {signal['timestamp']}",
        color="white", fontsize=11, fontweight="bold", pad=10
    )

    # Axes styling
    ax.tick_params(colors="#8b949e", labelsize=8)
    ax.spines[:].set_color("#30363d")
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    ax.set_xlim(-1, last_x + 6)
    ax.set_ylabel("Price", color="#8b949e", fontsize=8)
    ax.grid(axis="y", color="#21262d", linewidth=0.5, alpha=0.6)

    # Legend
    legend_items = [
        mpatches.Patch(color="#f0b429", label="Entry"),
        mpatches.Patch(color="#f85149", label="Stop Loss"),
        mpatches.Patch(color="#3fb950", label="Take Profit"),
        mpatches.Patch(color="#9b59b6", label="EMA 50"),
        mpatches.Patch(color="#e67e22", label="EMA 200"),
    ]
    ax.legend(handles=legend_items, loc="upper left", facecolor="#161b22",
              edgecolor="#30363d", labelcolor="white", fontsize=8, framealpha=0.9)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
