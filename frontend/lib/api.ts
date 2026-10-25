export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface Candle {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface HistoryResponse {
  yahoo_symbol: string;
  daily: Candle[];
  intraday: Candle[];
}

export interface CheckResult {
  mode: "check";
  as_of: string;
  as_of_close: number;
  horizon_trading_days: number;
  evaluated_through: string;
  direction: { predicted: "UP" | "DOWN"; actual: "UP" | "DOWN"; correct: boolean };
  move: { predicted_pct: number; actual_pct: number; error_pct: number };
  plan: {
    entry: number;
    stop: number;
    target: number;
    outcome: "TARGET_HIT" | "STOPPED_OUT" | "NO_TOUCH";
    detail: string;
  };
}

export interface AnalysisResponse {
  symbol: string;
  exchange: string;
  yahoo_symbol: string;
  company: string;
  sector: string;
  horizon: "swing" | "positional";
  horizon_label: string;
  mode?: "real" | "check";
  check?: CheckResult | null;
  prediction: {
    verdict: "BUY" | "SELL" | "HOLD";
    prob_up: number;
    expected_move_pct: number;
    move_band_pct: number;
    confidence: number;
    model_agreement: number;
    per_model: Record<string, number>;
    backtest: { accuracy: number; mae_pct: number; folds: number };
    feature_importance: { feature: string; weight: number }[];
  };
  timing: {
    currency: string;
    current_price: number;
    entry_price: number;
    stop_loss: number;
    target: number;
    target_band_low: number;
    target_band_high: number;
    expected_holding_trading_days: number;
    approx_exit_by: string;
    entry_hint: string;
    intraday_note: string;
    indicators: {
      rsi_14: number;
      price_vs_sma20_pct: number;
      price_vs_sma50_pct: number;
      atr_14: number;
    };
  };
  llm: {
    available: boolean;
    reason?: string;
    final_verdict?: string;
    tally?: Record<string, number>;
    models_used?: string[];
    analyses?: {
      model: string;
      verdict: string;
      thesis: string;
      risks: string;
      timing_note: string;
    }[];
  };
  disclaimer: string;
}

export async function fetchHistory(symbol: string, exchange: string) {
  const res = await fetch(
    `${API_BASE}/api/history?symbol=${encodeURIComponent(symbol)}&exchange=${encodeURIComponent(exchange)}`
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `History request failed (${res.status})`);
  }
  return res.json() as Promise<HistoryResponse>;
}

export async function fetchAnalysis(
  symbol: string,
  exchange: string,
  horizon: "swing" | "positional",
  mode: "real" | "check" = "real",
  asOf?: string
) {
  const res = await fetch(`${API_BASE}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, exchange, horizon, mode, as_of: asOf || null }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `Analysis failed (${res.status})`);
  }
  return res.json() as Promise<AnalysisResponse>;
}
