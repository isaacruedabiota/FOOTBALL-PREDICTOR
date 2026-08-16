# ⚽ Footy Predictor

Modelo predictivo de fútbol que, durante una temporada, **registra cada predicción
que hace y luego mide cuántas acierta**. Usa el modelo **Dixon-Coles** (Poisson con
corrección de marcadores bajos y ponderación temporal): de un único ajuste salen las
tres predicciones a la vez —**1X2**, **más/menos 2.5 goles** y **marcador exacto**—
porque todas se derivan de la distribución de goles esperados de cada equipo.

El registro es **honesto**: para cada partido se guarda una sola predicción, la que se
hace *antes* de jugarse, y nunca se reescribe. Cuando el partido termina, se compara con
el resultado real y se guardan las métricas.

---

## 1. Instalación

```powershell
cd c:\Users\isaac\Documents\FP
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Conseguir la API key (gratis)

1. Regístrate en <https://www.football-data.org/client/register>.
2. Copia el fichero `.env.example` a `.env`.
3. Pega tu clave en `FOOTBALL_DATA_API_KEY`.

```powershell
Copy-Item .env.example .env
notepad .env
```

## 3. Configurar qué seguir

Edita [config.yaml](config.yaml): competiciones (`PD` LaLiga, `PL` Premier, `SA` Serie A…)
y `season` (año de inicio; 2026/27 → `2026`).

Dos opciones clave ya ajustadas:
- `history_seasons: 1` — descarga también la temporada anterior, para poder predecir
  **desde la jornada 1** (si no, habría que esperar a jugar ~30 partidos).
- `predict_horizon_days: 10` — solo predice los partidos de los próximos 10 días, para no
  "congelar" toda la temporada de golpe. Cada día que corre, predice la jornada inminente
  con los datos más frescos.

## 4. Uso

```powershell
python -m footy init-db     # crea la base de datos (data/footy.db)
python -m footy fetch       # descarga partidos jugados y futuros
python -m footy predict     # entrena y registra predicciones (modelo + baseline Elo)
python -m footy evaluate    # evalúa las predicciones cuyos partidos ya terminaron
python -m footy report      # muestra el histórico de aciertos y compara modelos
python -m footy export      # vuelca el histórico a track_record/track_record.csv
```

O todo el ciclo de golpe (lo que conviene automatizar):

```powershell
python -m footy run         # fetch -> predict -> evaluate -> export -> report
```

Cada partido se predice con **dos** modelos: el principal (Dixon-Coles) y un
**baseline Elo**. El informe los compara: si el RPS de Dixon-Coles no es menor que
el del Elo, el modelo elaborado no está aportando valor.

### Probar sin API key (datos sintéticos)

Genera una liga ficticia con equipos de fuerza conocida y recorre todo el flujo:

```powershell
python scripts\seed_synthetic.py            # siembra la liga (usa config.yaml)
python -m footy predict
python scripts\seed_synthetic.py --reveal   # "pasa el tiempo": revela resultados
python -m footy evaluate
python -m footy report
```

> Para que `predict` toque la liga sintética, añade `SYN` a `competitions` en tu config,
> o usa una config aparte con `-c mi_config.yaml`.

## 5. Automatizar durante el año (Programador de tareas de Windows)

El script [scripts/run_scheduled.py](scripts/run_scheduled.py) ejecuta el ciclo completo
y deja un log en `logs/`. Para lanzarlo **todos los días a las 9:00**:

```powershell
$py     = "c:\Users\isaac\Documents\FP\.venv\Scripts\python.exe"
$script = "c:\Users\isaac\Documents\FP\scripts\run_scheduled.py"
$accion = New-ScheduledTaskAction -Execute $py -Argument $script -WorkingDirectory "c:\Users\isaac\Documents\FP"
$disparador = New-ScheduledTaskTrigger -Daily -At 9:00am
Register-ScheduledTask -TaskName "FootyPredictor" -Action $accion -Trigger $disparador -Description "Predicciones diarias de fútbol"
```

Comprobar / quitar la tarea:

```powershell
Get-ScheduledTask -TaskName "FootyPredictor"                       # ver estado
Start-ScheduledTask -TaskName "FootyPredictor"                     # ejecutar ya
Unregister-ScheduledTask -TaskName "FootyPredictor" -Confirm:$false # eliminar
```

Ejecutar a diario es idempotente: cada partido se predice una sola vez (cuando entra en el
horizonte de `predict_horizon_days`), `fetch` trae los resultados que se van jugando y
`evaluate` los puntúa en cuanto terminan. No pasa nada si un día no se ejecuta.

## 6. Cómo se mide el acierto

| Métrica | Qué es | Bueno |
|---|---|---|
| **Acierto 1X2** | ¿acertó local/empate/visitante más probable? | > 45 % (baseline "siempre local") |
| **Acierto O/U** | ¿acertó más/menos de 2.5 goles? | > 50 % |
| **Marcador** | ¿acertó el resultado exacto? | ~ 8–12 % ya es notable |
| **Brier** | error cuadrático de las probabilidades | menor = mejor |
| **LogLoss** | penaliza estar seguro y fallar | menor = mejor |
| **RPS** | Ranked Probability Score (estándar en fútbol) | ~0.19 bueno; casas ~0.18 |

El acierto simple (%) engaña: un modelo puede "acertar" mucho siendo trivial. Por eso se
guardan también Brier, LogLoss y RPS, que puntúan la **calibración** de las probabilidades.

**Baseline Elo.** Para saber si el modelo aporta valor de verdad, cada partido se predice
también con un Elo simple ([footy/baseline.py](footy/baseline.py)). El informe compara ambos:
el objetivo es que Dixon-Coles tenga un RPS menor que el del baseline.

## Track record versionado (git)

La base de datos SQLite (`data/`) **no** se versiona: es binaria y no se puede leer en un
diff. En su lugar, `python -m footy export` (incluido en `run`) genera
`track_record/track_record.csv`, que sí se versiona y se abre en Excel. Así, cada commit
guarda una foto del histórico de predicciones y aciertos a lo largo del año.

## Web / App (PWA)

En [web/](web/) hay un panel **Next.js** (instalable en el móvil como app) para visualizar
todo: KPIs, comparación Dixon-Coles vs Elo, evolución del acierto durante la temporada,
próximos partidos y resultados recientes. Lee el fichero `web/public/data.json` que genera
`python -m footy webdata` (incluido en `run`). Instrucciones completas en
[web/README.md](web/README.md).

### Publicar en GitHub + Vercel (gratis)

```powershell
# 1) Crea un repo vacío en https://github.com/new  (p. ej. "footy-predictor")
# 2) Conéctalo y sube todo:
cd c:\Users\isaac\Documents\FP
git remote add origin https://github.com/TU_USUARIO/footy-predictor.git
git push -u origin main
# 3) En https://vercel.com importa el repo y pon Root Directory = "web".
```

Con el remoto configurado, la tarea diaria (`scripts/run_scheduled.py`) hace `commit` +
`push` de los datos automáticamente, y Vercel redespliega la web sola.

## 7. Estructura

```
footy/
  config.py     Carga de config.yaml + .env
  db.py         Esquema SQLite y accesos
  ingest.py     Cliente de football-data.org
  model.py      Modelo Dixon-Coles (ajuste + matriz de marcadores)
  baseline.py   Baseline Elo de referencia
  predict.py    Deriva 1X2 / O/U / marcador y los registra (modelo + baseline)
  metrics.py    Brier, LogLoss, RPS, aciertos
  evaluate.py   Compara predicción vs resultado real
  report.py     Informe y comparación de modelos
  export.py     Exporta el histórico a CSV versionable
  cli.py        Línea de comandos
scripts/
  seed_synthetic.py   Liga de prueba sin API
  run_scheduled.py    Entrada para el Programador de tareas
tests/          Tests (pytest)
```

## 8. Tests

```powershell
pytest -q
```

## 9. Ideas para mejorar el modelo

- Comparar el RPS contra un baseline (Elo, o las cuotas de las casas) para saber si
  aportas valor real.
- Añadir más señales: descanso entre partidos, lesiones, xG en vez de goles.
- Registrar varias versiones del modelo (`MODEL_VERSION`) y compararlas en el mismo periodo.
