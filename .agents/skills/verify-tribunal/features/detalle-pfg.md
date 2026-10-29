# Detalle de un PFG

Al abrir una tarjeta se ve el detalle: la cabecera con la ficha, el botón «Leer memoria», el botón «Borrar» y tres pestañas. «Ficha de lectura» muestra el análisis, «Secciones» los resúmenes por sección con sus tensiones y «Preguntas» las preguntas ordenadas por prioridad, con un filtro por categoría cuando ya están clasificadas. Todo lo que se afirma enlaza a su página, que se abre en el lector (ver [lector-anotaciones](./lector-anotaciones.md)).

## Sub-features

- `detalle-ficha`: los bloques «Qué hace», «Aportación propia», «Decisiones clave», «Puntos fuertes», «Coherencia objetivos ↔ resultados» y los demás, con enlaces `pág. N`.
- `detalle-secciones`: un desplegable por sección con su número, título y rango de PDF. Las secciones aún no leídas muestran «sin leer».
- `detalle-preguntas`: las preguntas ordenadas por prioridad, con su anclaje y «Cómo valorar la respuesta».
- `detalle-filtro`: los chips de categoría con su recuento. Filtran por la ruta `#/<id>/preguntas/<categoría>`.
- `detalle-pdf`: «Leer memoria» y los enlaces de página abren el lector; con ⌘ o Ctrl más clic abren `/pfgs/<id>/memoria.pdf#page=N` en el visor del navegador.
- `detalle-vacios`: estados vacíos («Todavía no hay ficha de lectura», «Todavía no hay secciones», «Todavía no hay preguntas»).
- `detalle-inexistente`: `#/no-existe` muestra «Ese PFG no existe».
- `detalle-borrar`: «Borrar» pide confirmación en el mismo diálogo que el borrado de varios y borra `pfgs/<id>/` entero, con el PDF, los resúmenes, la ficha, las preguntas y los registros. Vuelve a la lista con `PFG borrado.`. Con una ejecución en curso se niega con `detén la ejecución en curso antes de borrar este PFG`.

## How to get to it (user POV)

- Pulsar el título de una tarjeta en la lista.
- Abrir directamente `#/<id>`, `#/<id>/secciones`, `#/<id>/preguntas` o `#/<id>/preguntas/<categoría>`.
- Volver con «← Todos los PFG».

## Driving it with verificar.py

Preconditions:

- `memoria-demo-verificacion` subido por la UI.
- `$V fase memoria-demo-verificacion clasificadas` sale con `ok`. Las 3 preguntas sintéticas quedan clasificadas así: `validacion` ×2 y `decisiones-diseno` ×1.

- **Vacíos.** Antes de ejecutar `fase`, con el PDF recién subido, `page.goto(url + "/#/memoria-demo-verificacion")`. Se ven `Todavía no hay ficha de lectura`, en `#/memoria-demo-verificacion/secciones` se ve `Todavía no hay secciones` y en `#/memoria-demo-verificacion/preguntas` se ve `Todavía no hay preguntas`.
- **Abrir la ficha.** `page.get_by_role("link", name="Memoria sintética de verificación").click()`. `expect(page.get_by_role("heading", level=1)).to_have_text("Memoria sintética de verificación")` y `expect(page.get_by_role("heading", name="Qué hace")).to_be_visible()`. `ev("detalle-ficha")`.
- **Secciones.** `page.get_by_role("link", name="Secciones · ").click()` y después `page.locator("details.sec summary").first.click()`. Se ve la etiqueta `Sin evidencia` y el resumen `[sintético] Resumen de …`. `ev("detalle-secciones")`.
- **Preguntas.** `page.get_by_role("link", name="Preguntas · 3").click()`. `expect(page.locator("li.q")).to_have_count(3)` y el chip `Todas` lleva `aria-current="true"`.
- **Filtro.** `page.get_by_role("navigation", name="Filtrar por categoría").get_by_role("link", name="Validación y pruebas").click()`. `expect(page.locator("li.q")).to_have_count(2)` y `location.hash` es `#/memoria-demo-verificacion/preguntas/validacion`. `ev("detalle-filtro")`.
- **PDF.** `r = page.request.get(url + "/pfgs/memoria-demo-verificacion/memoria.pdf")`, con `r.ok`, `r.headers["content-type"] == "application/pdf"` y `r.body().startswith(b"%PDF")`. El enlace «Leer memoria» tiene `href` `/pfgs/memoria-demo-verificacion/memoria.pdf`.
- **Inexistente.** `page.goto(url + "/#/no-existe")`. Se ve `Ese PFG no existe` con el enlace `Volver`.
- **Borrar.** Sube una segunda memoria y ponla en `leido`. En su detalle pulsa `Borrar`: `page.get_by_role("dialog")` muestra `¿Borrar este PFG?` con su título, estado y estudiante. `Escape` o `Cancelar` no borran nada. `dialog.get_by_role("button", name="Borrar", exact=True).click()` deja el estado `PFG borrado.`, la URL vuelve a `#/`, `(pfgs / <id>).exists()` es falso, `GET /api/pfgs/<id>` y `/pfgs/<id>/memoria.pdf` devuelven 404 y la otra memoria sigue en disco. Con `Origin: https://evil.example`, `POST /api/pfgs/<id>/borrar` devuelve 403.

## Gotchas

- El nombre accesible de las pestañas lleva los recuentos (`Secciones · 3/3`, `Preguntas · 3`). Usa un prefijo o el recuento esperado.
- Los chips de categorías vacías se muestran atenuados con recuento 0. El chip `Otra` solo aparece si alguna pregunta tiene esa categoría.
- Las pestañas y los chips son enlaces hash: cambiar de vista no recarga la página y el estado se queda en la URL.
- Al imprimir se abren todos los `details` (con `beforeprint`) y se oculta la navegación (con CSS `@media print`). `page.emulate_media(media="print")` aplica el CSS pero no dispara `beforeprint`. Para probar las dos cosas, ejecuta `page.evaluate("dispatchEvent(new Event('beforeprint'))")` y después `page.emulate_media(media="print")`, `ev(...)`.
