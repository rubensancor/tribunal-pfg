# Tribunal PFG

Herramienta para preparar tribunales de Proyecto Fin de Grado: un dashboard local donde se cargan y se leen memorias en PDF, y tres skills que las leen, generan preguntas para la defensa y responden las notas del docente.

## Arrancar el dashboard

Si piden «inicializa», «arranca» o «abre el dashboard», ejecuta en segundo plano:

```bash
uv run dashboard/server.py
```

Abre http://127.0.0.1:8765. Si el puerto ya está ocupado, probablemente el dashboard ya esté en marcha.

## Flujo

1. El usuario sube los PDF en el dashboard, que los guarda en `pfgs/<id>/memoria.pdf`.
2. Skill `leer-pfg`: escribe los resúmenes por sección y `analisis.json`.
3. Skill `preguntas-pfg`: escribe `preguntas.json` y después `clasificacion.json`. Tiene en cuenta las notas «Para las preguntas» de `anotaciones.json`.
4. Cuando quiera, el docente lee la memoria en el dashboard y anota. Skill `anotaciones-pfg`: responde las notas «Preguntar al agente» de `anotaciones.json` en `respuestas.json`.

El dashboard muestra lo que haya en `pfgs/<id>/` y el siguiente paso. También puede lanzar las skills en modo no interactivo con el harness y el modelo que fije `config/ejecucion.json` (pantalla Ajustes). En ese caso nadie leerá tus preguntas: no pidas confirmación. Los JSON de `pfgs/` son el contrato con el dashboard: después de escribirlos, ejecuta `uv run scripts/pfg.py validar <id>`.

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota ni califiques, y no afirmes que el estudiante ha usado IA.
- Todo lo que afirmes sobre una memoria lleva página. Si no lo encuentras, no lo afirmes. Plantea los posibles errores técnicos como dudas que hay que verificar.
- No mezcles contenido entre memorias. No inventes bibliografía, normativa ni datos externos.
- Escribe en el idioma de la memoria.
- Privacidad: las memorias contienen datos personales y trabajo no publicado. No salen de `pfgs/`, que está en `.gitignore`. Recuerda al docente una vez, en una línea, que use la herramienta de IA que autorice la universidad.
- Mientras generas preguntas no leas `config/categorias.json`: lo usa solo el clasificador, después.
- No leas `notas-personales.json`: son notas privadas del docente.

## Desarrollo

- Test: `uv run tests/test_pfg.py` y `uv run tests/test_dashboard.py`
- Las instrucciones de los subagentes están en `.agents/agents/*.md`, que es la fuente única. `.claude/agents` es un enlace a esa carpeta, y `.codex/agents/*.toml` solo apunta a esos archivos y fija el modelo de Codex.
