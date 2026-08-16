# ⚽ Footy Predictor — Web (PWA)

Panel web para visualizar las predicciones y los aciertos del modelo. Es una
**PWA**: se ve en el navegador y se puede **instalar en el móvil** como una app
(icono, offline, pantalla completa). Hecha con **Next.js 14 + React 18**, sin
servidor propio: lee un fichero estático `public/data.json` que genera el proyecto
Python.

## Cómo fluyen los datos

```
footy run  ─►  web/public/data.json  ─►  (git push)  ─►  Vercel redepliega  ─►  PWA
(tu PC)         lo genera "footy webdata"                                       (móvil/web)
```

No hay base de datos en la nube: la web solo consume el JSON. Para actualizarlo:
`python -m footy webdata` (ya incluido en `python -m footy run`).

## Requisitos

- **Node.js 18+**. Descárgalo en <https://nodejs.org> (versión LTS).
  Comprueba: `node --version`.

## Desarrollo local

```powershell
cd c:\Users\isaac\Documents\FP\web
npm install
npm run dev
```
Abre <http://localhost:3000>. Mientras no haya datos reales, se muestra un
`data.json` de ejemplo (con la etiqueta “datos de ejemplo”).

Para verlo con tus datos reales, regenera el JSON desde la raíz del proyecto:
```powershell
cd ..
python -m footy webdata   # escribe web/public/data.json
```

## Compilar para producción

```powershell
npm run build
npm start
```

## Desplegar gratis en Vercel

1. Sube el repositorio a GitHub (ver el README principal, sección de despliegue).
2. Entra en <https://vercel.com>, **Add New → Project**, e importa el repo.
3. **IMPORTANTE:** en *Root Directory* selecciona **`web`** (la app no está en la raíz).
4. Framework: *Next.js* (se detecta solo). Pulsa **Deploy**.
5. Te da una URL pública (p. ej. `footy-predictor.vercel.app`).

A partir de ahí, cada `git push` que actualice `web/public/data.json` hace que
Vercel **redepliegue solo**. La tarea diaria (`scripts/run_scheduled.py`) hace ese
push automáticamente si el repo tiene remoto.

## Instalar como app en el móvil

Abre la URL en Chrome/Safari del móvil → menú → **“Añadir a pantalla de inicio”**
/ **“Instalar app”**. Quedará con icono propio y se abrirá a pantalla completa.

## Estructura

```
web/
  app/
    layout.js         Metadatos, manifest, tema
    page.js           Dashboard (KPIs, comparación, tablas)
    TimelineChart.js  Gráfica SVG (RPS/acierto acumulado, ambos modelos)
    RegisterSW.js     Registro del service worker
    globals.css       Estilos y paleta (claro/oscuro)
  public/
    data.json         Datos que consume la web (generado por Python)
    manifest.webmanifest, sw.js, icon-*.png
```
