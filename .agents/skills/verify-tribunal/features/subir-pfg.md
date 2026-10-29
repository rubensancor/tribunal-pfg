# Subir memorias

El docente carga una o varias memorias en PDF. Cada una aparece como tarjeta «Pendiente de leer» y se guarda en `pfgs/<id>/memoria.pdf`, con un id sacado del nombre del archivo.

## Sub-features

- `subir-boton` sube con el botón «Cargar PFG» y el selector de archivos.
- `subir-arrastrar` sube al soltar archivos en cualquier parte de la página.
- `subir-repetido` da a un segundo archivo con el mismo nombre el id `<id>-2`.
- `subir-no-pdf` rechaza un archivo que no es PDF y lo avisa.
- `subir-preparar` lanza la lectura al cargar si está marcada la casilla «Leer y preguntar al cargar» de la cabecera (manda `preparar=1`), y al terminar bien lanza las preguntas. Si se cargan varios PDF, hacen cola y se preparan de uno en uno: las tarjetas que esperan muestran `En cola para leer y preguntar · puesto N` y ningún botón para lanzar. La tarjeta que lee muestra `Ejecutando: Lectura de la memoria con … · luego, preguntas para la defensa`. La casilla se recuerda en el navegador y no se ve ni se aplica en pantallas de 720 px o menos. Si no se puede lanzar, el PDF queda cargado y el aviso dice `<nombre>: cargado, pero no se pudo lanzar la lectura: <motivo>.`.
- `subir-panel-cola` muestra sobre la rejilla el panel «Cola de preparación» mientras algo se prepara o espera. La cabecera dice `N en marcha · M en espera`. Cada memoria en marcha tiene su bloque con el título, el botón «Detener», los pasos Lectura → Preguntas con el paso actual resaltado (`Lectura · 5/12` mientras lee) y la barra de progreso de la lectura. Debajo va la cola numerada con `en espera` en cada puesto, y al final los contadores `N listos`, `N con problemas` y `N sin preparar` de las memorias que quedan fuera. Si no hay nada en marcha ni en cola, el panel no aparece.

## How to get to it (user POV)

- Pulsar «Cargar PFG» en la cabecera y elegir uno o varios PDF.
- Arrastrar los PDF a la ventana; aparece el aviso «Suelta los PDF para cargarlos».

## Driving it with verificar.py

Preconditions:

- `$V doctor` sin fallos y la carpeta de datos vacía (`$V estado pfgs` no contiene nada).
- `$V pdf "Memoria Demo Verificación.pdf"` y `$V pdf "Arrastrado.pdf" 6` ya ejecutados.

- **Estado vacío.** Abrir el dashboard. `expect(page.get_by_text("Aún no hay ningún PFG")).to_be_visible()` y después `ev("subir-0-vacio")`.
- **Botón.** Pulsar «Cargar PFG» y elegir el PDF. `with page.expect_file_chooser() as fc: page.get_by_role("button", name="Cargar PFG").click()`, y después `fc.value.set_files(evidencia / "Memoria Demo Verificación.pdf")`. El estado pasa a `1 PDF cargado.` y aparece una tarjeta con el enlace `memoria-demo-verificacion` que contiene `Pendiente de leer`. `ev("subir-1-tarjeta")`.
- **Efecto en disco.** `assert (pfgs / "memoria-demo-verificacion" / "memoria.pdf").read_bytes() == (evidencia / "Memoria Demo Verificación.pdf").read_bytes()`.
- **Repetido.** Subir otra vez el mismo archivo con el botón. Aparece un segundo enlace, `memoria-demo-verificacion-2`, y `pfgs / "memoria-demo-verificacion-2" / "memoria.pdf"` existe.
- **Arrastrar.** Simular la acción de soltar con un `DataTransfer` real:
  ```python
  import base64
  datos = base64.b64encode((evidencia / "Arrastrado.pdf").read_bytes()).decode()
  page.evaluate("""([b64, nombre]) => { const dt = new DataTransfer();
    dt.items.add(new File([Uint8Array.from(atob(b64), c => c.charCodeAt(0))], nombre, {type: "application/pdf"}));
    document.body.dispatchEvent(new DragEvent("drop", {dataTransfer: dt, bubbles: true, cancelable: true})); }""",
    [datos, "Arrastrado.pdf"])
  ```
  Aparece el enlace `arrastrado`. `ev("subir-2-arrastrado")`.
- **No es PDF.** Crear `(evidencia / "falso.pdf").write_bytes(b"hola")` y subirlo con el botón. El estado debe mostrar `falso.pdf: no es un PDF` y no debe aparecer ninguna tarjeta `falso`. `ev("subir-3-no-pdf")`. En el servidor: `page.request.post(url + "/api/pfgs?nombre=falso.pdf", data=b"hola")` devuelve 400 con `{"error": "no es un PDF"}`.

## Gotchas

- El aviso final junta el recuento de subidos y los errores de cada archivo. Al subir a la vez `Buena.pdf` y `falso.pdf`, el estado es `1 PDF cargado. falso.pdf: no es un PDF`.
- Un archivo sin extensión `.pdf` no llega al servidor y añade `<nombre>: no es un PDF.` al aviso, también dentro de un lote mixto. El selector de archivos propone solo `.pdf` (`accept`), así que el camino habitual para un lote mixto es arrastrar y soltar (pasa un `File` por cada archivo en el mismo `DataTransfer`).
- `set_files` admite una lista para subir varios a la vez; el aviso pasa a `2 PDF cargados.`.
- Si estás en una vista de detalle, la subida te devuelve a `#/`.
