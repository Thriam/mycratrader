"""Prediction engine: several algorithms, walk-forward evaluation, ensemble.

Direction models (classification, "will the price be higher in H days?"):
  - LogisticRegression
  - RandomForestClassifier
  - GradientBoostingClassifier

Magnitude models (regression, "by how much?"):
  - OLS linear regression (statsmodels)
  - RidgeCV
  - GradientBoostingRegressor

The ensemble combines classifier probabilities for direction and regressor
medians for the expected move. Walk-forward evaluation on recent history gives
honest out-of-sample accuracy numbers instead of in-sample overfit ones.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

from .features import build_features, FEATURE_NAMES


@dataclass
class PredictionResult:
    prob_up: float                      # ensemble probability price is higher after horizon
    expected_move_pct: float            # ensemble expected forward return (fraction)
    move_band_pct: float                # +/- band around expected move (fraction)
    verdict: str                        # BUY / SELL / HOLD
    confidence: float                   # 0..1
    model_agreement: float              # fraction of direction models agreeing
    backtest: Dict[str, float] = field(default_factory=dict)
    per_model: Dict[str, float] = field(default_factory=dict)
    feature_importance: List[Dict[str, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def make_dataset(df: pd.DataFrame, horizon: int):
    X = build_features(df)
    fwd_ret = df["Close"].shift(-horizon) / df["Close"] - 1.0
    y_clf = (fwd_ret > 0).astype(int)
    y_reg = fwd_ret.fillna(0.0)

    aligned = pd.concat([X, y_clf.rename("y_clf"), y_reg.rename("y_reg")], axis=1).dropna()
    return aligned[FEATURE_NAMES], aligned["y_clf"].astype(int), aligned["y_reg"]


def _fit_direction_models(X_tr, y_tr):
    models = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=25,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
        "grad_boost": GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42,
        ),
    }
    for m in models.values():
        m.fit(X_tr, y_tr)
    return models


def _fit_magnitude_models(X_tr, y_tr):
    models = {
        "ols": sm.OLS(y_tr, sm.add_constant(X_tr, has_constant="add")).fit(),
        "ridge": make_pipeline(StandardScaler(), RidgeCV(alphas=(0.01, 0.1, 1.0, 10.0))),
        "grad_boost_reg": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42,
        ),
    }
    for name, m in models.items():
        if name != "ols":
            m.fit(X_tr, y_tr)
    return models


def _direction_probs(models, X) -> Dict[str, float]:
    out = {}
    for name, m in models.items():
        out[name] = float(m.predict_proba(X.iloc[[-1]])[0, 1])
    return out


def _magnitude_preds(models, X) -> Dict[str, float]:
    row = X.iloc[[-1]]
    ols_design = sm.add_constant(row, has_constant="add")
    ols_pred = np.asarray(models["ols"].predict(ols_design)).ravel()[0]
    return {
        "ols": float(ols_pred),
        "ridge": float(models["ridge"].predict(row)[0]),
        "grad_boost_reg": float(models["grad_boost_reg"].predict(row)[0]),
    }


def _feature_importance(direction_models) -> List[Dict[str, float]]:
    importances: Dict[str, float] = {}
    for name in ("random_forest", "grad_boost"):
        imp = getattr(direction_models[name], "feature_importances_", None)
        if imp is None:
            continue
        for fname, value in zip(FEATURE_NAMES, imp):
            importances[fname] = importances.get(fname, 0.0) + float(value)
    total = sum(importances.values()) or 1.0
    ranked = sorted(
        ((k, v / total) for k, v in importances.items()),
        key=lambda kv: kv[1], reverse=True,
    )
    return [{"feature": k, "weight": round(v, 4)} for k, v in ranked[:8]]


# ---------------------------------------------------------------------------
# Walk-forward evaluation
# ---------------------------------------------------------------------------

def walk_forward_evaluate(X, y_clf, y_reg, horizon: int, folds: int = 5) -> Dict[str, float]:
    """Rolling-origin evaluation on the most recent slice of history.

    For each fold we train on everything before the fold's test window and
    score direction accuracy / magnitude error on the window itself. This
    mimics how the model would have performed if run live, fold by fold.
    """
    n = len(X)
    if n < 600:
        return {"accuracy": 0.5, "mae_pct": 0.0, "folds": 0} # not enough history

    test_size = 60
    test_span = folds * test_size
    start = n - test_span
    if start < 200:
        return {"accuracy": 0.5, "mae_pct": 0.0, "folds": 0}

    accs, maes = [], []
    for f in range(folds):
        tr_end = start + f * test_size
        te_end = tr_end + test_size
        X_tr, y_tr = X.iloc[:tr_end], y_clf.iloc[:tr_end]
        X_te, y_te_true = X.iloc[tr_end:te_end], y_clf.iloc[tr_end:te_end]
        y_reg_true = y_reg.iloc[tr_end:te_end]

        if y_tr.nunique() < 2:
            continue
        dir_models = _fit_direction_models(X_tr, y_tr)

        # Predict each test day with only data before it available is
        # approximated here by fitting once up to tr_end (standard practice).
        probs = {}
        for name, m in dir_models.items():
            probs[name] = m.predict_proba(X_te)[:, 1]
        ens = np.mean(np.vstack(list(probs.values())), axis=0)
        accs.append(float(((ens > 0.5) == (y_te_true == 1)).mean()))

        reg_models = _fit_magnitude_models(X_tr, y_reg.iloc[:tr_end])
        row = X_te
        ols_pred = np.asarray(reg_models["ols"].predict(
            sm.add_constant(row, has_constant="add")
        )).ravel()
        preds = np.vstack([
            ols_pred,
            np.asarray(reg_models["ridge"].predict(row)).ravel(),
            np.asarray(reg_models["grad_boost_reg"].predict(row)).ravel(),
        ])
        med = np.median(preds, axis=0)
        maes.append(float(np.abs(med - y_reg_true.values).mean()))

    if not accs:
        return {"accuracy": 0.5, "mae_pct": 0.0, "folds": 0}
    return {"accuracy": float(np.mean(accs)), "mae_pct": float(np.mean(maes)), "folds": len(accs)}


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------

def predict(df: pd.DataFrame, horizon: int) -> PredictionResult:
    X, y_clf, y_reg = make_dataset(df, horizon)

    cutoff = int(len(X) * 0.8)
    X_tr, X_te = X.iloc[:cutoff], X.iloc[cutoff:]

    dir_models = _fit_direction_models(X_tr, y_clf.iloc[:cutoff])
    reg_models = _fit_magnitude_models(X_tr, y_reg.iloc[:cutoff])

    probs = _direction_probs(dir_models, X)
    values = list(probs.values())
    prob_up = float(np.mean(values))
    agreement = float(max(
        sum(1 for p in values if p > 0.5),
        sum(1 for p in values if p <= 0.5),
    ) / len(values))

    mag = _magnitude_preds(reg_models, X)
    move = float(np.median(list(mag.values())))
    band = move + float(np.std(list(mag.values())))
    band = 0.03 if band <= 0 else band

    # Recalibrate expected move against out-of-sample MAE (models overfit).
    backtest = walk_forward_evaluate(X, y_clf, y_reg, horizon)
    mae_shrink = max(0.35, 1.0 - backtest["mae_pct"] * 14)
    move_shrunk = move * mae_shrink

    max_prob = max(max(values), 1.0 - min(values))
    edge = abs(prob_up - 0.5) / 0.5
    confidence = float(np.clip(
        0.55 * edge + 0.35 * (backtest["accuracy"] - 0.5) * 2 + 0.10 * agreement,
        0.05, 0.95,
    )) if backtest["folds"] else float(np.clip(0.55 * edge + 0.10 * agreement, 0.05, 0.8))

    verdict = "HOLD"
    if prob_up > 0.58:
        verdict = "BUY"
    elif prob_up < 0.42:
        verdict = "SELL"

    return PredictionResult(
        prob_up=prob_up,
        expected_move_pct=move_shrunk,
        move_band_pct=band,
        verdict=verdict,
        confidence=confidence,
        model_agreement=agreement,
        backtest=backtest,
        per_model={"direction_" + k: round(v, 4) for k, v in probs.items()},
        feature_importance=_feature_importance(dir_models),
    )
