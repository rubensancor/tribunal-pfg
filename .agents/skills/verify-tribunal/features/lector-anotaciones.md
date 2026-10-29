# Lector de la memoria y anotaciones

En el detalle de un PFG, «Leer memoria» o cualquier enlace `pág. N` abre la memoria en un panel a la derecha (a pantalla completa por debajo de 1100 px), en esa página. La barra muestra `pág. 8 · PDF 10/40`, las flechas y el zoom. El docente selecciona texto y elige «Resaltar», «Nota personal», «Preguntar al agente» o «Para las preguntas». Cada nota aparece en la columna «Notas» con el color de su tipo, su cita y su texto, y se guarda en el servidor. Las preguntas al agente quedan pendientes hasta que `anotaciones-pfg` las responde en `respuestas.json`; editar una respondida la deja pendiente otra vez.

## Sub-features

- `lector-abrir`: «Leer memoria» abre en la página 1; un enlace `pág. N` de la ficha, las secciones o las preguntas abre en esa página. Con ⌘ o Ctrl más clic se abre `/pfgs/<id>/memoria.pdf#page=N` en otra pestaña y el lector no se abre.
- `lector-paginas`: las páginas se generan bajo demanda en `pfgs/<id>/paginas/` (`indice.json`, `pNNN.png`, `pNNN.json`) y solo se pintan las cercanas a la vista.
- `lector-navegar`: ← → y los botones cambian de página, «Ampliar» y «Reducir» escalan un 20 %, Esc cierra el lector.
- `lector-nota-crear`: los cuatro botones de la selección y «Nota en esta página» (personal, sin cita). Las personales van a `notas-personales.json` y las demás a `anotaciones.json`, con la `cita` y la `pag` que deriva el servidor.
- `lector-nota-tipo`: el desplegable «Tipo de nota» cambia el tipo y mueve la nota de archivo con el mismo id.
- `lector-nota-borrar`: «Borrar» quita la nota y muestra `Nota borrada.`.
- `lector-respuesta`: una respuesta en `respuestas.json` aparece como «Respuesta del agente» con enlaces de página; al editar la nota pasa a «Respuesta del agente a la versión anterior de la nota» y «Pendiente de enviar al agente».
- `lector-enviar`: «Enviar N preguntas al agente con <harness>» hace `POST /api/pfgs/<id>/ejecutar` con `{"fase": "anotaciones-pfg"}`. Sin notas pendientes, la API responde 409.
- `lector-tarde`: una nota «Para las preguntas» creada después de `preguntas.json` avisa de que solo cuenta si se vuelven a generar.
- `lector-repintado`: el refresco de cada 4 s no borra ni desenfoca una nota a medio escribir.

## How to get to it (user POV)

- Abrir el detalle de un PFG y pulsar «Leer memoria».
- Pulsar un enlace `pág. N` en «Ficha de lectura», «Secciones» o «Preguntas».
- Seleccionar texto en una página del lector.

## Driving it with verificar.py

Preconditions:

- Una memoria sintética con párrafos, para poder seleccionar varias líneas. `$V pdf` solo pone una línea por página; basta con un PDF generado con pymupdf (`insert_textbox`) en la carpeta de evidencia. Súbela por la UI.
- `$V fase <id> preguntas`, para que haya enlaces `pág. N` y `preguntas.json`.
- Las páginas y las palabras no tienen rol ARIA: usa `#hojas [data-pdf="N"] .capa span[data-i="I"]` para seleccionar y `#lista-notas > li` para las tarjetas.

- **Abrir.** En `#/<id>`, `page.locator(".bloque.flojo").get_by_role("link", name="pág. 8").click()`. `get_by_role("complementary", name="Lector de la memoria")` es visible, `#donde` dice `pág. 8 · PDF 10/40` y la ficha sigue visible. Existen `paginas/p010.png` y `p010.json`, y hay menos de 10 páginas con `data-pintada`.
- **Seleccionar.** Arrastra el ratón del primer al último span del rango con `page.mouse`. Aparece `get_by_role("toolbar", name="Anotar la selección")`. Pulsa «Preguntar al agente» y escribe. Al segundo, `anotaciones.json` tiene `palabras: [i, j]` y la `cita` es la unión de esas palabras de `p010.json`.
- **Cuatro tipos.** Repite con «Resaltar», «Nota personal» y «Para las preguntas», y pulsa «Nota en esta página». `notas-personales.json` tiene las personales (una con `palabras: null`) y `anotaciones.json` solo `agente` y `preguntas`.
- **Persistir.** Recarga y pulsa «Leer memoria»: las tarjetas siguen ahí y el `border-left-color` de cada una es el de su tipo.
- **Cambiar el tipo.** `get_by_label("Tipo de nota").select_option("agente")` en una personal: pasa a `anotaciones.json` con el mismo id y el botón «Enviar» cuenta una más.
- **Respuesta.** Escribe `respuestas.json` en la carpeta desechable con la `nota` exacta. En menos de 6 s se ve «Respuesta del agente» y desaparece «Pendiente de enviar al agente». Su enlace `pág. N` mueve el lector.
- **Editar.** `fill` y `blur` en el textarea de esa nota: vuelve «Pendiente de enviar al agente» y la respuesta pasa a ser de la versión anterior.
- **Repintado.** Escribe en un textarea, cambia `respuestas.json` para forzar un repintado y espera 4,5 s: el texto y el foco siguen.
- **Enviar.** Sin gastar tokens, intercepta con `page.route("**/api/pfgs/<id>/ejecutar", …)` y comprueba que el cuerpo es `{"fase": "anotaciones-pfg"}` y el estado `Preguntas enviadas al agente.`. El recorrido real está en [ejecutar-fases](./ejecutar-fases.md).
- **Tema y ancho.** Con `localStorage.tema = 'noche'` las páginas siguen blancas y los resaltes se leen. Con `page.set_viewport_size({"width": 800, "height": 900})` el lector ocupa los 800 px, sin desbordes, y «Notas · N» oculta la columna.

## Gotchas

- La primera vista de cada página ejecuta `uv run scripts/pfg.py imagen`: tarda unas décimas. Espera a `img.complete` antes de una captura.
- El navegador pide el JSON de la página antes que la PNG para que `imagen` no se ejecute dos veces a la vez.
- `ev()` hace capturas de página completa: el lector es fijo y sale solo en la parte de arriba. Para el lector a pantalla completa usa `page.screenshot` sin `full_page`.
- Una nota se guarda 0,7 s después de dejar de escribir o al perder el foco. Espera antes de leer el disco.
- No pulses «Enviar» sin interceptar la ruta: lanzaría un agente real.
