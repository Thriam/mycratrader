# mycratrader — User Manual

A research dashboard that predicts NSE/BSE stock direction over a few days or a few
weeks, and hands you a concrete trade plan: entry price, stop loss, target, and the
approximate date to exit.

> This is a research tool, not financial advice. Models are wrong often — the app tries
> to tell you *how often* by backtesting itself honestly and showing its accuracy.

---

## 1. Starting the app

### Backend (FastAPI, port 8000)

```bash
cd backend
python -m venv venv                  # first time only
venv/Scripts/python -m pip install -r requirements.txt    # first time only
venv/Scripts/python -m uvicorn app.main:app --port 8000
```

### Optional: turn on the free-LLM consensus

The app calls **only OpenRouter models whose id ends in `:free`**. Copy
`backend/.env.example` to `backend/.env`, put your key behind `OPENROUTER_API_KEY=`,
and restart the backend. Without a key everything still runs; the consensus card will
just say it is unavailable.

### Frontend (Next.js, port 3000)

```bash
cd frontend
npm install                          # first time only
npm run dev                          # open http://localhost:3000
```

If the backend runs on another host, set `NEXT_PUBLIC_API_BASE_URL` before starting.

Health check: `http://localhost:8000/api/health` should return `"status": "ok"`.

---

## 2. Running a prediction

On the dashboard, fill in:

| Field | What to type / pick |
|---|---|
| Stock symbol | The listing symbol, e.g. `RELIANCE`, `TCS`, `TATAMOTORS` (a full suffix like `RELIANCE.NS` also works) |
| Exchange | `NSE` or `BSE` toggle |
| Horizon | `Swing 2–10d` (holds for days) or `Positional 2–8w` (holds for weeks) |

Press **Predict**. The first analysis of a symbol takes around 1–2 minutes because six
models are trained and walk-forward backtested. Repeat queries within five minutes are
near-instant (data cache). Results appear in cards explained below.

---

## 3. Reading the results

### Verdict header

- **BUY / SELL / HOLD** — ensemble machine-learning verdict.
  A dashed border means the OpenRouter models voted differently from the quant engine.
- **Current** — last traded close.
- **P(up) ensemble** — probability the price is higher after the horizon. 0.55+ leans
  BUY, below 0.45 leans SELL, in between is a coin flip and usually means HOLD.
- **Exp. move** — expected % move over the horizon, deliberately shrunk by the observed
  backtest error so regression overfit does not inflate it.
- **Confidence** — blends direction edge, backtest accuracy and model agreement.
- **Backtest acc.** — out-of-sample hit rate over 5 rolling cross-validation folds. This
  is the honest number; on daily NSE data, anywhere from 50% to 60% is normal.
- **Agreement** — fraction of direction models voting the same way.

### Trade plan & timing

- **Entry** — limit-style price, slightly better than market so you don't chase.
- **Stop loss** — 2×ATR(14) from entry.
- **Target** — entry ± expected move, with a band.
- **Exit by (≈)** — the calendar date about `N` trading days out.
- **Entry hint** — if the stock is stretched (RSI > 70, price > 6% over the 20-SMA) it
  tells you to wait for a pullback instead of entering immediately.
- **Intraday note** — short-term momentum read from recent 15-minute candles.

### Indicator & signal cards

RSI, distance to 20/50-SMA, ATR, and the features the tree models relied on most
(importance bars). Use these to sanity-check the verdict.

### Chart

Last ~130 daily candles; the dashed blue line overlays recent intraday closes. To the
right of today's candle, a shaded **forecast cone** shows the expected price range at
the horizon (target band), a dashed midline pulls toward the target, and dashed level
lines mark the planned **T**arget, **E**ntry and **S**top across the chart.

### OpenRouter free-model consensus

Up to three free models independently review **only the computed statistics** (they get
no other market access) and return a verdict, a short thesis, risks and a timing note,
with a vote tally. Consider it a second opinion, not an extra brain — where they all
agree with the quant verdict, conviction is higher.

---

## 4. Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| `No market data returned for ...` (HTTP 404) | Symbol doesn't exist on that exchange. Check the listing symbol. |
| Dashboard shows `Quant prediction above runs without it` | No `OPENROUTER_API_KEY` in `backend/.env`, or all free-model calls failed (free tiers throttle; retry later). |
| First prediction very slow | Normal: six models are trained plus rollback evaluation. Cached for 5 minutes. |
| Port already in use | Backend: change `--port 8000`. Frontend: `npm run dev -- -p 3001`. |
| Prediction looks frozen | Leave it running; terminal shows uvicorn log lines when done. |

---

## 5. Good habits

1. Start with the backtest accuracy — below ~52% on swing horizon, treat as low-conviction.
2. Always respect the stop loss; prices can jump through gaps overnight.
3. Compare both horizons before committing capital; they can disagree.
4. If the LLM verdict differs from the quant verdict, understand *why* before you act
   on either.
5. Weekly positional calls rely on more distant history and will flip more slowly —
   don't re-trade on every daily refresh.
