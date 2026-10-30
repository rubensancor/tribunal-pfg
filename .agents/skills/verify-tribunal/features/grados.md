# Programas del grado

En **Grados** el docente crea un grado por titulación y le añade las guías docentes de sus asignaturas: archivos PDF o `.txt`, URL (una por línea, que el dashboard descarga) o texto pegado. Cada grado lista sus asignaturas, leídas o sin leer. Cuando hay algún grado con programas, un PFG leído pasa a «Contrastar con el grado» antes de las preguntas, y su detalle gana la pestaña «Grado · N más allá», con lo que va más allá de lo que se imparte y lo que aplica, cada cosa con su página.

## Sub-features

- `grados-lista`: botón «Grados» de la cabecera (`#grados`). Una tarjeta por grado con su estado (`Sin programas`, `N sin leer` o `Leídos`), el número de programas y los PFG que lo usan, y la tarjeta «Nuevo grado».
- `grado-crear`: «Nuevo grado» con el nombre exacto de la titulación lleva a `#grados/<gid>`. Un nombre repetido da `ya hay un grado con ese nombre`.
- `programa-archivo`: «Elegir archivos» o soltar PDF o `.txt` en la página del grado. Se guarda en `grados/<gid>/programas/<slug>.<ext>`.
- `programa-url`: cuadro «URL de las guías», una por línea, y «Descargar». El cuadro se vacía al momento y debajo sale la región «Progreso de las URL»: un resumen (`3 de 8 descargadas · 1 con error · descargando la 5.ª`) y una fila por URL con `En cola`, `Descargando…`, `Añadida → <slug>` o `Error: <motivo>`. El servidor las baja en segundo plano, de una en una, y la página se refresca cada segundo mientras queden pendientes; las asignaturas aparecen según se guardan. Las filas terminadas siguen hasta el siguiente «Descargar» o hasta reiniciar el servidor. Una redirección a algo que no sea http o https falla con `redirige a <destino>, que no es una URL http o https`. `_codAsignatura` da el slug: la misma asignatura sustituye a la anterior y borra su ficha.
- `programa-pegado`: «Pegar texto» con «Nombre del programa (opcional)». Sin nombre, el slug sale de la primera línea.
- `asignaturas`: una fila desplegable por programa. Leída: `curso.º · carácter · N temas · origen`, los temas al desplegar, «Ver fuente» y «Borrar». Sin leer: `sin leer · origen`.
- `paso-contrastar`: tras `fase leido`, con algún grado con programas, la tarjeta ofrece «Contrastar con el grado con …» y la instrucción `usa la skill grado-pfg con el PFG <id>`. Sin grados, el paso sigue siendo `preguntas-pfg`.
- `pestana-grado`: «Grado · N más allá». La línea «Comparado con <grado> (N programas). Identificado en la portada (pág. i): «…». Es un mapa para el tribunal, no una valoración.», el bloque «Va más allá de lo que se imparte» y después «Aplica lo que se imparte». Cada entrada lleva su enlace de página, una etiqueta `asignatura · tema` con el texto del tema al pasar el ratón y, si la asignatura es optativa, la etiqueta `optativa`.
- `desfase`: si cambian los programas o las fichas después del contraste, la pestaña avisa «Los programas del grado han cambiado después del contraste.» y ofrece «Rehacer el contraste con …». No cambia el estado del PFG.
- `grado-null`: si la portada no casa con ningún grado, el contraste dice por qué y el PFG sigue a las preguntas.

## How to get to it (user POV)

- Cabecera → «Grados» → «Nuevo grado» → la página del grado → «Añadir programas».
- Un PFG leído → su tarjeta o «Siguiente paso» → «Contrastar con el grado». Después, la pestaña «Grado».

## Driving it with verificar.py

Preconditions:

- `$V arrancar` y `$V doctor` sin `FALLO`. Las guías de prueba son sintéticas o páginas públicas guardadas en disco. Para las URL, sírvelas con un servidor HTTP local que arranques tú en otro puerto (nunca el 8765) y páralo al terminar.
- Para el PFG: `$V pdf "Memoria Demo Verificación.pdf"` subido por la UI (ver [subir-pfg](./subir-pfg.md)).

- **Crear.** `page.get_by_role("link", name="Grados").click()`, `page.get_by_role("textbox", name="Nuevo grado").fill("Grado en Ingeniería Informática")` y «Crear grado». La URL acaba en `#grados/grado-en-ingenieria-informatica` y existe `grados/<gid>/grado.json` en `$($V estado app)`.
- **Archivo.** `with page.expect_file_chooser() as fc: page.get_by_role("button", name="Elegir archivos").click()` y `fc.value.set_files([...])`. Estado `N programas añadidos.`.
- **Pegado.** Rellena «Nombre del programa (opcional)» y el cuadro «Pegar texto» y pulsa «Añadir».
- **URL.** Rellena «URL de las guías» con varias líneas, una de ellas mala, y pulsa «Descargar». Sirve las guías con un retraso por petición para capturar `En cola` y `Descargando…` mientras la página sigue respondiendo. Comprueba `get_by_role("region", name="Progreso de las URL")`, los errores y `grados/<gid>/grado.json` (`fuentes`).
- **CLI.** `uv run "$($V estado app)/scripts/pfg.py" programas <gid>` sale con 2 y lista una línea `texto ficha` por programa.
- **Fichas.** `$V fichas <gid>` ejecuta esa misma CLI, escribe fichas `[sintético]` (la última, optativa) y sale con el código de `validar-grado`. La página del grado pasa a `N de N programas leídos`.
- **Contrastar.** `$V fase <id> leido`: la tarjeta muestra el botón «Contrastar con el grado con …». `$V fase <id> contrastado` sale con `ok` y escribe `grado.json` y `contraste.json` sintéticos con temas reales del catálogo. En `#/<id>/grado`, `Va más allá` va antes que `Aplica`; y la tarjeta ofrece «Generar las preguntas».
- **Desfase.** Añade otro programa al grado y vuelve a `#/<id>/grado`: aparece el aviso y el botón «Rehacer el contraste con …».

## Gotchas

- `fase` con una fase igual o posterior a `contrastado` escribe el contraste si hay algún grado con fichas; sin grados, se comporta como antes.
- La pestaña «Grado» solo aparece si hay contraste o algún grado con programas: sin grados, el detalle es el de siempre.
- Soltar archivos en la página de un grado los añade como programas, no como memorias. En cualquier otra página se cargan como memorias.
- Las descargas de URL se hacen de una en una y pueden tardar hasta 20 s cada una: usa `expect(...).to_be_visible(timeout=...)` con margen. Si borras el grado con descargas pendientes, fallan con `este grado ya no existe` y no se piden.
- «Ver fuente» de una URL abre la URL original. Un HTML guardado nunca se sirve como HTML.
