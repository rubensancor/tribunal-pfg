---
name: leer-pfg
description: Lee la memoria de un PFG/TFG/TFM cargada en el dashboard del tribunal (pfgs/<id>/memoria.pdf). La trocea por secciones, resume cada una con un subagente barato y escribe la ficha de lectura (analisis.json) con el modelo principal. Úsala cuando pidan leer, analizar o resumir un PFG del dashboard, o cuando peguen «usa la skill leer-pfg con el PFG <id>».
---

# Leer PFG

Entrada: un id de `pfgs/`. Si no te lo dan, lista los PFG sin `analisis.json` y pregunta cuál, o procesa todos. Las rutas son relativas a la raíz del repo.

Reparto del trabajo: los **lectores** (modelo barato) resumen cada sección; **tú** (modelo principal, el más capaz) haces la síntesis a partir de esos resúmenes. No leas la memoria entera tú mismo.

## 1. Trocear

```bash
uv run scripts/pfg.py trocear <id>
```

Escribe `pfgs/<id>/secciones/indice.json` y un `NN.txt` por sección, con marcas de página `[[pdf:N pág:M]]`. Si ya estaba troceado, sigue adelante.

## 2. Lectores (modelo barato)

Lanza un lector por cada sección del índice que todavía no tenga `NN.json`; así el proceso se puede reanudar. Ve en paralelo, en tandas de 8 como máximo. A cada lector le basta este encargo:

> Lee `pfgs/<id>/secciones/NN.txt` y escribe `pfgs/<id>/secciones/NN.json`.

Sus instrucciones están en `.agents/agents/lector-seccion.md`. Usa la primera vía que tengas:

1. **Subagentes con agentes de proyecto**, que ya traen fijado el modelo barato:
   - Claude Code: Agent/Task con `subagent_type: lector-seccion`.
   - Pi con pi-subagents: agente `lector-seccion`.
   - Codex: pide explícitamente lanzar el agente `lector-seccion` (definido en `.codex/agents/`).
   - OpenCode: herramienta subagent con el agente `lector-seccion` (definido en `.opencode/agents/`). Usa el modelo de la sesión.
2. **CLI no interactivo desde la shell**, solo en una sesión interactiva. En modo no interactivo (lanzado desde el dashboard) solo se permiten `uv run scripts/pfg.py` y `python3 -m json.tool`: no busques ni lances otros CLI y pasa a la vía 3. Un proceso por sección, con `&` y `wait`. El prompt es: «Sigue .agents/agents/lector-seccion.md (ignora la cabecera YAML). Lee … y escribe …».
   - `claude -p --model sonnet --permission-mode acceptEdits --allowedTools "Bash(python3 -m json.tool:*)" "<prompt>"`
   - `pi -p --model sonnet --no-session "<prompt>"`
   - `codex exec -m gpt-6-luna -s workspace-write "<prompt>"`
3. **Nada de lo anterior**: lee tú las secciones de una en una siguiendo `lector-seccion.md` al pie de la letra. Avisa al usuario de que así cuesta más.

## 3. Validar

```bash
uv run scripts/pfg.py validar <id>
```

Si hay errores, relanza los lectores de esas secciones (2 reintentos como máximo). Si siguen fallando, corrige tú el JSON.

## 4. Síntesis (tú)

- Lee `secciones/indice.json` y todos los `secciones/NN.json`. **No leas los `NN.txt` enteros.**
- Antes de afirmar una cifra, una tensión o un posible error, compruébalo en su tramo del `NN.txt`: busca la marca `[[pdf:N`.
- Si una figura con datos importa (aparece en `no_legible`, o su página está en `paginas_sin_texto`), ejecuta `uv run scripts/pfg.py imagen <id> <pdf>` y mira la PNG.
- **Páginas**: cita siempre la numeración impresa (`pag`); `pdf` sirve para abrir el visor.
  - Si las marcas no traen `pág:`, calcula el desfase comprobándolo en dos puntos distintos, donde el número impreso se lea en el texto.
  - Rellena `pag` = pdf − desfase y anota el desfase en `desfase_paginas`.
  - En portada, índices o anexos sin número impreso, `pag` vale `null`.
- Aplica las lentes de `.agents/skills/leer-pfg/lentes.md` que encajen con el tipo de proyecto.

Escribe `pfgs/<id>/analisis.json`. Todas las claves son obligatorias: si un dato no aparece, usa `""` o `null`. En `coherencia`, el par `pdf`/`pag` señala dónde se plantea el objetivo, y `evaluacion` dónde se evalúa (`null` si no se evalúa).

```json
{
  "titulo": "", "estudiante": "", "titulacion": "", "director": "", "paginas": 0, "desfase_paginas": 0,
  "que_hace": "dos frases",
  "aportacion_propia": "lo que ha hecho el estudiante, no lo que ha usado",
  "decisiones": [{"texto": "", "pdf": 0, "pag": ""}],
  "resultados": [{"texto": "cifras", "pdf": 0, "pag": ""}],
  "fortalezas": [{"texto": "2–3, concretas", "pdf": 0, "pag": ""}],
  "debilidades": [{"texto": "3–5, concretas", "pdf": 0, "pag": ""}],
  "leer_al_menos": "págs. … (las 10–15 donde están el núcleo y las dudas)",
  "coherencia": [{"objetivo": "", "pdf": 0, "pag": "", "evaluado": "sí|parcial|no", "evaluacion": {"pdf": 0, "pag": ""}, "comentario": ""}],
  "notas_tribunal": ["lo que no se ha podido leer o verificar", "posibles errores técnicos, con página, como dudas que hay que confirmar"]
}
```

Después vuelve a ejecutar `validar` y termina con 3 líneas: qué hace el trabajo, su principal debilidad y el siguiente paso, «usa la skill preguntas-pfg con el PFG <id>».

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota, no califiques y no afirmes que el estudiante ha usado IA.
- Todo lo que afirmes lleva página. Si no lo encuentras, no lo afirmes. Plantea los posibles errores técnicos como dudas.
- No inventes bibliografía, normativa ni datos externos. No mezcles contenido entre memorias.
