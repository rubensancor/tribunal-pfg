# Mapa de verificación del Tribunal PFG

Esta carpeta es la fuente que se mantiene para verificar lo que ve un docente en el dashboard. Lee el índice antes de conducir y usa el archivo de la funcionalidad como receta.

## Precondiciones base

- `V=.agents/skills/verify-tribunal/verificar.py`, ejecutado desde la raíz del repo.
- `$V arrancar` y después `$V doctor` sin ningún `FALLO`.
- La carpeta de datos desechable empieza vacía. Cada receta crea sus memorias con `$V pdf` y las sube por la UI.
- Nunca conduzcas el puerto 8765 ni uses nada del `pfgs/` del repo.

## Convenciones

- Los guiones de navegador van por `$V navegar <<'PY' … PY` y empiezan con `from playwright.sync_api import expect`.
- Usa roles ARIA y nombres accesibles (ver la tabla de SKILL.md), no selectores CSS, salvo los `locator("code")` y `locator("li.q")` que se indican.
- Toma los comandos al pie de la letra. Los ids de PFG salen del nombre del archivo: `Memoria Demo Verificación.pdf` → `memoria-demo-verificacion`.
- La CLI de verificación es la de la copia, `uv run "$($V estado app)/scripts/pfg.py"`. La del repo apunta al `pfgs/` real.

## Prueba e informes

- Prueba de UI: `ev(nombre)` antes y después de la acción (PNG + snapshot ARIA).
- Prueba de efecto: un `assert` sobre `pfgs` (disco) o sobre `page.request.get(url + "/api/…")`.
- Prueba de CLI: comando, salida estándar y de error, y código de salida.
- Anota con cada evidencia el id de la funcionalidad y la entrada que usaste.
- Si un camino no se puede recorrer, informa del comando que lo intentó y de la precondición que falta. No lo des por verificado usando otra entrada.

## Contrato de cada archivo

Un H1, un párrafo con el comportamiento visible y cuatro H2 en este orden: `Sub-features`, `How to get to it (user POV)`, `Driving it with verificar.py` (empieza por `Preconditions:`) y `Gotchas`.

## Funcionalidades

- [Subir memorias](./subir-pfg.md): botón, arrastrar y soltar, nombres repetidos y rechazo de archivos que no son PDF.
- [Estado y siguiente paso](./estados-pfg.md): estados de la tarjeta, KPI, progreso, comando del siguiente paso y botón Copiar.
- [Detalle de un PFG](./detalle-pfg.md): ficha, secciones, preguntas con filtro por categoría, enlaces al PDF y PFG inexistente.
- [Ejecutar fases y ajustes](./ejecutar-fases.md): harness y modelo por fase, lanzar, detener, resultado sin avance y protección de origen.
- [CLI pfg.py](./cli-pfg.md): `trocear`, `validar` e `imagen` sobre la copia desechable.

Las skills `leer-pfg` y `preguntas-pfg` se ejecutan de verdad solo en [ejecutar-fases](./ejecutar-fases.md), que gasta tokens. Las demás recetas usan `fase`, que simula sus archivos de salida.
