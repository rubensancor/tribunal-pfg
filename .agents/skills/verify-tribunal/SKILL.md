---
name: verify-tribunal
description: Arranca una copia desechable del dashboard del Tribunal PFG (web local en Python + scripts/pfg.py), la conduce con Playwright como lo haría un docente (subir PDF, ver estados, ficha, secciones, preguntas por categoría) y guarda capturas y snapshots ARIA como prueba. Úsala para demostrar que un cambio en dashboard/, scripts/ o config/ funciona en la app real, no solo en los tests.
---

# Verificar el dashboard del Tribunal PFG

Superficie principal: el dashboard web (`dashboard/server.py` sirve `dashboard/index.html`, una SPA con rutas hash `#/<id>/<pestaña>/<categoría>`). Secundaria: la CLI `scripts/pfg.py` (`trocear`, `validar`, `imagen`, `paginas`). Las skills `leer-pfg`, `grado-pfg`, `preguntas-pfg` y `anotaciones-pfg` las ejecuta un agente y quedan fuera: este arnés simula sus archivos de salida, que son el contrato con el dashboard.

Todo pasa por un solo script, `.agents/skills/verify-tribunal/verificar.py` (un script de uv; la primera vez descarga playwright y pymupdf). En los ejemplos, `V=.agents/skills/verify-tribunal/verificar.py`, ejecutado desde la raíz del repo.

## Reglas de aislamiento (léelas primero)

- **Nunca conduzcas `http://127.0.0.1:8765`** ni ninguna instancia que no hayas arrancado tú: es la del docente y `pfgs/` contiene memorias reales con datos personales.
- **Nunca leas, subas ni copies nada de `pfgs/` del repo.** Usa solo memorias sintéticas (`$V pdf`).
- El servidor fija su carpeta de datos en `<raíz>/pfgs` y no admite otra. Por eso `arrancar` copia `dashboard/`, `scripts/pfg.py`, `config/categorias.json`, `AGENTS.md`, `CLAUDE.md` y `.agents/` (con los enlaces de `.claude/`, que necesitan los agentes que lanza el dashboard) a una carpeta desechable y arranca esa copia en un puerto libre. Pueden convivir varias ejecuciones; fija la tuya con `export VERIFY_RUN=<run>`.
- Si cambias código del repo después de arrancar, la copia queda desfasada: `doctor` lo detecta. Haz `limpiar` y `arrancar` otra vez.

## Arrancar

```bash
$V arrancar
```

Copia la app a `$TMPDIR/tribunal-pfg-verify/runs/<run>/app`, crea `pfgs/` vacío y arranca `uv run <copia>/dashboard/server.py <puerto>`. Está listo cuando imprime `listo: http://127.0.0.1:<puerto>`. Antes de imprimirlo comprueba que el log contiene `Dashboard del tribunal en` y que `GET /api/pfgs` devuelve `[]`. El `webbrowser.open` del servidor se captura en `runs/<run>/navegador.log`, así que no se abre ninguna pestaña. `$V estado [url|puerto|app|pfgs|evidencia]` imprime las rutas de la ejecución.

## Doctor

```bash
$V doctor
```

Solo lee. Comprueba que el grupo de procesos sigue vivo, que el puerto lo escucha nuestro proceso (con `lsof`), que `/` es el dashboard, que la API sirve la carpeta desechable y que la copia coincide byte a byte con el checkout. Sale con 1 si algo falla. Ejecútalo primero siempre que algo parezca raro.

## Conducir

```bash
$V navegar <<'PY'
from playwright.sync_api import expect
page.get_by_role("button", name="Cargar PFG").click()
...
ev("nombre-de-la-prueba")
PY
```

`navegar` abre Chrome del sistema en modo headless (`channel="chrome"`, sin descargar navegadores), carga `/`, espera a que `#main` tenga contenido y ejecuta el guion de stdin con estas variables: `page`, `url`, `pfgs` (la carpeta de datos desechable, para comprobar efectos en disco), `evidencia` (Path), `json` y `ev(nombre)`. Si el guion lanza una excepción, guarda `error-<hora>` como evidencia y sale con código distinto de 0. Cada llamada es un navegador nuevo; el estado vive en el servidor y en las rutas hash.

Manejadores estables de la UI (no uses coordenadas):

| Qué | Localizador |
|---|---|
| Subir PDF | `get_by_role("button", name="Cargar PFG")` + `page.expect_file_chooser()` |
| Aviso tras una acción | `get_by_role("status")` (por ejemplo `1 PDF cargado.`) |
| Tarjeta de un PFG | `get_by_role("article").filter(has=get_by_role("link", name=<título o id>))` |
| Siguiente paso | botón «o copia la instrucción para tu agente» en la tarjeta (atributo `data-copiar`), o `locator("code")` y botón `Copiar` en el bloque «Siguiente paso» del detalle; ambos pasan a `Copiado` |
| Progreso de lectura | `get_by_role("progressbar")`, atributos `aria-valuenow`/`aria-valuemax` |
| Pestañas del detalle | enlaces `Ficha de lectura`, `Secciones · N/M`, `Preguntas · N`; la activa lleva `aria-current="page"` |
| Filtro por categoría | `get_by_role("navigation", name="Filtrar por categoría")`; el chip activo lleva `aria-current="true"` |
| Volver | `get_by_role("link", name="← Todos los PFG")` |
| Grados | `get_by_role("link", name="Grados")` en la cabecera; en un grado, `get_by_role("region", name="Añadir programas")` |

Para mover un PFG por los estados sin ejecutar las skills:

```bash
$V pdf "Memoria Demo Verificación.pdf"           # sintética; ruta relativa → carpeta de evidencia
$V fase memoria-demo-verificacion leido          # troceado|leyendo|leido|contrastado|preguntas|clasificadas
$V fichas grado-en-ingenieria-informatica        # fichas sintéticas para los programas del grado
```

`fase` trocea con la CLI real de la copia, escribe JSON sintéticos marcados `[sintético]` y borra los de fases posteriores. `contrastado` necesita un grado con fichas, creado por la UI y completado con `fichas`. Desde `leido` ejecuta `pfg.py validar` y sale con su código. El PDF hay que subirlo antes por la UI.

## Evidencia

Va a `$TMPDIR/tribunal-pfg-verify/evidencia/<run>/` (`$V estado evidencia`) y sobrevive a `limpiar`. `ev(nombre)` guarda `<nombre>.png` (página completa) y `<nombre>.aria.txt` (snapshot ARIA del body).

Criterios de prueba:

- Sigue el camino real del usuario: botones, enlaces y rutas hash. No escribas en `pfgs/` lo que debería llegar por la UI (la subida). `fase` es la excepción, porque sustituye a las skills, que son otra superficie.
- Captura la acción y el estado resultante (`ev` antes y después), no solo la pantalla final.
- Comprueba los efectos en disco además de lo visible: por ejemplo, que `pfgs/<id>/memoria.pdf` coincide byte a byte con el PDF subido.
- Para la CLI, guarda el comando, la salida estándar y de error y el código de salida.
- El dashboard se refresca cada 4 s. Usa `expect(...)` (reintenta hasta 5 s), nunca esperas fijas.

## Limpiar

```bash
$V limpiar
```

Envía SIGTERM al grupo de procesos que arrancó esta ejecución (SIGKILL a los 5 s) y borra `runs/<run>/`. Nunca mata por nombre de proceso. Conserva la evidencia e imprime su ruta. Hazlo también después de cada intento fallido.

## Mapa de funcionalidades

Antes de conducir, lee `features/README.md`. Cada archivo de `features/` es la receta de una funcionalidad. Una prueba que solo recorre una entrada no cubre las demás que liste el mapa.
