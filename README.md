# 📊 Pro Signal Bot — Full Setup Guide

## ✨ Features
- Signals for XAUUSD, BTCUSDT, EURUSD, GBPUSD, USDJPY
- Chart image with every signal (candlestick + levels)
- Risk/lot size calculator (step-by-step in chat)
- Signal history & win rate statistics
- Auto-broadcast every 4 hours to subscribers

---

## Local Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env → add BOT_TOKEN
python bot.py
```

---

## Railway Deployment (Free, 24/7)

1. Push all files to a private GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard:
   - BOT_TOKEN = your telegram bot token
   - TWELVE_DATA_KEY = (optional) from twelvedata.com
4. Click Deploy — live in ~2 minutes

Railway free tier ($5/month credit) runs this bot 24/7.

---

## Commands

/start — Main menu
/signal — XAUUSD signal
/signal BTCUSDT — specific pair
/pairs — choose pair
/allsignals — all 5 pairs
/stats — win rate & history
/calc — risk/lot calculator
/subscribe — auto signals every 4h
/unsubscribe — stop auto signals
/status — bot info
/cancel — cancel calculator

---

## Optional: Live Prices

Get a free key at twelvedata.com (800 req/day).
Add as TWELVE_DATA_KEY in .env or Railway variables.
Without it, bot uses realistic market simulation.

---

Not financial advice. Always use a stop loss.
