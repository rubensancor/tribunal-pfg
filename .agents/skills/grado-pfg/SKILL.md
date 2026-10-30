---
name: grado-pfg
description: Contrasta un PFG/TFG/TFM ya leído en el dashboard del tribunal (pfgs/<id>/analisis.json) con los programas de las asignaturas de su grado (grados/<gid>/). Identifica el grado en la portada, lee los programas que falten con un subagente barato y escribe contraste.json, con lo que el PFG aplica de lo que imparte el grado y dónde va más allá, siempre con página. Úsala cuando pidan contrastar un PFG con su grado o con las guías docentes, o cuando peguen «usa la skill grado-pfg con el PFG <id>».
---

# Contrastar con el grado

Entrada: un id de `pfgs/`. Necesita `pfgs/<id>/analisis.json`; si no existe, ejecuta antes la skill `leer-pfg`. Las rutas son relativas a la raíz del repo.

El contraste es un mapa para el tribunal, no una valoración. Solo cuenta lo que el PFG usa: no listes las asignaturas ni los temas que no usa, y no lo presentes como una carencia.

## Subagentes

Los pasos 1 y 2 usan agentes baratos. Usa la primera vía que tengas, como en `leer-pfg`:

1. **Subagentes con agentes de proyecto**, que ya traen fijado el modelo barato. Úsalos aunque el trabajo parezca pequeño: así no gastas el modelo principal en leer guías.
   - Claude Code: Agent/Task con `subagent_type: identificador-grado` o `subagent_type: lector-programa`.
   - Pi con pi-subagents: el agente del mismo nombre.
   - Codex: pide explícitamente lanzar el agente del mismo nombre (definido en `.codex/agents/`).
   - OpenCode: herramienta subagent con el agente del mismo nombre (definido en `.opencode/agents/`). Usa el modelo de la sesión.
2. **CLI no interactivo desde la shell**, solo en una sesión interactiva. En modo no interactivo (lanzado desde el dashboard) solo se permiten `uv run scripts/pfg.py` y `python3 -m json.tool`: pasa a la vía 3. El prompt es «Sigue .agents/agents/<agente>.md (ignora la cabecera YAML). <encargo>».
   - `claude -p --model haiku --permission-mode acceptEdits --allowedTools "Bash(python3 -m json.tool:*)" "<prompt>"`
   - `codex exec -m gpt-6-luna -s workspace-write "<prompt>"`
3. **Nada de lo anterior**: hazlo tú siguiendo el archivo del agente al pie de la letra.

## 1. Identificar el grado (agente `identificador-grado`)

```bash
uv run scripts/pfg.py grados
```

Imprime los grados cargados, `[{id, nombre}]`. Lanza el agente `identificador-grado` con este encargo, aunque ya exista `grado.json`, porque el docente puede haber cargado el grado después:

> Lee la portada en `pfgs/<id>/secciones/00.txt` y escribe `pfgs/<id>/grado.json`. Grados cargados: <la salida de `pfg.py grados`>.

Si `grado` es `null`, escribe `pfgs/<id>/contraste.json` y salta al paso 4:

```json
{"grado": null, "motivo": "La portada (pág. i) dice «…» y no hay ningún grado cargado con ese nombre.", "aplica": [], "extiende": []}
```

No contrastes con un grado parecido ni con uno de los dos grados de un doble grado.

## 2. Leer los programas que falten (agente `lector-programa`)

```bash
uv run scripts/pfg.py programas <gid>
```

Pasa a texto los programas nuevos o cambiados. Si imprime `ninguno`, ve al paso 3. Si sale con código 2, imprime una línea por programa sin ficha, con el texto que hay que leer y la ficha que hay que escribir. Lanza un `lector-programa` por línea, en paralelo y en tandas de 8 como máximo. El nombre del grado hace falta para elegir el curso y el carácter de su titulación:

> Lee `grados/<gid>/textos/<slug>.txt` y escribe `grados/<gid>/asignaturas/<slug>.json`. El grado es «<nombre del grado>».

Después valida las fichas:

```bash
uv run scripts/pfg.py validar-grado <gid>
```

Relanza los lectores de las fichas con errores (2 reintentos como máximo). Si siguen fallando, corrige tú el JSON. Los avisos no se corrigen: una guía sin contenidos no cuenta en el contraste.

## 3. Contrastar (tú, modelo principal)

```bash
uv run scripts/pfg.py catalogo <gid>
```

Imprime todas las fichas del grado en un JSON `{slug: ficha}`. Lee también `analisis.json` y los `secciones/NN.json`. Antes de afirmar algo, compruébalo en su tramo del `secciones/NN.txt`: busca la marca `[[pdf:N`.

- **`aplica`**: lo que la memoria hace con conocimiento que el grado imparte. Una entrada por uso concreto y relevante (una decisión, un método, una técnica), no por cada palabra que coincida. Cada entrada cita al menos un tema, `{"asignatura": "<slug>", "tema": "<id>"}`, con el slug del catálogo y el `id` del tema copiados tal cual.
- **`extiende`**: lo que va más allá de lo que se imparte. Puede ser una técnica, una herramienta o una profundidad que ningún programa cargado trata, o que supera lo que trata un tema. `mas_alla` dice en una frase en qué va más allá, comparado con el texto del tema. Si no hay ningún tema cercano, deja `temas` vacío y di en `mas_alla` que no aparece en los N programas cargados.
- Ir más allá no es sospechoso: es lo que se espera de un buen PFG. Descríbelo sin valorarlo.
- Cada entrada lleva la página de la memoria: `pdf` (entero) y `pag` (la numeración impresa, como en `analisis.json`). Sin página, no lo afirmes.
- El estudiante puede no haber cursado una optativa. No lo supongas en ningún sentido; el dashboard ya la marca.
- Cuántas: las que el trabajo dé, normalmente entre 5 y 15 en cada lista. No rellenes.

Escribe `pfgs/<id>/contraste.json`:

```json
{"grado": "<gid>", "motivo": "",
 "aplica": [{"texto": "Diseña el esquema en 3FN y desnormaliza el histórico por rendimiento.", "pdf": 34, "pag": "22",
             "temas": [{"asignatura": "145320", "tema": "TEMA 2"}]}],
 "extiende": [{"texto": "Sincroniza sin conexión con CRDT.", "pdf": 41, "pag": "29", "temas": [],
               "mas_alla": "No aparece en los 48 programas cargados."}]}
```

## 4. Validar

```bash
uv run scripts/pfg.py validar <id>
```

Corrige lo que señale. Termina con 2 líneas: el grado con el que se ha contrastado y cuántas entradas tiene cada lista, y el siguiente paso, «usa la skill preguntas-pfg con el PFG <id>».

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota, no califiques y no afirmes que el estudiante ha usado IA.
- Todo lo que afirmes lleva página de la memoria y, si aplica lo que se imparte, la asignatura y el tema del catálogo.
- No inventes asignaturas ni temas: solo los del catálogo. No mezcles contenido entre memorias.
- Escribe en el idioma de la memoria.
