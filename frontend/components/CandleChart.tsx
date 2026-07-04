"use client";

import { Candle } from "@/lib/api";

interface Props {
  daily: Candle[];
  intraday: Candle[];
}

const W = 720;
const H = 300;
const PAD_L = 8;
const PAD_R = 56;
const PAD_T = 12;
const PAD_B = 24;

function scale(v: number, min: number, max: number, y0: number, y1: number) {
  if (max === min) return (y0 + y1) / 2;
  return y1 - ((v - min) / (max - min)) * (y1 - y0);
}

export default function CandleChart({ daily, intraday }: Props) {
  const candles = daily.slice(-130);
  if (candles.length < 2) {
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-500">
        No chart data
      </div>
    );
  }

  const lows = candles.map((c) => c.l);
  const highs = candles.map((c) => c.h);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const pad = (max - min) * 0.05;
  const lo = min - pad;
  const hi = max + pad;

  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const step = plotW / candles.length;
  const bodyW = Math.max(2, step * 0.6);

  const y = (v: number) => scale(v, lo, hi, PAD_T, PAD_T + plotH);

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const price = hi - f * (hi - lo);
    return { price, yPos: y(price) };
  });

  // Intraday overlay (last session-ish tail) drawn on the same scale if it fits.
  const intradayTail = intraday.filter((c) => c.t === intraday[intraday.length - 1]?.t);
  const intradayPath =
    intradayTail.length > 2
      ? intradayTail
          .map(
            (c, i) =>
              `${i === 0 ? "M" : "L"}${(PAD_L + plotW - (intradayTail.length - 1 - i) * 3).toFixed(1)},${y(c.c).toFixed(1)}`
          )
          .join(" ")
      : null;

  const lastClose = candles[candles.length - 1];
  const firstClose = candles[0];
  const rising = lastClose.c >= firstClose.c;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Daily candlestick chart">
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
        <path d={intradayPath} fill="none" stroke="#38bdf8" strokeWidth={1.5} strokeDasharray="3 2" />
      )}
      <text x={PAD_L + 4} y={H - 6} fill="#64748b" fontSize={10}>
        {candles[0].t} → {lastClose.t} · last close {lastClose.c.toFixed(2)}
      </text>
      {intradayPath && (
        <text x={W - PAD_R - 160} y={H - 6} fill="#38bdf8" fontSize={10}>
          – – – recent intraday
        </text>
      )}
      <rect x={0} y={H - PAD_B} width={W} height={PAD_B} fill="#0a0e17" opacity={0} />
      <text x={PAD_L} y={PAD_T - 2} fill={rising ? "#22c55e" : "#ef4444"} fontSize={10}>
        {rising ? "▲" : "▼"} {(((lastClose.c / firstClose.c) - 1) * 100).toFixed(1)}% over shown period
      </text>
    </svg>
  );
}
