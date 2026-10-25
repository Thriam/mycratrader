# FUTUREPLANS

Where the project goes next, roughly in order of priority.

## Near term (next few weekends)

- **Persist trained models** — joblib-serialize fitted models per symbol/horizon keyed
  by last candle date, so repeat analyses skip the full retrain and return in seconds.
- **Symbol autocomplete** — a searchable index of NSE/BSE listings (code + company name)
  so users don't have to know listing symbols, plus currency/paid-up info in the header.
- **Streaming progress** — Server-Sent Events from the backend so the dashboard shows
  live pipeline stages (fetch → features → train → backtest → LLM) instead of a spinner.
- **Better free-model handling** — rotate across more `:free` models, back off on 429s,
  and remember which models are currently alive.

## Medium term

- **Intraday horizon** — a third mode trained on 15-minute features for same-day calls
  with entry windows (e.g. "buy in the 10:00–10:30 window").
- **Sector-relative features** — normalize features against sector peers and the index
  (NIFTY 50 / SENSEX), and combine market-breadth into the trade plan.
- **Events** — earnings dates, dividends and corporate actions flagged in the plan,
  since gaps around them break stop losses.
- **Full backtest of the trade plan** — currently the backtest scores direction/return;
  next step is replaying the actual entry/stop/target rule over history and reporting
  expectancy, drawdown and holding-time distribution.
- **Watchlists + persistence** — user accounts, saved symbols, re-run on schedule, and
  store past predictions to score the app's own track record over time.

## Longer term

- **Options data** — NSE option chain sampling: IV, PCR and OI shifts as extra features.
- **Alerts** — Telegram/email/webhook notification when a plan's entry zone is reached.
- **Deployment story** — Dockerfile for backend + frontend, a lightweight scheduler that
  refreshes watchlists daily, and hosted mode.
- **Test suite + CI** — pytest for the pipeline with recorded responses, and Playwright
  smoke tests for the dashboard.
- **Ensemble of horizons** — one meta-model that weighs swing vs positional blended
  probabilities and can echo "swing says buy, positional says wait".

## Explicitly out of scope

- No paid data feeds; all data stays free/open endpoints.
- No premium (non-`:free`) LLM calls, ever.
- No auto-trading / broker integration. The user reads the plan and decides.
