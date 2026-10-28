# Subir memorias

El docente carga una o varias memorias en PDF. Cada una aparece como tarjeta «Pendiente de leer» y se guarda en `pfgs/<id>/memoria.pdf`, con un id sacado del nombre del archivo.

## Sub-features

- `subir-boton` sube con el botón «Cargar PFG» y el selector de archivos.
- `subir-arrastrar` sube al soltar archivos en cualquier parte de la página.
- `subir-repetido` da a un segundo archivo con el mismo nombre el id `<id>-2`.
- `subir-no-pdf` rechaza un archivo que no es PDF y lo avisa.

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

- `subir()` en `index.html` muestra siempre `N PDF cargado(s).` al terminar, también cuando el servidor rechaza el archivo. El aviso de error dura milisegundos y la comprobación del estado de `subir-no-pdf` falla. Es un fallo real de la app; no relajes la comprobación.
- Un archivo sin extensión `.pdf` no llega al servidor: el aviso es `Solo se pueden cargar archivos PDF.`.
- `set_files` admite una lista para subir varios a la vez; el aviso pasa a `2 PDF cargados.`.
- Si estás en una vista de detalle, la subida te devuelve a `#/`.
