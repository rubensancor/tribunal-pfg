# Tribunal PFG

Herramienta para preparar tribunales de Proyecto Fin de Grado: un dashboard local donde se cargan y se leen memorias en PDF, y cuatro skills que las leen, las contrastan con los programas de su grado, generan preguntas para la defensa y responden las notas del docente.

## Arrancar el dashboard

Si piden «inicializa», «arranca» o «abre el dashboard», ejecuta en segundo plano:

```bash
uv run dashboard/server.py
```

Abre http://127.0.0.1:8765. Si el puerto ya está ocupado, probablemente el dashboard ya esté en marcha.

Si piden «actualiza», ejecuta `git pull --ff-only` y pide que reinicien el dashboard. Si git se niega por cambios locales, di qué archivos son y no los descartes. El dashboard también actualiza desde Ajustes, hasta la última release.

## Flujo

1. El usuario sube los PDF en el dashboard, que los guarda en `pfgs/<id>/memoria.pdf`.
2. Skill `leer-pfg`: escribe los resúmenes por sección y `analisis.json`.
3. Skill `grado-pfg`, solo si el docente ha cargado en la pantalla Grados los programas de algún grado (`grados/<gid>/`): identifica el grado en la portada (`grado.json`), lee los programas que falten (`grados/<gid>/asignaturas/`) y escribe `contraste.json`.
4. Skill `preguntas-pfg`: escribe `preguntas.json` y después `clasificacion.json`. Tiene en cuenta las notas «Para las preguntas» de `anotaciones.json` y lo que va más allá del grado en `contraste.json`.
5. Cuando quiera, el docente lee la memoria en el dashboard y anota. Skill `anotaciones-pfg`: responde las notas «Preguntar al agente» de `anotaciones.json` en `respuestas.json`.

El dashboard muestra lo que haya en `pfgs/<id>/` y el siguiente paso. También puede lanzar las skills en modo no interactivo con el harness y el modelo que fije `config/ejecucion.json` (pantalla Ajustes). En ese caso nadie leerá tus preguntas: no pidas confirmación. Los JSON de `pfgs/` son el contrato con el dashboard: después de escribirlos, ejecuta `uv run scripts/pfg.py validar <id>`.

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota ni califiques, y no afirmes que el estudiante ha usado IA.
- Todo lo que afirmes sobre una memoria lleva página. Si no lo encuentras, no lo afirmes. Plantea los posibles errores técnicos como dudas que hay que verificar.
- No mezcles contenido entre memorias. No inventes bibliografía, normativa ni datos externos.
- Escribe en el idioma de la memoria.
- Privacidad: las memorias contienen datos personales y trabajo no publicado. No salen de `pfgs/`, que está en `.gitignore`. Recuerda al docente una vez, en una línea, que use la herramienta de IA que autorice la universidad.
- En el contraste con el grado, lo que aplica cita la asignatura y el tema del catálogo. Lista solo lo que el PFG usa, nunca las asignaturas que no usa.
- Mientras generas preguntas no leas `config/categorias.json`: lo usa solo el clasificador, después.
- No leas `notas-personales.json`: son notas privadas del docente.

## Desarrollo

- Test: `uv run tests/test_pfg.py`, `uv run tests/test_dashboard.py` y `uv run tests/test_instalar.py`
- App de escritorio: `npm install` y `npx electron .`. `app/main.js` arranca `server.py` con `TRIBUNAL_APP=1`, que no abre el navegador, para cuando la app cierra su stdin y tras actualizar sale con el código 75 para que la app lo arranque otra vez.
- Empaquetar: `npm run dist -- --mac --win --linux`, que deja en `dist/` los `.dmg`, el instalador `.exe` y el `.AppImage`, sin firmar (macOS lleva firma ad hoc). Cada paquete lleva el código en `resources/tribunal/` y su `uv` en `resources/uv/` (lo descarga `app/uv.js`, con versión y sha256 fijados). Al arrancar, `scripts/instalar.py` copia ese código a `Documentos/Tribunal PFG`, la carpeta de trabajo donde corren el dashboard y los agentes: conserva los archivos que cambió el docente y nunca toca `pfgs/`, `grados/` ni `config/ejecucion.json`. Si añades un archivo o una carpeta que necesitan los agentes, añádelo a `scripts/codigo.json`: de esa lista salen el paquete y el código que baja el botón Actualizar de la app (el tarball de la release, que se instala igual y no vuelve atrás al abrir otra vez la app).
- Versiones: semver `0.x` en `VERSION`. Para publicar, sube `VERSION`, haz commit en `main`, crea la tag `vX.Y.Z`, súbela y ejecuta `gh release create vX.Y.Z --generate-notes`. Al publicarse, `.github/workflows/instaladores.yml` cuelga en ella los cuatro instaladores; falla si la tag no coincide con `VERSION`. `.github/workflows/tests.yml` pasa los tests en Linux, macOS y Windows. El botón Actualizar del dashboard avanza solo hasta la última release. Una versión nueva debe seguir leyendo los `pfgs/` de las anteriores: si cambia el formato de un JSON, la migración va en el arranque y lleva su test.
- Las instrucciones de los subagentes están en `.agents/agents/*.md`, que es la fuente única. `.claude/agents` es un enlace a esa carpeta, `.codex/agents/*.toml` solo apunta a esos archivos y fija el modelo de Codex, y `.opencode/agents/*.md` solo apunta a ellos y hereda el modelo de la sesión.
