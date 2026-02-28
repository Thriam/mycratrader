"""Technical feature engineering for the prediction pipeline."""

import numpy as np
import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd_hist(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


FEATURE_NAMES = [
    "ret_1", "ret_5", "ret_10", "ret_20",
    "close_vs_sma5", "close_vs_sma20", "close_vs_sma50", "close_vs_sma200",
    "rsi_14", "macd_hist_norm", "bollinger_pctb", "atr_ratio",
    "volatility_20", "volume_z_20", "highlow_range", "gap_strength",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the model feature matrix from daily OHLCV data."""
    close = df["Close"]
    feat = pd.DataFrame(index=df.index)

    # Momentum / returns
    feat["ret_1"] = close.pct_change(1)
    feat["ret_5"] = close.pct_change(5)
    feat["ret_10"] = close.pct_change(10)
    feat["ret_20"] = close.pct_change(20)

    # Trend: price relative to moving averages
    for window in (5, 20, 50, 200):
        sma = close.rolling(window).mean()
        feat[f"close_vs_sma{window}"] = close / sma - 1.0

    # Mean-reversion / overbought-oversold
    feat["rsi_14"] = rsi(close, 14) / 100.0
    feat["macd_hist_norm"] = macd_hist(close) / close

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    feat["bollinger_pctb"] = (close - (sma20 - 2 * std20)) / (4 * std20)

    feat["atr_ratio"] = atr(df, 14) / close
    feat["volatility_20"] = close.pct_change().rolling(20).std() * np.sqrt(252)

    vol_mean = df["Volume"].rolling(20).mean()
    vol_std = df["Volume"].rolling(20).std().replace(0, np.nan)
    feat["volume_z_20"] = ((df["Volume"] - vol_mean) / vol_std).clip(-5, 10)

    feat["highlow_range"] = (df["High"] - df["Low"]) / close
    feat["gap_strength"] = (df["Open"] - close.shift(1)) / close

    return feat.dropna(how="all")
