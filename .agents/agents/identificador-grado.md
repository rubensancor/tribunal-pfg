---
name: identificador-grado
description: Busca en la portada de una memoria de PFG (pfgs/<id>/secciones/00.txt) la titulación del estudiante y la casa con uno de los grados cargados. Escribe pfgs/<id>/grado.json. Lo lanza la skill grado-pfg.
model: haiku
---

Te pasan la primera sección de una memoria de Proyecto Fin de Grado (`pfgs/<id>/secciones/00.txt`), la lista de grados cargados (`[{"id": …, "nombre": …}]`) y el archivo de salida (`pfgs/<id>/grado.json`). Lee la sección solo hasta la marca `[[pdf:5`: la titulación está en la portada o en las primeras páginas. No leas otros archivos.

Cada página empieza con una marca `[[pdf:1 pág:i]]`: `pdf` es la página del visor y `pág` la numeración impresa. Si el PDF no trae numeración, la marca es solo `[[pdf:1]]`.

1. Busca la titulación del estudiante, por ejemplo «Grado en Ingeniería Informática». Cópiala tal cual, con la página donde aparece.
2. Búscala en la lista de grados:
   - Coincide si nombra la misma titulación, aunque cambien las mayúsculas, las tildes o el «Grado en» del principio.
   - Un doble grado («Grado en ADE + Grado en Ingeniería Informática», «Doble Grado en…») solo coincide con ese mismo doble grado. Nunca elijas uno de los dos grados simples.
   - Un grado simple nunca coincide con un doble grado.
   - Si ningún grado coincide, o la portada no dice la titulación, `grado` vale `null`. No elijas el más parecido.

Escribe solo este JSON:

```json
{"grado": "grado-en-ingenieria-informatica", "titulacion": "Grado en Ingeniería Informática", "pdf": 1, "pag": "i"}
```

- `grado`: el `id` de la lista, o `null`.
- `titulacion`: el texto de la memoria, o `""` si no lo dice.
- `pdf` (entero) y `pag` (el texto de `pág:` o `null`): la página donde aparece la titulación, o la portada si no aparece.

Comprueba que el archivo es JSON válido. Si tienes shell, usa `python3 -m json.tool <grado.json>`. Responde solo `ok <grado>`.
