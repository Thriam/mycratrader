"""FastAPI app exposing the analysis pipeline to the Next.js frontend."""

import os
from pathlib import Path
from typing import Any, Dict, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data
from .analyze import run_analysis

# Load backend/.env for OPENROUTER_API_KEY (kept out of the repo).
BACKEND_ENV = Path(__file__).resolve().parent.parent / ".env"
if BACKEND_ENV.exists():
    load_dotenv(BACKEND_ENV)

app = FastAPI(title="mycratrader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-friendly; tighten for production deploys
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    symbol: str
    exchange: Literal["NSE", "BSE"] = "NSE"
    horizon: Literal["swing", "positional"] = "swing"


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "openrouter_key_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


@app.post("/api/predict")
def predict(req: PredictRequest) -> Dict[str, Any]:
    try:
        return run_analysis(req.symbol, req.exchange, req.horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.get("/api/history")
def history(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
    yahoo_symbol = data.resolve_yahoo_symbol(symbol, exchange)
    try:
        daily = data.get_daily_history(yahoo_symbol, period="1y")
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    try:
        intraday = data.get_intraday_history(yahoo_symbol)
    except Exception:
        intraday = None

    def rows(df, max_points=260):
        if df is None or df.empty:
            return []
        step = max(1, len(df) // max_points)
        sliced = df.iloc[::step].tail(max_points)
        return [
            {
                "t": str(idx.date()),
                "o": round(float(r["Open"]), 2),
                "h": round(float(r["High"]), 2),
                "l": round(float(r["Low"]), 2),
                "c": round(float(r["Close"]), 2),
            }
            for idx, r in sliced.iterrows()
        ]

    return {
        "yahoo_symbol": yahoo_symbol,
        "daily": rows(daily),
        "intraday": rows(intraday) if intraday is not None else [],
    }
