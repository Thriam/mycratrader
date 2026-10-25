"use client";

import { useCallback, useState } from "react";
import CandleChart from "@/components/CandleChart";
import { AnalysisResponse, HistoryResponse, fetchAnalysis, fetchHistory } from "@/lib/api";

interface FormState {
  symbol: string;
  exchange: "NSE" | "BSE";
  horizon: "swing" | "positional";
  mode: "real" | "check";
  asOf: string;
}

const VERDICT_STYLES: Record<string, string> = {
  BUY: "bg-green-500/15 text-green-400 border-green-500/40",
  SELL: "bg-red-500/15 text-red-400 border-red-500/40",
  HOLD: "bg-amber-500/15 text-amber-400 border-amber-500/40",
};

function defaultAsOf() {
  return new Date(Date.now() - 120 * 86400000).toISOString().slice(0, 10);
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold ${accent ?? "text-slate-100"}`}>{value}</div>
    </div>
  );
}

export default function Home() {
  const [form, setForm] = useState<FormState>({
    symbol: "RELIANCE",
    exchange: "NSE",
    horizon: "swing",
    mode: "real",
    asOf: defaultAsOf(),
  });
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (form.mode === "check" && !form.asOf) {
      setError("Pick the pretend-today date for the self-check first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [analysisRes, historyRes] = await Promise.all([
        fetchAnalysis(form.symbol, form.exchange, form.horizon, form.mode, form.asOf),
        fetchHistory(form.symbol, form.exchange),
      ]);
      setAnalysis(analysisRes);
      setHistory(historyRes);
    } catch (e) {
      setAnalysis(null);
      setHistory(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [form]);

  const p = analysis?.prediction;
  const t = analysis?.timing;
  const verdict = p?.verdict ?? "HOLD";

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">mycratrader</h1>
        <p className="mt-1 text-sm text-slate-400">
          Multi-algorithm prediction engine for NSE &amp; BSE stocks — regression + ensemble ML,
          walk-forward backtested, reviewed by free OpenRouter models.
        </p>
      </header>

      {/* Mode tabs */}
      <section className="mb-6 flex gap-2">
        {(
          [
            ["real", "Live market"],
            ["check", "Self-check"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setForm({ ...form, mode: key })}
            className={`rounded-lg border px-4 py-1.5 text-sm font-medium transition ${
              form.mode === key
                ? key === "real"
                  ? "border-sky-500/60 bg-sky-500/15 text-sky-300"
                  : "border-violet-500/60 bg-violet-500/15 text-violet-300"
                : "border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
        {form.mode === "check" && (
          <span className="ml-2 self-center text-xs text-slate-500">
            Pretends today is the date below, trains only on candles before it, then scores the call against what really happened.
          </span>
        )}
      </section>

      {/* Query form */}
      <section className="mb-10 rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <form
          className="flex flex-wrap items-end gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
        >
          <div className="flex-1 min-w-[220px]">
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Stock symbol (e.g. RELIANCE, TCS, TATAMOTORS)
            </label>
            <input
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              placeholder="RELIANCE"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-500"
            />
          </div>

          <div>
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">Exchange</span>
            <div className="flex rounded-lg border border-slate-700 bg-slate-950 p-0.5">
              {(["NSE", "BSE"] as const).map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setForm({ ...form, exchange: ex })}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                    form.exchange === ex ? "bg-sky-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">Horizon</span>
            <div className="flex rounded-lg border border-slate-700 bg-slate-950 p-0.5">
              {(
                [
                  ["swing", "Swing 2–10d"],
                  ["positional", "Positional 2–8w"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setForm({ ...form, horizon: key })}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                    form.horizon === key ? "bg-sky-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="min-w-[180px]">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              {form.mode === "check" ? "Pretend today is" : "—"}
            </span>
            <input
              type="date"
              value={form.asOf}
              disabled={form.mode === "real"}
              onChange={(e) => setForm({ ...form, asOf: e.target.value })}
              className={`w-full rounded-lg border px-3 py-2 text-slate-200 outline-none disabled:cursor-not-allowed disabled:opacity-40 ${
                form.mode === "check"
                  ? "border-slate-700 bg-slate-950 focus:border-violet-500"
                  : "border-slate-900 bg-slate-950"
              }`}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-sky-600 px-6 py-2 font-medium text-white transition hover:bg-sky-500 disabled:opacity-50"
          >
            {loading ? "Analyzing…" : form.mode === "check" ? "Run self-check" : "Predict"}
          </button>
        </form>
        {error && (
          <p className="mt-3 rounded-lg border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
      </section>

      {/* Results */}
      {analysis && p && t && (
        <div className="space-y-8">
          {/* Verdict header */}
          <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">
                  {analysis.company}{" "}
                  <span className="text-sm font-normal text-slate-400">
                    · {analysis.symbol} ({analysis.exchange}) · {analysis.horizon_label}
                    {analysis.mode === "check" && analysis.check &&
                      ` · self-check as of ${analysis.check.as_of}`}
                  </span>
                </h2>
                <div className="text-sm text-slate-500">{analysis.sector}</div>
              </div>
              <div className={`rounded-lg border px-4 py-2 text-lg font-bold ${VERDICT_STYLES[verdict]} ${analysis.llm.available && analysis.llm.final_verdict && analysis.llm.final_verdict !== verdict ? "border-dashed" : ""}`}>
                {verdict}
                {analysis.llm.available && analysis.llm.final_verdict && analysis.llm.final_verdict !== verdict && (
                  <span className="ml-2 text-xs font-medium opacity-80">LLM says {analysis.llm.final_verdict}</span>
                )}
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Metric label="Current" value={`₹${t.current_price.toLocaleString("en-IN")}`} />
              <Metric label="P(up) ensemble" value={pct(p.prob_up)} accent={p.prob_up >= 0.5 ? "text-green-400" : "text-red-400"} />
              <Metric label="Exp. move" value={`${t.currency} ${p.expected_move_pct > 0 ? "+" : ""}${p.expected_move_pct.toFixed(2)}%`} />
              <Metric label="Confidence" value={pct(p.confidence)} />
              <Metric label="Backtest acc." value={pct(p.backtest.accuracy)} accent={p.backtest.accuracy >= 0.55 ? "text-green-400" : "text-slate-100"} />
              <Metric label="Agreement" value={pct(p.model_agreement)} />
            </div>
          </section>

          {/* Self-check outcome */}
          {analysis.check && (
            <section className="rounded-xl border border-violet-900/60 bg-violet-950/20 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-violet-300">
                  Self-check: prediction vs reality
                </h3>
                {analysis.check.direction.correct && analysis.check.plan.outcome !== "STOPPED_OUT" ? (
                  <span className="rounded-lg border border-green-500/50 bg-green-500/15 px-3 py-1 text-sm font-bold text-green-400">
                    ✓ Call held up
                  </span>
                ) : (
                  <span className="rounded-lg border border-red-500/50 bg-red-500/15 px-3 py-1 text-sm font-bold text-red-400">
                    ✗ Call failed
                  </span>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Direction</div>
                  <div className="mt-1 text-sm text-slate-200">
                    predicted <span className="font-bold">{analysis.check.direction.predicted}</span>
                    {" · actual "}
                    <span className="font-bold">{analysis.check.direction.actual}</span>
                    <span className={`ml-2 text-xs ${analysis.check.direction.correct ? "text-green-400" : "text-red-400"}`}>
                      {analysis.check.direction.correct ? "correct" : "wrong"}
                    </span>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Move over horizon</div>
                  <div className="mt-1 text-sm text-slate-200">
                    predicted <span className="font-bold">{analysis.check.move.predicted_pct > 0 ? "+" : ""}{analysis.check.move.predicted_pct}%</span>
                    {" · actual "}
                    <span className="font-bold">{analysis.check.move.actual_pct > 0 ? "+" : ""}{analysis.check.move.actual_pct}%</span>
                    <span className="ml-2 text-xs text-slate-500">err {analysis.check.move.error_pct}%</span>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Trade plan replay</div>
                  <div className="mt-1 text-sm text-slate-200">{analysis.check.plan.outcome.replace("_", " ")}</div>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-300">{analysis.check.plan.detail}</p>
              <p className="mt-1 text-xs text-slate-500">
                Called on {analysis.check.as_of} (close ₹{analysis.check.as_of_close.toLocaleString("en-IN")}), evaluated
                through {analysis.check.evaluated_through} over {analysis.check.horizon_trading_days} trading days.
              </p>
            </section>
          )}

          {/* Trade timing plan */}
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Trade plan &amp; timing</h3>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-slate-500">Entry</div>
                    <div className="text-2xl font-bold text-sky-400">₹{t.entry_price.toLocaleString("en-IN")}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Stop loss</div>
                    <div className="text-2xl font-bold text-red-400">₹{t.stop_loss.toLocaleString("en-IN")}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Target</div>
                    <div className="text-2xl font-bold text-green-400">₹{t.target.toLocaleString("en-IN")}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      band ₹{t.target_band_low.toLocaleString("en-IN")} – ₹{t.target_band_high.toLocaleString("en-IN")}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Exit by (≈)</div>
                    <div className="text-2xl font-bold">{t.approx_exit_by}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {t.expected_holding_trading_days} trading days
                    </div>
                  </div>
                </div>
                <p className="mt-4 border-t border-slate-800 pt-3 text-sm text-slate-300">{t.entry_hint}</p>
                {t.intraday_note && <p className="mt-2 text-sm text-slate-400">{t.intraday_note}</p>}
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
                <h4 className="mb-3 text-sm font-semibold text-slate-300">Live indicators</h4>
                <ul className="space-y-2 text-sm text-slate-300">
                  <li>RSI(14): <span className="font-mono">{t.indicators.rsi_14}</span>{t.indicators.rsi_14 > 70 ? " · overbought" : t.indicators.rsi_14 < 30 ? " · oversold" : ""}</li>
                  <li>vs 20-SMA: <span className="font-mono">{pct(t.indicators.price_vs_sma20_pct)}</span></li>
                  <li>vs 50-SMA: <span className="font-mono">{pct(t.indicators.price_vs_sma50_pct)}</span></li>
                  <li>ATR(14): <span className="font-mono">{t.indicators.atr_14}</span></li>
                  <li>Walk-forward MAE: <span className="font-mono">{p.backtest.mae_pct.toFixed(2)}%</span> ({p.backtest.folds} folds)</li>
                </ul>
                <h4 className="mb-2 mt-5 text-sm font-semibold text-slate-300">Top model signals</h4>
                <ul className="space-y-1.5">
                  {p.feature_importance.map((f) => (
                    <li key={f.feature} className="flex items-center gap-2 text-xs">
                      <span className="w-36 shrink-0 truncate text-slate-400">{f.feature}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
                        <div
                          className="h-full rounded bg-sky-500"
                          style={{ width: `${Math.min(100, f.weight * 100)}%` }}
                        />
                      </div>
                      <span className="w-10 text-right font-mono text-slate-500">{(f.weight * 100).toFixed(1)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* Chart */}
          {history && (
            <section>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Price history (daily)</h3>
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <CandleChart
                  daily={history.daily}
                  intraday={history.intraday}
                  forecast={{
                    verdict: p.verdict,
                    entry: t.entry_price,
                    stop: t.stop_loss,
                    target: t.target,
                    targetBandLow: t.target_band_low,
                    targetBandHigh: t.target_band_high,
                    exitBy: t.approx_exit_by,
                  }}
                />
              </div>
            </section>
          )}

          {/* LLM consensus */}
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              OpenRouter free-model consensus
            </h3>
            {analysis.llm.available ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
                <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
                  <span className={`rounded border px-2 py-1 font-semibold ${VERDICT_STYLES[analysis.llm.final_verdict ?? "HOLD"]}`}>
                    {analysis.llm.final_verdict}
                  </span>
                  <span className="text-slate-500">
                    tally: {Object.entries(analysis.llm.tally ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ")}
                  </span>
                  <span className="text-xs text-slate-600">models: {analysis.llm.models_used?.join(", ")}</span>
                </div>
                <div className="space-y-4">
                  {analysis.llm.analyses?.map((a) => (
                    <div key={a.model} className="rounded-lg border border-slate-800/70 bg-slate-950/60 p-4 text-sm">
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <span className="text-xs text-slate-500">{a.model}</span>
                        <span className="text-xs font-semibold text-slate-300">{a.verdict}</span>
                      </div>
                      <p className="text-slate-300">{a.thesis}</p>
                      {a.risks && <p className="mt-1.5 text-slate-400"><span className="text-red-400">Risk:</span> {a.risks}</p>}
                      {a.timing_note && <p className="mt-1.5 text-slate-400"><span className="text-sky-400">Timing:</span> {a.timing_note}</p>}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 p-4 text-sm text-amber-300">
                Free-LLM consensus unavailable: {analysis.llm.reason}. Quant prediction above runs without it.
              </div>
            )}
          </section>

          <footer className="rounded-xl border border-slate-800 p-4 text-xs leading-relaxed text-slate-500">
            ⚠ {analysis.disclaimer}
          </footer>
        </div>
      )}

      {!analysis && !loading && (
        <p className="text-center text-sm text-slate-600">
          Enter an NSE or BSE stock symbol above and hit Predict.
        </p>
      )}
    </main>
  );
}
