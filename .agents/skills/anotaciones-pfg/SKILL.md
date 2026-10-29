---
name: anotaciones-pfg
description: Responde las notas «Preguntar al agente» que el docente ha dejado al leer una memoria en el lector del dashboard del tribunal (pfgs/<id>/anotaciones.json) y escribe respuestas.json con página en cada afirmación. Úsala cuando pidan responder las notas o anotaciones de un PFG, o cuando peguen «usa la skill anotaciones-pfg con el PFG <id>».
---

# Responder las notas del docente

Entrada: un id de `pfgs/`. El docente lee la memoria en el dashboard, subraya pasajes y deja notas. Tú respondes las que son preguntas para ti.

**No abras `pfgs/<id>/notas-personales.json`.** Son notas privadas del docente y no deben llegar al proveedor del modelo.

## 1. Qué responder

Lee `pfgs/<id>/anotaciones.json` y, si existe, `pfgs/<id>/respuestas.json`. Cada nota tiene esta forma:

```json
{"k3f9a2c1": {"tipo": "agente", "pdf": 34, "pag": "22", "palabras": [120, 141],
              "cita": "la latencia media se reduce un 30 % respecto al sistema anterior",
              "nota": "¿Frente a qué carga? No veo cuántas repeticiones.", "creada": 1761730000}}
```

- `pdf` es la página del PDF y `pag`, la numeración impresa (`null` si la página no lleva número).
- `cita` es el texto que subrayó el docente. Si `palabras` es `null`, la nota es de toda la página, sin cita.

Responde solo las notas **pendientes**: `tipo` es `"agente"`, `nota` no está vacía y `respuestas.json` no tiene esa clave o la tiene con otra `nota` (el docente la ha editado). Las de tipo `"preguntas"` no se responden: las usa `preguntas-pfg`. Si no hay ninguna pendiente, dilo y termina.

## 2. Buscar en la memoria

- Si falta `secciones/indice.json`, ejecuta `uv run scripts/pfg.py trocear <id>`.
- Para cada nota, abre el `secciones/NN.txt` cuya sección contiene su `pdf` (rango `pdf_ini`–`pdf_fin` del índice) y busca la marca `[[pdf:N`. La cita está ahí con las mismas palabras, salvo las ligaduras («ﬁ»), que en la cita van separadas.
- Si la nota pide comparar con otra parte de la memoria, búscala también. `secciones/NN.json` y `analisis.json`, si existen, ayudan a localizarla.
- Si la nota es de página sin cita, o habla de una figura o una tabla, mira `paginas/pNNN.png`. Si no existe, ejecuta `uv run scripts/pfg.py imagen <id> <pdf>`.

## 3. Escribir `respuestas.json`

Reescribe `pfgs/<id>/respuestas.json` con las respuestas nuevas **y conserva las anteriores** de las notas que no tocas. En `nota` copia el texto exacto de la nota que respondes: así el dashboard sabe que está respondida y la vuelve a marcar pendiente si el docente la edita.

```json
{
  "k3f9a2c1": {
    "nota": "¿Frente a qué carga? No veo cuántas repeticiones.",
    "respuesta": [
      {"texto": "Compara con 100 usuarios simultáneos (cuadro 5.1).", "pdf": 50, "pag": "38"},
      {"texto": "No encuentro el número de repeticiones en el capítulo 5: duda que hay que verificar.", "pdf": 34, "pag": "22"}
    ]
  }
}
```

- Cada elemento de `respuesta` es una afirmación con su página: `pdf` entero y `pag` impresa, o `null`.
- Sé breve: de 1 a 4 elementos por nota.
- Si no encuentras algo, dilo como duda que hay que verificar y da la página donde lo has buscado.
- Si la nota pide una pregunta para la defensa, puedes proponerla en la respuesta, pero no toques `preguntas.json`.
- No escribas en `anotaciones.json`: lo escribe solo el dashboard.

Valida con `uv run scripts/pfg.py validar <id>` y corrige los problemas que empiecen por `respuestas.json`. Los demás son de otras fases: si has troceado tú la memoria, faltarán los `secciones/NN.json` hasta que se ejecute `leer-pfg`. Termina con el número de notas respondidas.

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota, no califiques y no afirmes que el estudiante ha usado IA.
- Todo lo que afirmes lleva página. Si no lo encuentras, no lo afirmes. Plantea los posibles errores técnicos como dudas.
- No inventes bibliografía, normativa ni datos externos. No mezcles contenido entre memorias.
- Escribe en el idioma de la memoria.
