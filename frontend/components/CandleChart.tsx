"use client";

import { Candle } from "@/lib/api";

export interface Forecast {
  verdict: "BUY" | "SELL" | "HOLD";
  entry: number;
  stop: number;
  target: number;
  targetBandLow: number;
  targetBandHigh: number;
  exitBy: string;
}

interface Props {
  daily: Candle[];
  intraday: Candle[];
  forecast?: Forecast;
}

const W = 780;
const H = 300;
const PAD_L = 8;
const PAD_R = 56;
const PAD_T = 12;
const PAD_B = 24;
const FUTURE_W = 110; // forecast cone width on the right

function scale(v: number, min: number, max: number, y0: number, y1: number) {
  if (max === min) return (y0 + y1) / 2;
  return y1 - ((v - min) / (max - min)) * (y1 - y0);
}

export default function CandleChart({ daily, intraday, forecast }: Props) {
  const candles = daily.slice(-130);
  if (candles.length < 2) {
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-500">
        No chart data
      </div>
    );
  }

  // Price domain includes the forecast levels so cone + level lines fit.
  let min = Math.min(...candles.map((c) => c.l));
  let max = Math.max(...candles.map((c) => c.h));
  if (forecast) {
    min = Math.min(min, forecast.stop, forecast.targetBandLow, forecast.entry);
    max = Math.max(max, forecast.stop, forecast.targetBandHigh, forecast.entry);
  }
  const pad = (max - min) * 0.05;
  const lo = min - pad;
  const hi = max + pad;

  const plotW = W - PAD_L - PAD_R - FUTURE_W;
  const plotH = H - PAD_T - PAD_B;
  const step = plotW / candles.length;
  const bodyW = Math.max(2, step * 0.6);

  const y = (v: number) => scale(v, lo, hi, PAD_T, PAD_T + plotH);

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const price = hi - f * (hi - lo);
    return { price, yPos: y(price) };
  });

  const lastX = PAD_L + (candles.length - 1) * step + step / 2;
  const futX = W - PAD_R - 6;
  const lastCandle = candles[candles.length - 1];
  const lastClose = lastCandle.c;

  // Intraday overlay (same-date tail only) drawn against the same scale.
  const lastDate = intraday[intraday.length - 1]?.t;
  const intradayTail = lastDate ? intraday.filter((c) => c.t === lastDate) : [];
  const intradayPath =
    intradayTail.length > 2
      ? intradayTail
          .map(
            (c, i) =>
              `${i === 0 ? "M" : "L"}${(lastX - (intradayTail.length - 1 - i) * 3).toFixed(1)},${y(c.c).toFixed(1)}`
          )
          .join(" ")
      : null;

  const firstClose = candles[0].c;
  const rising = lastClose >= firstClose;

  const coneColor =
    forecast && forecast.target >= lastClose ? "rgba(34,197,94,0.16)" : "rgba(239,68,68,0.16)";
  const targetLineColor = forecast && forecast.target >= lastClose ? "#22c55e" : "#ef4444";

  const levelLines = forecast
    ? [
        { v: forecast.target, color: targetLineColor, label: `T ${forecast.target.toFixed(1)}` },
        { v: forecast.entry, color: "#38bdf8", label: `E ${forecast.entry.toFixed(1)}` },
        { v: forecast.stop, color: "#ef4444", label: `S ${forecast.stop.toFixed(1)}` },
      ]
    : [];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Daily candlestick chart with forecast cone"
    >
      {gridLines.map((g, i) => (
        <g key={i}>
          <line x1={PAD_L} x2={W - PAD_R} y1={g.yPos} y2={g.yPos} stroke="#1e293b" strokeWidth={1} />
          <text x={W - PAD_R + 6} y={g.yPos + 3.5} fill="#64748b" fontSize={10}>
            {g.price.toFixed(1)}
          </text>
        </g>
      ))}

      {candles.map((c, i) => {
        const cx = PAD_L + i * step + step / 2;
        const up = c.c >= c.o;
        const color = up ? "#22c55e" : "#ef4444";
        const top = y(Math.max(c.o, c.c));
        const bottom = y(Math.min(c.o, c.c));
        return (
          <g key={i}>
            <line x1={cx} x2={cx} y1={y(c.h)} y2={y(c.l)} stroke={color} strokeWidth={1} />
            <rect
              x={cx - bodyW / 2}
              y={top}
              width={bodyW}
              height={Math.max(1, bottom - top)}
              fill={color}
              rx={0.5}
            />
          </g>
        );
      })}

      {intradayPath && (
        <path
          d={intradayPath}
          fill="none"
          stroke="#38bdf8"
          strokeWidth={1.5}
          strokeDasharray="3 2"
        />
      )}

      {forecast && (
        <g>
          {/* cone: expected range at the horizon */}
          <polygon
            points={`${lastX},${y(lastClose)} ${futX},${y(forecast.targetBandHigh)} ${futX},${y(forecast.targetBandLow)}`}
            fill={coneColor}
          />
          <line
            x1={lastX}
            x2={futX}
            y1={y(lastClose)}
            y2={y(forecast.target)}
            stroke={targetLineColor}
            strokeWidth={1.5}
            strokeDasharray="5 3"
          />
          <text x={futX - 4} y={y(forecast.targetBandHigh) - 4} fill="#64748b" fontSize={9} textAnchor="end">
            expected by {forecast.exitBy}
          </text>

          {/* planned levels */}
          {levelLines.map((l) => (
            <g key={l.label}>
              <line
                x1={PAD_L}
                x2={futX}
                y1={y(l.v)}
                y2={y(l.v)}
                stroke={l.color}
                strokeWidth={1}
                strokeDasharray="2 4"
                opacity={0.7}
              />
              <text
                x={PAD_L + 4}
                y={y(l.v) - 3}
                fill={l.color}
                fontSize={9}
                opacity={0.9}
              >
                {l.label}
              </text>
            </g>
          ))}
        </g>
      )}

      <text x={PAD_L + 4} y={PAD_T - 2} fill={rising ? "#22c55e" : "#ef4444"} fontSize={10}>
        {rising ? "▲" : "▼"} {(((lastClose / firstClose) - 1) * 100).toFixed(1)}% over shown period
        {forecast ? (forecast.verdict === "SELL" ? " · predicted: ▼" : " · predicted: ▲") : ""}
      </text>
      <text x={PAD_L + 4} y={H - 6} fill="#64748b" fontSize={10}>
        {candles[0].t} → {lastCandle.t} · last close {lastClose.toFixed(2)}
      </text>
      {intradayPath && (
        <text x={W - PAD_R - 160} y={H - 6} fill="#38bdf8" fontSize={10}>
          – – – recent intraday
        </text>
      )}
    </svg>
  );
}
