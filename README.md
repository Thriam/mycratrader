# mycratrader

Full-stack NSE/BSE stock prediction research tool.

The application gathers ~8 years of daily OHLCV candles (plus recent 15-minute candles)
for **any stock listed on the NSE or BSE**, engineers 16 technical features, trains **six
algorithms** (3 direction classifiers + 3 return regressors), walk-forward backtests
them for honest out-of-sample accuracy, computes a trade plan with entry / stop-loss /
target / expected exit date, and finally asks **OpenRouter free models only** (ids ending
in `:free`) to independently review the numbers and vote BUY / SELL / HOLD.

```
frontend/   Next.js 15 + React 19 + Tailwind 4 dashboard (candle chart, verdict, trade plan)
backend/    Python FastAPI + yfinance + scikit-learn + statsmodels + httpx
```

## What you get per query

- **Verdict** — BUY / SELL / HOLD from the ML ensemble, shown with the free-LLM vote if it differs
- **P(up)** — ensemble probability the price is higher after the chosen horizon
- **Expected move** — shrinkage-calibrated % move with a band, target price and target band
- **Timing** — entry price (limit-style, respects stretched setups), stop-loss (2×ATR),
  target, approx exit calendar date, holding days, and an entry hint
  (enter now vs wait for pullback to the 20-SMA)
- **Trust metrics** — walk-forward out-of-sample accuracy over 5 rolling folds, MAE,
  model agreement, per-model probabilities, top feature importances
- **Chart** — daily candlesticks with recent intraday overlay
- **LLM consensus** — up to 3 free OpenRouter models review the computed stats only
  (they get no other market access) and give a verdict, thesis, risks and timing note

Horizons: **Swing (2–10 trading days)** and **Positional (2–8 weeks)** — pick per query.

## Run it

### 1. Backend (Python 3.12+)

```bash
cd backend
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: venv/bin/pip
venv/Scripts/python -m uvicorn app.main:app --port 8000  # Linux/macOS: venv/bin/uvicorn ...
```

### 2. OpenRouter key (free models)

Copy `backend/.env.example` → `backend/.env` and paste your key from
[openrouter.ai/keys](https://openrouter.ai/keys). The catalog is fetched live and **only
models whose id ends in `:free` are ever called**; without a key the app still runs in
quant-only mode and the dashboard shows a notice instead of LLM commentary.

### 3. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL` if the backend runs somewhere other than `http://localhost:8000`.

## Architecture notes

- **Data gathering is ours, not the LLM's** — yfinance (`.NS` for NSE, `.BO` for BSE) with a
  5-minute TTL cache; the models only ever see model-computed statistics.
- **Algorithms**: LogisticRegression, RandomForestClassifier, GradientBoostingClassifier
  (direction); statsmodels OLS, RidgeCV, GradientBoostingRegressor (magnitude). Ensemble =
  mean of classifier probabilities + median of regressor returns.
- **Walk-forward evaluation** re-trains across 5 rolling-origin folds on the most recent
  history, so the reported accuracy is out-of-sample, not in-sample curve-fitting.
- **Calibration**: the expected move is shrunk by the backtest MAE so regression overfit
  doesn't produce fantasy targets.

## Disclaimer

Educational research software, not investment advice. Equity prediction is extremely
hard; even a "trustworthy" looking backtest can fail live. Always evaluate results
yourself before risking money.
