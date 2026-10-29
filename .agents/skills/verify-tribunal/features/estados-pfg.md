# Estado y siguiente paso

Cada tarjeta muestra el estado del PFG, deducido de los archivos que hay en `pfgs/<id>/`, y el comando que hay que pegar en el agente para avanzar. Los KPI de arriba cuentan cuántos hay en cada tramo. La página se refresca sola cada 4 s.

## Sub-features

- `estado-pendiente`: solo hay `memoria.pdf`. Insignia «Pendiente de leer» y comando `usa la skill leer-pfg con el PFG <id>`.
- `estado-leyendo`: hay `secciones/indice.json` pero no `analisis.json`. Insignia «Leyendo», barra de progreso `leídas/secciones` y el mismo comando.
- `estado-leido`: hay `analisis.json`. Insignia «Leído», el título y el estudiante salen de la ficha, y el comando pasa a `usa la skill preguntas-pfg con el PFG <id>`.
- `estado-preguntas`: hay `preguntas.json`. Insignia «Preguntas sin clasificar» y el mismo comando.
- `estado-clasificadas`: hay `clasificacion.json`. Insignia «Listo» y ningún comando.
- `estado-copiar`: el botón «o copia la instrucción para tu agente» copia el comando al portapapeles y cambia a «Copiado».
- `estado-kpi`: «PFG cargados», «por leer», «en preparación» y «listo(s) para la defensa», en una frase.

## How to get to it (user POV)

- Abrir la lista (`#/`) y mirar la tarjeta.
- Abrir el detalle: el comando aparece en el bloque «Siguiente paso: pégalo en tu agente».

## Driving it with verificar.py

Preconditions:

- `memoria-demo-verificacion` subido por la UI (ver [subir-pfg](./subir-pfg.md)).
- En los guiones, `card = page.get_by_role("article").filter(has=page.get_by_role("link", name=<nombre>))`. Hasta `leido` el nombre es el id con espacios y mayúscula inicial (`Memoria demo verificacion`), y desde ahí el título `Memoria sintética de verificación`.

- **Pendiente.** `expect(card).to_contain_text("Pendiente de leer")` y `expect(card.get_by_role("button", name="o copia la instrucción para tu agente")).to_have_attribute("data-copiar", "usa la skill leer-pfg con el PFG memoria-demo-verificacion")`.
- **Copiar.** `card.get_by_role("button", name="o copia la instrucción para tu agente").click()`. Aparece el botón `Copiado` y `page.evaluate("navigator.clipboard.readText()")` es el comando. `ev("estado-copiar")`.
- **Leyendo.** `$V fase memoria-demo-verificacion leyendo`. `expect(card).to_contain_text("Leyendo")` y `expect(card.get_by_role("progressbar")).to_have_attribute("aria-valuenow", "1")`. `ev("estado-leyendo")`.
- **Leído.** `$V fase memoria-demo-verificacion leido` sale con `ok`. La tarjeta con el enlace `Memoria sintética de verificación` muestra `Leído`, `Estudiante Sintético` y el comando `usa la skill preguntas-pfg con el PFG memoria-demo-verificacion`.
- **Sin clasificar.** `$V fase memoria-demo-verificacion preguntas`. La tarjeta muestra `Preguntas sin clasificar` y `3 preguntas`.
- **Listo.** `$V fase memoria-demo-verificacion clasificadas`. La tarjeta muestra `Listo` y `expect(card.locator("code")).to_have_count(0)`. `ev("estado-listo")`.
- **Refresco automático.** Con la página abierta, en el mismo guion, cambia de fase sin recargar: `import subprocess; subprocess.run([".agents/skills/verify-tribunal/verificar.py", "fase", "memoria-demo-verificacion", "preguntas"], check=True)`. En menos de 5 s la tarjeta pasa a `Sin clasificar` sin `page.reload()`.
- **KPI.** Con un PFG en `clasificadas` y otro recién subido, `expect(page.get_by_role("main")).to_contain_text("2 PFG cargados")`, `1 por leer` y `1 listo para la defensa`.

## Gotchas

- `fase` borra los archivos de las fases posteriores, así que se puede retroceder de estado.
- `fase leyendo` marca como leída solo la primera sección. Con un PDF de una sola sección, la barra no aparece y se ve «Secciones leídas · sintetizando…».
- Los KPI son una frase sobre la rejilla (solo aparecen los grupos que no están a cero): compruébalos con `to_contain_text` sobre `main`, no por rol.
- Un JSON roto no rompe la tarjeta: se ve en el detalle como un error rojo `<archivo>: JSON no válido`.
