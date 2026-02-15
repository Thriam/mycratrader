"""Market data gathering layer.

Gathers OHLCV candles for any NSE/BSE listed stock through Yahoo Finance
("our application" does the data gathering; the LLM only interprets it).
NSE symbols get a `.NS` suffix, BSE symbols get a `.BO` suffix.

Every fetch is cached in-memory with a TTL so repeated analyses of the same
stock do not re-download data.
"""

import time
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Simple TTL cache
# ---------------------------------------------------------------------------

_CACHE: Dict[Tuple[str, str, str, str], Tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_get(key: Tuple[str, str, str, str]) -> Optional[pd.DataFrame]:
    hit = _CACHE.get(key)
    if hit is None:
        return None
    stamp, df = hit
    if time.time() - stamp > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return df


def _cache_put(key: Tuple[str, str, str, str], df: pd.DataFrame) -> pd.DataFrame:
    _CACHE[key] = (time.time(), df)
    return df


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

def resolve_yahoo_symbol(symbol: str, exchange: str) -> str:
    symbol = symbol.strip().upper()
    exchange = exchange.strip().upper()
    if "." in symbol:
        return symbol  # user already typed RELIANCE.NS etc.
    if exchange == "NSE":
        return f"{symbol}.NS"
    if exchange == "BSE":
        return f"{symbol}.BO"
    raise ValueError(f"Unsupported exchange: {exchange}")


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def _fetch(ticker_symbol: str, period: str, interval: str) -> pd.DataFrame:
    cache_key = (ticker_symbol, period, interval, "ohlcv")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(
            f"No market data returned for '{ticker_symbol}'. "
            "Check the stock symbol and exchange (NSE/BSE)."
        )

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = df.dropna(subset=["Close"])
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    return _cache_put(cache_key, df)


def get_daily_history(yahoo_symbol: str, period: str = "8y") -> pd.DataFrame:
    """Daily OHLCV candles used for training and backtesting."""
    return _fetch(yahoo_symbol, period, "1d")


def get_intraday_history(yahoo_symbol: str) -> pd.DataFrame:
    """Recent 15-minute candles; used for short-term timing context."""
    return _fetch(yahoo_symbol, "60d", "15m")


def get_company_profile(yahoo_symbol: str) -> dict:
    """Basic company metadata (name, sector) from Yahoo; cached separately."""
    cache_key = (yahoo_symbol, "profile", "", "raw")
    hit = _CACHE.get(cache_key)
    if hit is not None and time.time() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    try:
        info = yf.Ticker(yahoo_symbol).info or {}
    except Exception:
        info = {}
    profile = {
        "name": info.get("shortName") or info.get("longName") or yahoo_symbol,
        "sector": info.get("sector") or "Unknown",
        "industry": info.get("industry") or "Unknown",
        "currency": info.get("currency") or "INR",
    }
    _CACHE[cache_key] = (time.time(), profile)
    return profile
