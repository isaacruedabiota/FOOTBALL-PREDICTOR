"use client";
import { useRef, useState } from "react";

// Gráfica de líneas SVG hecha a mano: dos series, rejilla discreta, leyenda,
// y crosshair + tooltip al pasar el ratón/dedo. Sin dependencias.

const W = 800;
const H = 340;
const L = 48; // margen izq. (etiquetas Y)
const R = 16;
const T = 16;
const B = 32; // margen inf. (etiquetas X)

function niceTicks(min, max, count) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(min / step) * step;
  const out = [];
  for (let v = start; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

function shortDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}`;
}

export default function TimelineChart({ series, format, lowerBetter }) {
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null); // {n, px, py}

  const allPts = series.flatMap((s) => s.points);
  if (allPts.length === 0) {
    return <p className="empty">Aún no hay histórico que representar.</p>;
  }

  const xMax = Math.max(...allPts.map((p) => p.n));
  const xMin = 1;
  const vals = allPts.map((p) => p.value);
  let yMin = Math.min(...vals);
  let yMax = Math.max(...vals);
  const pad = (yMax - yMin || Math.abs(yMax) || 1) * 0.15;
  yMin = Math.max(0, yMin - pad);
  yMax = yMax + pad;

  const sx = (n) => L + ((n - xMin) / (xMax - xMin || 1)) * (W - L - R);
  const sy = (v) => T + (1 - (v - yMin) / (yMax - yMin || 1)) * (H - T - B);

  const yTicks = niceTicks(yMin, yMax, 4);
  // Etiquetas X: ~5 índices repartidos, con su fecha.
  const ref = series.reduce((a, b) => (b.points.length > a.points.length ? b : a), series[0]);
  const xIdx = [];
  const steps = Math.min(5, ref.points.length);
  for (let i = 0; i < steps; i++) {
    const idx = Math.round((i / (steps - 1 || 1)) * (ref.points.length - 1));
    xIdx.push(ref.points[idx]);
  }

  function onMove(e) {
    const rect = wrapRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const ratio = (clientX - rect.left) / rect.width;
    let n = Math.round(xMin + ratio * (xMax - xMin));
    n = Math.max(xMin, Math.min(xMax, n));
    setHover({ n, px: clientX - rect.left, py: clientY - rect.top });
  }

  const hoverX = hover ? sx(hover.n) : null;

  return (
    <div className="chart-wrap" ref={wrapRef}>
      <div className="legend">
        {series.map((s) => (
          <span className="item" key={s.key}>
            <span className="line" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
        <span className="item" style={{ color: "var(--muted)" }}>
          {lowerBetter ? "menor = mejor" : "mayor = mejor"}
        </span>
      </div>

      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onTouchStart={onMove}
        onTouchMove={onMove}
        onTouchEnd={() => setHover(null)}
      >
        {/* Rejilla horizontal + etiquetas Y */}
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke="var(--grid)" strokeWidth="1" />
            <text x={L - 8} y={sy(v) + 4} textAnchor="end" fontSize="12" fill="var(--muted)">
              {format(v)}
            </text>
          </g>
        ))}
        {/* Eje X (línea base) + etiquetas */}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="var(--axis)" strokeWidth="1" />
        {xIdx.map((p, i) => (
          <text key={`x${i}`} x={sx(p.n)} y={H - B + 20} textAnchor="middle" fontSize="12" fill="var(--muted)">
            {shortDate(p.date)}
          </text>
        ))}

        {/* Crosshair */}
        {hoverX != null && (
          <line x1={hoverX} x2={hoverX} y1={T} y2={H - B} stroke="var(--axis)" strokeWidth="1" strokeDasharray="4 4" />
        )}

        {/* Series */}
        {series.map((s) => (
          <polyline
            key={s.key}
            fill="none"
            stroke={s.color}
            strokeWidth="2.4"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={s.points.map((p) => `${sx(p.n)},${sy(p.value)}`).join(" ")}
          />
        ))}

        {/* Puntos resaltados en hover */}
        {hover &&
          series.map((s) => {
            const p = s.points.find((q) => q.n === hover.n);
            if (!p) return null;
            return (
              <circle key={`h${s.key}`} cx={sx(p.n)} cy={sy(p.value)} r="4" fill={s.color}
                stroke="var(--surface)" strokeWidth="2" />
            );
          })}
      </svg>

      {hover && (
        <div className="tooltip" style={{ left: hover.px, top: hover.py }}>
          <div className="tt-date">
            {(() => {
              const p = ref.points.find((q) => q.n === hover.n);
              return p ? `Partido ${p.n} · ${shortDate(p.date)}` : `Partido ${hover.n}`;
            })()}
          </div>
          {series.map((s) => {
            const p = s.points.find((q) => q.n === hover.n);
            if (!p) return null;
            return (
              <div className="tt-row" key={`tt${s.key}`}>
                <span className="dot" style={{ background: s.color }} />
                {s.label}: <b>{format(p.value)}</b>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
