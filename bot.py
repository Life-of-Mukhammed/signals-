import asyncio
import logging
import os
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from signal_engine import get_signal, get_all_signals, get_supported_pairs
from history import save_signal, get_stats, get_history
from risk_calc import calculate_lot_size, PIP_VALUES
from chart import generate_signal_chart

load_dotenv()
BOT_TOKEN = os.getenv("8680342112:AAGrAZMugJ7hRnrmsZrAOHo9KRAX-ZANjzo")
TWELVE_DATA_KEY = os.getenv("77260265312844138c2b3aaae9886cec", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
subscribed_chats: set = set()

# Conversation states
CALC_BALANCE, CALC_RISK, CALC_ENTRY, CALC_SL, CALC_PAIR = range(5)
calc_data = {}


# ─── FORMATTERS ──────────────────────────────────────────────

def fmt_signal(signal: dict) -> str:
    d = signal["direction"]
    sig_line = "🔴 *SELL*" if d == "SELL" else ("🟢 *BUY*" if d == "BUY" else "⚪ *NO TRADE*")
    trend_icon = "📉" if signal["trend"] == "Bearish" else ("📈" if signal["trend"] == "Bullish" else "➡️")
    risk_icon = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(signal["risk"], "⚪")
    pair = signal.get("pair", "XAUUSD")

    return (
        f"╔══════════════════════════╗\n"
        f"║  📊 *{pair} SIGNAL*\n"
        f"╚══════════════════════════╝\n\n"
        f"*SIGNAL:* {sig_line}\n"
        f"*ENTRY:* `{signal['entry']}`\n"
        f"*STOP LOSS:* `{signal['sl']}`\n\n"
        f"📌 *TAKE PROFIT*\n"
        f"├ TP1: `{signal['tp1']}`\n"
        f"├ TP2: `{signal['tp2']}`\n"
        f"└ TP3: `{signal['tp3']}`\n\n"
        f"{trend_icon} *TREND:* {signal['trend']}\n"
        f"{risk_icon} *RISK:* {signal['risk']}\n"
        f"🎯 *CONFIDENCE:* {signal['confidence']}%\n"
        f"💰 *R:R:* `{signal['rr']}`\n\n"
        f"📝 *STRATEGY:*\n_{signal['strategy']}_\n\n"
        f"🕐 `{signal['timestamp']}`\n\n"
        f"⚠️ _Not financial advice. Manage risk carefully._"
    )


def fmt_stats(stats: dict, pair: str = "All pairs") -> str:
    if stats["total"] == 0:
        return "📊 *No signal history yet.*\nSend /signal to generate your first signal!"

    lines = [
        f"📊 *Signal Statistics — {pair}*\n",
        f"Total signals: `{stats['total']}`",
        f"✅ Wins: `{stats['wins']}`",
        f"❌ Losses: `{stats['losses']}`",
        f"🔓 Open: `{stats['open']}`",
        f"📈 Win rate: `{stats['winrate']}%`\n",
    ]

    if stats.get("by_pair"):
        lines.append("*By pair:*")
        for p, v in stats["by_pair"].items():
            wr = round(v["wins"] / max(v["wins"] + v["losses"], 1) * 100, 1)
            lines.append(f"  `{p}` — {v['total']} signals | {wr}% WR")

    if stats.get("last_5"):
        lines.append("\n*Last 5 signals:*")
        for h in stats["last_5"]:
            icon = {"WIN": "✅", "LOSS": "❌", "OPEN": "🔓", "BREAKEVEN": "➡️"}.get(h["result"], "❓")
            lines.append(f"  {icon} `{h['pair']}` {h['direction']} — {h['timestamp'][:10]}")

    return "\n".join(lines)


# ─── KEYBOARDS ───────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Get Signal", callback_data="signal_XAUUSD"),
         InlineKeyboardButton("📡 All Pairs", callback_data="all_signals")],
        [InlineKeyboardButton("📈 Statistics", callback_data="stats"),
         InlineKeyboardButton("🧮 Risk Calc", callback_data="calc_start")],
        [InlineKeyboardButton("🔔 Subscribe", callback_data="subscribe"),
         InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


def pairs_keyboard():
    pairs = get_supported_pairs()
    buttons = []
    row = []
    for i, (pair, info) in enumerate(pairs.items()):
        row.append(InlineKeyboardButton(f"{pair}", callback_data=f"signal_{pair}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# ─── HANDLERS ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Pro Signal Bot*\n\n"
        "Institutional-grade signals for:\n"
        "• Gold (XAUUSD) • Bitcoin (BTCUSDT)\n"
        "• EURUSD • GBPUSD • USDJPY\n\n"
        "Powered by SMC + EMA + RSI confluence.\n\n"
        "Choose an option:",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data.startswith("signal_"):
        pair = data.split("_", 1)[1]
        msg = await query.message.reply_text(f"⏳ Analyzing {pair}...")
        signal = await get_signal(pair, TWELVE_DATA_KEY)
        save_signal(signal)
        text = fmt_signal(signal)
        chart_bytes = generate_signal_chart(signal)
        await msg.delete()
        if chart_bytes:
            await query.message.reply_photo(
                photo=InputFile(BytesIO(chart_bytes), filename="signal.png"),
                caption=text,
                parse_mode="Markdown",
            )
        else:
            await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "all_signals":
        await query.message.reply_text("📡 Select a pair for its signal:", reply_markup=pairs_keyboard())

    elif data == "stats":
        stats = get_stats()
        await query.message.reply_text(fmt_stats(stats), parse_mode="Markdown")

    elif data == "subscribe":
        subscribed_chats.add(chat_id)
        await query.message.reply_text(
            "✅ *Subscribed!*\nYou'll get signals every 4h:\n`00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC`",
            parse_mode="Markdown",
        )

    elif data == "unsubscribe":
        subscribed_chats.discard(chat_id)
        await query.message.reply_text("🔕 Unsubscribed from auto-signals.")

    elif data == "back_main":
        await query.message.reply_text("Main menu:", reply_markup=main_keyboard())

    elif data == "calc_start":
        await start_calc(query, context)

    elif data == "help":
        await query.message.reply_text(
            "*Commands:*\n"
            "/start — Main menu\n"
            "/signal — XAUUSD signal\n"
            "/pairs — Choose pair\n"
            "/allsignals — All pairs at once\n"
            "/stats — Signal history\n"
            "/calc — Risk/lot calculator\n"
            "/subscribe — Auto every 4h\n"
            "/status — Bot status\n\n"
            "*Signal guide:*\n"
            "🟢 BUY | 🔴 SELL | ⚪ NO TRADE\n\n"
            "Never risk more than 1-2% per trade.",
            parse_mode="Markdown",
        )


# ─── COMMANDS ────────────────────────────────────────────────

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = context.args[0].upper() if context.args else "XAUUSD"
    if pair not in get_supported_pairs():
        pair = "XAUUSD"
    msg = await update.message.reply_text(f"⏳ Analyzing {pair}...")
    signal = await get_signal(pair, TWELVE_DATA_KEY)
    save_signal(signal)
    chart_bytes = generate_signal_chart(signal)
    await msg.delete()
    if chart_bytes:
        await update.message.reply_photo(
            photo=InputFile(BytesIO(chart_bytes), filename="signal.png"),
            caption=fmt_signal(signal),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(fmt_signal(signal), parse_mode="Markdown")


async def pairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Choose a pair:", reply_markup=pairs_keyboard())


async def allsignals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Analyzing all pairs... this takes ~10 seconds.")
    signals = await get_all_signals(TWELVE_DATA_KEY)
    await msg.delete()
    for sig in signals:
        save_signal(sig)
        await update.message.reply_text(fmt_signal(sig), parse_mode="Markdown")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = context.args[0].upper() if context.args else None
    stats = get_stats(pair)
    await update.message.reply_text(fmt_stats(stats, pair or "All pairs"), parse_mode="Markdown")


async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscribed_chats.add(update.effective_chat.id)
    await update.message.reply_text(
        "✅ *Subscribed!* Auto-signals every 4 hours.",
        parse_mode="Markdown",
    )


async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscribed_chats.discard(update.effective_chat.id)
    await update.message.reply_text("🔕 Unsubscribed.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs = ", ".join(get_supported_pairs().keys())
    await update.message.reply_text(
        f"🤖 *Bot Status:* Online ✅\n"
        f"👥 *Subscribers:* {len(subscribed_chats)}\n"
        f"📊 *Pairs:* {pairs}\n"
        f"📡 *Live data:* {'✅ Twelve Data' if TWELVE_DATA_KEY else '⚠️ Simulation mode'}\n"
        f"⏱ *Auto-signal:* Every 4 hours",
        parse_mode="Markdown",
    )


# ─── RISK CALCULATOR (Conversation) ──────────────────────────

async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs_str = " | ".join(PIP_VALUES.keys())
    await update.message.reply_text(
        f"🧮 *Risk / Lot Size Calculator*\n\n"
        f"Supported pairs: `{pairs_str}`\n\n"
        f"Step 1/4 — Enter your *account balance* (USD):\n"
        f"Example: `10000`",
        parse_mode="Markdown",
    )
    return CALC_BALANCE


async def start_calc(query, context):
    await query.message.reply_text(
        "🧮 *Risk / Lot Size Calculator*\n\n"
        "Step 1/4 — Enter your *account balance* (USD):\n"
        "Example: `10000`",
        parse_mode="Markdown",
    )
    return CALC_BALANCE


async def calc_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", ""))
        context.user_data["balance"] = val
        await update.message.reply_text(
            f"✅ Balance: `${val:,.2f}`\n\n"
            "Step 2/4 — Enter your *risk %* per trade:\n"
            "Example: `1` (for 1%)",
            parse_mode="Markdown",
        )
        return CALC_RISK
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number. Example: `10000`", parse_mode="Markdown")
        return CALC_BALANCE


async def calc_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace("%", ""))
        if val <= 0 or val > 20:
            raise ValueError
        context.user_data["risk"] = val
        await update.message.reply_text(
            f"✅ Risk: `{val}%`\n\n"
            "Step 3/4 — Enter your *entry price*:\n"
            "Example: `4415.50`",
            parse_mode="Markdown",
        )
        return CALC_ENTRY
    except ValueError:
        await update.message.reply_text("❌ Enter a valid risk % (0–20). Example: `1`", parse_mode="Markdown")
        return CALC_RISK


async def calc_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", ""))
        context.user_data["entry"] = val
        await update.message.reply_text(
            f"✅ Entry: `{val}`\n\n"
            "Step 4/4 — Enter your *stop loss price*:\n"
            "Example: `4380`",
            parse_mode="Markdown",
        )
        return CALC_SL
    except ValueError:
        await update.message.reply_text("❌ Enter a valid price. Example: `4415.50`", parse_mode="Markdown")
        return CALC_ENTRY


async def calc_sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sl = float(update.message.text.replace(",", ""))
        context.user_data["sl"] = sl
        pairs_str = "\n".join([f"  `{p}`" for p in PIP_VALUES.keys()])
        await update.message.reply_text(
            f"✅ Stop Loss: `{sl}`\n\n"
            f"Final step — enter the *pair*:\n{pairs_str}",
            parse_mode="Markdown",
        )
        return CALC_PAIR
    except ValueError:
        await update.message.reply_text("❌ Enter a valid price.", parse_mode="Markdown")
        return CALC_SL


async def calc_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.message.text.strip().upper()
    if pair not in PIP_VALUES:
        await update.message.reply_text(
            f"❌ Unknown pair. Choose from:\n`{'`, `'.join(PIP_VALUES.keys())}`",
            parse_mode="Markdown",
        )
        return CALC_PAIR

    d = context.user_data
    result = calculate_lot_size(d["balance"], d["risk"], d["entry"], d["sl"], pair)

    if "error" in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return ConversationHandler.END

    direction = "SELL" if d["entry"] > d["sl"] else "BUY"
    dir_icon = "🔴 SELL" if direction == "SELL" else "🟢 BUY"

    await update.message.reply_text(
        f"🧮 *Risk Calculator Result*\n\n"
        f"*Pair:* `{pair}`  |  *Direction:* {dir_icon}\n\n"
        f"💼 *Account:* `${result['account_balance']:,.2f}`\n"
        f"⚠️ *Risk:* `{result['risk_percent']}%` = `${result['risk_amount']:,.2f}`\n"
        f"📏 *SL Distance:* `{result['sl_pips']:.1f} pips`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *LOT SIZE: `{result['lot_size']}`*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *If SL hit:* `-${result['potential_loss']:,.2f}`\n"
        f"✅ *TP1 profit:* `+${result['tp1_gain']:,.2f}` ({result['rr_tp1']})\n"
        f"✅ *TP2 profit:* `+${result['tp2_gain']:,.2f}` ({result['rr_tp2']})\n\n"
        f"_Always verify lot size with your broker._",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def calc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Calculator cancelled.")
    return ConversationHandler.END


# ─── AUTO BROADCAST ──────────────────────────────────────────

async def broadcast_signal(app: Application):
    if not subscribed_chats:
        return
    logger.info(f"Broadcasting to {len(subscribed_chats)} subscribers...")
    signals = await get_all_signals(TWELVE_DATA_KEY)
    for sig in signals:
        if sig["direction"] == "NO TRADE":
            continue
        save_signal(sig)
        text = "🔔 *Auto Signal Alert*\n\n" + fmt_signal(sig)
        chart_bytes = generate_signal_chart(sig)
        for chat_id in list(subscribed_chats):
            try:
                if chart_bytes:
                    await app.bot.send_photo(
                        chat_id=chat_id,
                        photo=InputFile(BytesIO(chart_bytes), filename="signal.png"),
                        caption=text,
                        parse_mode="Markdown",
                    )
                else:
                    await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Failed to send to {chat_id}: {e}")
                subscribed_chats.discard(chat_id)


# ─── MAIN ─────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in .env")

    app = Application.builder().token(BOT_TOKEN).build()

    calc_handler = ConversationHandler(
        entry_points=[
            CommandHandler("calc", calc_cmd),
        ],
        states={
            CALC_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_balance)],
            CALC_RISK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_risk)],
            CALC_ENTRY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_entry)],
            CALC_SL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_sl)],
            CALC_PAIR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_pair)],
        },
        fallbacks=[CommandHandler("cancel", calc_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("pairs", pairs_cmd))
    app.add_handler(CommandHandler("allsignals", allsignals_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(calc_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    scheduler.add_job(broadcast_signal, "cron", hour="0,4,8,12,16,20", minute=0, args=[app])
    scheduler.start()

    logger.info("🚀 Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
