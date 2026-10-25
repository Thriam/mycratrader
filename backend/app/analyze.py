"""Full analysis pipeline: gather data -> features/algorithms -> timing -> LLM consensus."""

from datetime import datetime, timedelta
from typing import Dict

import numpy as np
import pandas as pd

from . import data
from . import ml
from . import openrouter
from .features import atr, rsi

HORIZONS = {
    "swing": {"days": 5, "label": "Swing trade (2-10 trading days)"},
    "positional": {"days": 21, "label": "Positional trade (2-8 weeks)"},
}


def _add_trading_days(start: datetime, days: int) -> datetime:
    """Approximate a future date skipping weekends (holidays ignored)."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _timing_block(daily: pd.DataFrame, intraday: pd.DataFrame,
                  pred: ml.PredictionResult, horizon_days: int,
                  currency: str) -> Dict:
    close = float(daily["Close"].iloc[-1])
    atr14 = float(atr(daily, 14).iloc[-1])
    rsi14 = float(rsi(daily["Close"], 14).iloc[-1])
    sma20 = float(daily["Close"].rolling(20).mean().iloc[-1])
    sma50 = float(daily["Close"].rolling(50).mean().iloc[-1])

    direction = 1 if pred.verdict in ("BUY", "HOLD") else -1
    if pred.verdict == "HOLD" and pred.prob_up < 0.5:
        direction = -1

    # Entry logic: chase breakouts less — enter near a slight pullback.
    if direction > 0:
        entry = close - 0.25 * atr14
        aggressive_gap = rsi14 > 70 or close > sma20 * 1.06
    else:
        entry = close + 0.25 * atr14
        aggressive_gap = rsi14 < 30 or close < sma20 * 0.94

    stop = entry - direction * 2.0 * atr14
    target = entry + direction * max(abs(pred.expected_move_pct), 0.02) * entry

    if aggressive_gap and pred.verdict in ("BUY", "SELL"):
        entry_hint = (
            "Stretched setup (RSI {:.0f}, price {:.1%} vs 20-SMA). Let it pull back "
            "toward the 20-SMA (~{:.2f}) before entering."
        ).format(rsi14, close / sma20 - 1, sma20)
    elif pred.verdict == "HOLD":
        entry_hint = (
            "No edge right now; models are near a coin flip on direction. "
            "Re-check after a few sessions or on a decisive close."
        )
    else:
        entry_hint = "Setup is tradeable now; a limit near the entry level improves fill."

    intraday_note = ""
    if not intraday.empty:
        last_sessions = intraday["Close"].tail(96)
        if len(last_sessions) >= 8:
            intraday_ret = float(last_sessions.iloc[-1] / last_sessions.iloc[0] - 1)
            intraday_note = (
                "Last ~10 sessions intraday trend: {:+.2%}; short-term momentum is {}."
            ).format(intraday_ret, "positive" if intraday_ret > 0 else "negative")

    exit_by = _add_trading_days(datetime.now(), horizon_days)

    return {
        "currency": currency,
        "current_price": round(close, 2),
        "entry_price": round(entry, 2),
        "stop_loss": round(stop, 2),
        "target": round(target, 2),
        "target_band_low": round(target * (1 - 0.5 * pred.move_band_pct), 2),
        "target_band_high": round(target * (1 + 0.5 * pred.move_band_pct), 2),
        "expected_holding_trading_days": horizon_days,
        "approx_exit_by": exit_by.strftime("%d %b %Y"),
        "entry_hint": entry_hint,
        "intraday_note": intraday_note,
        "indicators": {
            "rsi_14": round(rsi14, 1),
            "price_vs_sma20_pct": round(close / sma20 - 1, 4),
            "price_vs_sma50_pct": round(close / sma50 - 1, 4),
            "atr_14": round(atr14, 2),
        },
    }


def _self_check_block(daily_full: pd.DataFrame, as_of_ts: pd.Timestamp,
                      horizon_days: int, pred: ml.PredictionResult,
                      timing: Dict, mode: str) -> Dict:
    """Re-play the plan against candles that actually followed the as-of date."""
    as_of_close = float(daily_full.loc[daily_full.index <= as_of_ts, "Close"].iloc[-1])
    future = daily_full.loc[daily_full.index > as_of_ts]
    win = future.iloc[:horizon_days]
    if len(win) < horizon_days:
        raise ValueError(
            "Not enough candles after that date to evaluate the horizon "
            f"(need {horizon_days} trading days; got {len(future)}). Pick an earlier date."
        )
    eval_date = str(win.index[-1].date())
    close_at_eval = float(win["Close"].iloc[-1])
    actual_pct = close_at_eval / as_of_close - 1.0

    predicted_dir = "UP" if pred.prob_up > 0.5 else "DOWN"
    actual_dir = "UP" if actual_pct > 0 else "DOWN"

    entry, stop, target = timing["entry_price"], timing["stop_loss"], timing["target"]
    target_hit_on = stop_hit_on = None
    for idx, row in win.iterrows():
        d = str(idx.date())
        if stop_hit_on is None and float(row["Low"]) <= stop:
            stop_hit_on = d
        if target_hit_on is None and float(row["High"]) >= target:
            target_hit_on = d
        if stop_hit_on and target_hit_on:
            break
    if target_hit_on and (not stop_hit_on or target_hit_on <= stop_hit_on):
        outcome, detail = "TARGET_HIT", f"target reached on {target_hit_on}"
    elif stop_hit_on:
        outcome, detail = "STOPPED_OUT", f"stop hit on {stop_hit_on}"
    else:
        outcome, detail = "NO_TOUCH", (
            f"neither level touched within {horizon_days} trading days; "
            f"closed at {close_at_eval:.2f} on {eval_date}"
        )

    return {
        "mode": mode,
        "as_of": str(as_of_ts.date()),
        "as_of_close": round(as_of_close, 2),
        "horizon_trading_days": horizon_days,
        "evaluated_through": eval_date,
        "direction": {
            "predicted": predicted_dir,
            "actual": actual_dir,
            "correct": predicted_dir == actual_dir,
        },
        "move": {
            "predicted_pct": round(pred.expected_move_pct * 100, 2),
            "actual_pct": round(actual_pct * 100, 2),
            "error_pct": round(abs(pred.expected_move_pct - actual_pct) * 100, 2),
        },
        "plan": {
            "entry": entry, "stop": stop, "target": target,
            "outcome": outcome, "detail": detail,
        },
    }


def run_analysis(symbol: str, exchange: str, horizon: str,
                 mode: str = "real", as_of: str | None = None) -> Dict:
    horizon_key = (horizon or "swing").lower()
    if horizon_key not in HORIZONS:
        raise ValueError(f"Unknown horizon '{horizon}'; use 'swing' or 'positional'")
    if mode not in ("real", "check"):
        raise ValueError(f"Unknown mode '{mode}'; use 'real' or 'check'")
    horizon_days = HORIZONS[horizon_key]["days"]
    horizon_label = HORIZONS[horizon_key]["label"]

    yahoo_symbol = data.resolve_yahoo_symbol(symbol, exchange)
    profile = data.get_company_profile(yahoo_symbol)
    daily_full = data.get_daily_history(yahoo_symbol)

    # In self-check mode the engine must believe 'today' is the chosen date:
    # everything downstream trains and times trades on candles up to as_of only.
    as_of_ts = None
    if mode == "check":
        if not as_of:
            raise ValueError("Self-check mode requires an 'as_of' date (YYYY-MM-DD)")
        as_of_ts = pd.Timestamp(as_of)
        if daily_full.index.tz is not None:
            as_of_ts = as_of_ts.tz_localize(daily_full.index.tz)
        daily = daily_full.loc[daily_full.index <= as_of_ts]
        if len(daily) < 250:
            raise ValueError(
                f"Not enough history before {as_of} ({len(daily)} candles) to train on; "
                "pick an earlier-self date at least a year after the stock's listing."
            )
        intraday = pd.DataFrame()  # no peeking at the future
    else:
        daily = daily_full
        try:
            intraday = data.get_intraday_history(yahoo_symbol)
        except Exception:
            intraday = pd.DataFrame()

    if len(daily) < 250:
        raise RuntimeError(
            f"Not enough history for {yahoo_symbol} (only {len(daily)} daily candles)."
        )

    pred = ml.predict(daily, horizon_days)
    timing = _timing_block(daily, intraday, pred, horizon_days, profile["currency"])
    check = None
    if mode == "check":
        check = _self_check_block(daily_full, as_of_ts, horizon_days,
                                  pred, timing, mode)

    payload = {
        "stock": f"{profile['name']} ({symbol.upper()} on {exchange.upper()})",
        "sector": profile["sector"],
        "horizon": horizon_label,
        "current_price": timing["current_price"],
        "quant_verdict": pred.verdict,
        "ensemble_prob_up": round(pred.prob_up, 3),
        "expected_move_pct": round(pred.expected_move_pct * 100, 2),
        "move_band_pct": round(pred.move_band_pct * 100, 2),
        "confidence": round(pred.confidence, 3),
        "model_agreement": round(pred.model_agreement, 3),
        "walk_forward_accuracy": round(pred.backtest.get("accuracy", 0.5), 3),
        "walk_forward_mae_pct": round(pred.backtest.get("mae_pct", 0.0) * 100, 2),
        "key_indicators": timing["indicators"],
        "planned_entry_stop_target": {
            "entry": timing["entry_price"],
            "stop": timing["stop_loss"],
            "target": timing["target"],
        },
        "top_signals": {f["feature"]: f["weight"] for f in pred.feature_importance[:5]},
    }

    llm = openrouter.consensus(payload)

    return {
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "yahoo_symbol": yahoo_symbol,
        "company": profile["name"],
        "sector": profile["sector"],
        "horizon": horizon_key,
        "horizon_label": horizon_label,
        "mode": mode,
        "check": check,
        "prediction": {
            "verdict": pred.verdict,
            "prob_up": round(pred.prob_up, 4),
            "expected_move_pct": round(pred.expected_move_pct * 100, 2),
            "move_band_pct": round(pred.move_band_pct * 100, 2),
            "confidence": round(pred.confidence, 4),
            "model_agreement": round(pred.model_agreement, 4),
            "per_model": pred.per_model,
            "backtest": {
                "accuracy": round(pred.backtest.get("accuracy", 0.5), 4),
                "mae_pct": round(pred.backtest.get("mae_pct", 0.0) * 100, 2),
                "folds": pred.backtest.get("folds", 0),
            },
            "feature_importance": pred.feature_importance,
        },
        "timing": timing,
        "llm": llm,
        "disclaimer": "Educational research tool. Not investment advice; markets can and will disagree with any model.",
    }
