"use client";
import { useEffect, useState } from "react";
import TimelineChart from "./TimelineChart";

const PICK_LABEL = { H: "1", D: "X", A: "2" };

// Las 5 grandes ligas, con su logo (bundleado en /public/leagues).
const LEAGUES = {
  PD: { name: "LaLiga", logo: "/leagues/PD.png" },
  PL: { name: "Premier League", logo: "/leagues/PL.png" },
  SA: { name: "Serie A", logo: "/leagues/SA.png" },
  BL1: { name: "Bundesliga", logo: "/leagues/BL1.png" },
  FL1: { name: "Ligue 1", logo: "/leagues/FL1.png" },
};

const THEMES = ["system", "light", "dark"];
const THEME_ICON = { system: "🖥️", light: "☀️", dark: "🌙" };

const pct = (x, d = 1) => (x == null ? "—" : `${x.toFixed(d)}%`);
const num = (x, d = 3) => (x == null ? "—" : x.toFixed(d));

function fdate(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  return dt.toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}
function fdatetime(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  return dt.toLocaleString("es-ES", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}
function team(n) {
  return n && n.length > 20 ? n.slice(0, 19) + "…" : n;
}
function fmatchdate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-ES", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}
const hideImg = (e) => { e.currentTarget.style.display = "none"; };

function Delta({ value, goodWhenNegative, unit }) {
  if (value == null || Number.isNaN(value)) return null;
  const good = goodWhenNegative ? value < 0 : value > 0;
  if (Math.abs(value) < 1e-9) {
    return <span className="delta" style={{ color: "var(--muted)" }}>=</span>;
  }
  const arrow = value > 0 ? "▲" : "▼";
  const shown = Math.abs(value);
  return (
    <span className={`delta ${good ? "good" : "bad"}`}>
      <span className="arrow">{arrow}</span>
      {unit === "pp" ? `${shown.toFixed(1)} pp` : shown.toFixed(3)} vs Elo
    </span>
  );
}

export default function Page() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [metric, setMetric] = useState("rps");
  const [theme, setTheme] = useState("system");

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    if (stored && THEMES.includes(stored)) {
      setTheme(stored);
      if (stored !== "system") document.documentElement.setAttribute("data-theme", stored);
    }
  }, []);

  useEffect(() => {
    fetch("/data.json", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { setData(d); setStatus("ok"); })
      .catch(() => setStatus("error"));
  }, []);

  function cycleTheme() {
    const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    setTheme(next);
    localStorage.setItem("theme", next);
    if (next === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", next);
  }

  return (
    <main className="container">
      <header className="header">
        <div className="brand">
          <img src="/icon-192.png" alt="" />
          <div>
            <h1>Footy Predictor</h1>
            <p>Predicciones y aciertos del modelo · temporada en curso</p>
          </div>
        </div>
        <div className="header-right">
          {data?.demo && <span className="badge-demo">datos de ejemplo</span>}
          {data?.generated_at && (
            <div className="meta">Actualizado<br />{fdatetime(data.generated_at)}</div>
          )}
          <button className="btn" onClick={cycleTheme} title="Tema" aria-label="Cambiar tema">
            {THEME_ICON[theme]}
          </button>
        </div>
      </header>

      {status === "loading" && <p className="empty">Cargando…</p>}
      {status === "error" && (
        <div className="info-banner">
          No se pudo cargar <code>data.json</code>. Genera los datos con{" "}
          <code>python -m footy webdata</code> y vuelve a intentarlo.
        </div>
      )}

      {status === "ok" && data && <Dashboard data={data} metric={metric} setMetric={setMetric} />}

      <footer className="meta" style={{ textAlign: "left", marginTop: 40 }}>
        Dixon-Coles vs baseline Elo · Métricas: acierto 1X2/O·U/marcador, Brier, LogLoss y RPS
        (menor = mejor). RPS ~0.19 es un modelo decente; las casas rondan 0.18.
      </footer>
    </main>
  );
}

function Dashboard({ data, metric, setMetric }) {
  const main = data.main_model;
  const base = data.baseline_model;
  const labels = data.labels || {};
  const sMain = data.summary?.[main] || null;
  const sBase = data.summary?.[base] || null;
  const counts = data.counts || { predictions: 0, evaluated: 0, pending: 0 };

  const [comp, setComp] = useState("ALL");
  const byComp = (arr) =>
    comp === "ALL" ? arr || [] : (arr || []).filter((m) => m.competition === comp);
  const upFiltered = byComp(data.upcoming);
  const recFiltered = byComp(data.recent);
  const compName = comp === "ALL" ? "" : ` · ${LEAGUES[comp]?.name || comp}`;

  return (
    <>
      {sMain ? (
        <section className="card">
          <div className="kpis">
            <div className="kpi">
              <span className="label">Acierto 1X2</span>
              <span className="value">{pct(sMain.acc_1x2)}</span>
              {sBase && <Delta value={sMain.acc_1x2 - sBase.acc_1x2} unit="pp" />}
            </div>
            <div className="kpi">
              <span className="label">RPS</span>
              <span className="value">{num(sMain.rps)}</span>
              {sBase && <Delta value={sMain.rps - sBase.rps} goodWhenNegative />}
            </div>
            <div className="kpi">
              <span className="label">Acierto O/U 2.5</span>
              <span className="value">{pct(sMain.acc_ou)}</span>
              <span className="foot">Marcador exacto: {pct(sMain.acc_score)}</span>
            </div>
            <div className="kpi">
              <span className="label">Predicciones</span>
              <span className="value">{counts.predictions}</span>
              <span className="foot">{counts.evaluated} evaluadas · {counts.pending} pendientes</span>
            </div>
          </div>
        </section>
      ) : (
        <section className="info-banner">
          Aún no hay predicciones evaluadas.{" "}
          {counts.predictions > 0
            ? `Ya hay ${counts.predictions} predicciones registradas para los próximos partidos; las métricas aparecerán en cuanto se jueguen.`
            : "La temporada aún no ha empezado o no se han generado predicciones."}
        </section>
      )}

      {sMain && sBase && (
        <section className="section card">
          <h2>Comparación de modelos</h2>
          <p className="sub">¿Aporta valor el modelo elaborado frente a un Elo simple? ({sMain.n} partidos)</p>
          <CompareTable sMain={sMain} sBase={sBase} labels={labels} main={main} base={base} />
        </section>
      )}

      {data.timeline?.[main]?.length > 0 && (
        <section className="section card">
          <h2>Evolución durante la temporada</h2>
          <p className="sub">Métrica acumulada partido a partido.</p>
          <div className="legend" style={{ marginBottom: 12 }}>
            <button className={`btn ${metric === "rps" ? "active" : ""}`} onClick={() => setMetric("rps")}>RPS</button>
            <button className={`btn ${metric === "acc" ? "active" : ""}`} onClick={() => setMetric("acc")}>Acierto 1X2</button>
          </div>
          <TimelineChart
            series={[
              {
                key: main, label: labels[main] || main, color: "var(--series-1)",
                points: data.timeline[main].map((p) => ({ n: p.n, date: p.date, value: metric === "rps" ? p.rps : p.acc_1x2 })),
              },
              {
                key: base, label: labels[base] || base, color: "var(--series-2)",
                points: (data.timeline[base] || []).map((p) => ({ n: p.n, date: p.date, value: metric === "rps" ? p.rps : p.acc_1x2 })),
              },
            ]}
            format={metric === "rps" ? (v) => v.toFixed(3) : (v) => `${v.toFixed(0)}%`}
            lowerBetter={metric === "rps"}
          />
        </section>
      )}

      <section className="section">
        <FilterBar comp={comp} setComp={setComp} />
      </section>

      <div className="grid2" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>Próximos partidos</h2>
          <p className="sub">{upFiltered.length} sin jugar{compName}.</p>
          {upFiltered.length ? (
            <div className="scrolllist">
              {upFiltered.map((m, i) => <UpcomingMatch key={i} m={m} />)}
            </div>
          ) : (
            <p className="empty">No hay próximos partidos{comp !== "ALL" ? " en esta liga" : ""} por ahora.</p>
          )}
        </section>

        <section className="card">
          <h2>Resultados recientes</h2>
          <p className="sub">Últimas predicciones ya evaluadas{compName}.</p>
          {recFiltered.length ? <RecentTable rows={recFiltered} /> : (
            <p className="empty">Aún no hay resultados evaluados{comp !== "ALL" ? " en esta liga" : ""}.</p>
          )}
        </section>
      </div>
    </>
  );
}

function FilterBar({ comp, setComp }) {
  const Btn = ({ code, label, logo }) => (
    <button
      className={`fbtn ${comp === code ? "active" : ""}`}
      onClick={() => setComp(code)}
      aria-pressed={comp === code}
    >
      {logo ? <img src={logo} alt="" /> : <span className="fall">Todas</span>}
      {logo && <span>{label}</span>}
    </button>
  );
  return (
    <div className="filterbar" role="group" aria-label="Filtrar por liga">
      <Btn code="ALL" label="Todas" logo={null} />
      {Object.entries(LEAGUES).map(([code, m]) => (
        <Btn key={code} code={code} label={m.name} logo={m.logo} />
      ))}
    </div>
  );
}

function CompareTable({ sMain, sBase, labels, main, base }) {
  const rows = [
    { k: "acc_1x2", label: "Acierto 1X2", fmt: (v) => pct(v), lower: false },
    { k: "acc_ou", label: "Acierto O/U 2.5", fmt: (v) => pct(v), lower: false },
    { k: "acc_score", label: "Marcador exacto", fmt: (v) => pct(v), lower: false },
    { k: "brier", label: "Brier", fmt: (v) => num(v), lower: true },
    { k: "logloss", label: "LogLoss", fmt: (v) => num(v), lower: true },
    { k: "rps", label: "RPS", fmt: (v) => num(v), lower: true },
  ];
  return (
    <table className="compare">
      <thead>
        <tr>
          <th>Métrica</th>
          <th><span className="swatch" style={{ background: "var(--series-1)" }} />{labels[main] || main}</th>
          <th><span className="swatch" style={{ background: "var(--series-2)" }} />{labels[base] || base}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const a = sMain[r.k], b = sBase[r.k];
          const mainWins = r.lower ? a < b : a > b;
          return (
            <tr key={r.k}>
              <td>{r.label}</td>
              <td className={mainWins ? "winner" : ""}>{r.fmt(a)}</td>
              <td className={!mainWins ? "winner" : ""}>{r.fmt(b)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function TeamCol({ name, crest }) {
  return (
    <div className="teamcol">
      {crest ? (
        <img className="crest" src={crest} alt="" loading="lazy" onError={hideImg} />
      ) : (
        <div className="crest crest-ph" aria-hidden="true" />
      )}
      <span className="tname">{name}</span>
    </div>
  );
}

function UpcomingMatch({ m }) {
  const H = (m.p_home * 100).toFixed(0);
  const D = (m.p_draw * 100).toFixed(0);
  const A = (m.p_away * 100).toFixed(0);
  return (
    <div className="match">
      <div className="mhead">
        <span className="comp-badge">
          {LEAGUES[m.competition]?.logo && (
            <img className="league-mini" src={LEAGUES[m.competition].logo} alt="" />
          )}
          {LEAGUES[m.competition]?.name || m.competition}
        </span>
        <span className="date">{fmatchdate(m.utc_date)}</span>
      </div>
      <div className="teamsrow">
        <TeamCol name={m.home_team} crest={m.home_crest} />
        <span className="vs">vs</span>
        <TeamCol name={m.away_team} crest={m.away_crest} />
      </div>
      <div className="probbar">
        <span className="h" style={{ width: `${H}%` }} />
        <span className="d" style={{ width: `${D}%` }} />
        <span className="a" style={{ width: `${A}%` }} />
      </div>
      <div className="problabels">
        <span>1 · {H}%</span>
        <span>X · {D}%</span>
        <span>2 · {A}%</span>
      </div>
      <div className="extra">
        <span>Pronóstico: <span className={`pick ${m.pick_1x2}`}>{PICK_LABEL[m.pick_1x2]}</span></span>
        <span>+2.5 goles: {(m.p_over25 * 100).toFixed(0)}%</span>
        <span>Marcador: {m.pred_home_goals}-{m.pred_away_goals}</span>
      </div>
    </div>
  );
}

function RecentTable({ rows }) {
  return (
    <div className="scrolllist">
      <table className="recent">
        <thead>
          <tr><th>Fecha</th><th>Partido</th><th>Pred.</th><th>Result.</th><th>1X2</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="date">{fdate(r.utc_date)}</td>
              <td>
                <span className="rteam">
                  {r.home_crest && <img className="crest-sm" src={r.home_crest} alt="" onError={hideImg} />}
                  {team(r.home_team)}
                </span>
                <span className="rdash"> – </span>
                <span className="rteam">
                  {r.away_crest && <img className="crest-sm" src={r.away_crest} alt="" onError={hideImg} />}
                  {team(r.away_team)}
                </span>
              </td>
              <td><span className={`pick ${r.pick_1x2}`}>{PICK_LABEL[r.pick_1x2]}</span></td>
              <td>{r.home_goals}-{r.away_goals}</td>
              <td>
                <span className={`result ${r.correct_1x2 ? "ok" : "no"}`}>
                  {r.correct_1x2 ? "✓" : "✗"} {PICK_LABEL[r.actual_1x2]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
