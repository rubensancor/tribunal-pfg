# Mapa de features

Lo que el docente puede hacer en el dashboard, camino a camino, con lo que debe ver. Es la guía de `tests/test_e2e.py` y la rúbrica para comprobar un cambio a mano. Al lado de cada camino, el test que lo cubre: `e2e` (navegador), `http` (`test_dashboard.py`), `instalar` (`test_instalar.py`) o nada todavía.

## A. Lista de PFG (`#/`)

- Sin PFG se ve «Aún no hay ningún PFG». `e2e`
- «Cargar PFG», o arrastrar, con uno o varios PDF: «N PDF cargados» y una fila por PDF. `e2e` (uno, con el selector)
- Un archivo que no es PDF o pasa de 100 MB: aviso y no se carga.
- Con «Leer y preguntar al cargar»: el PFG entra en la cola, se lee, se pregunta y la fila acaba en «Listo» con «Ver preguntas →». `e2e`
- El resumen cuenta los PFG por leer, en preparación y listos. `e2e`
- Cola de preparación: puesto de cada PFG, «Sacar» uno, «Vaciar cola». `http`
- Seleccionar varios y borrarlos, con confirmación; no se borra uno con un agente en marcha. `http`

## B. Ficha de un PFG (`#/<id>`)

- La cabecera con el estado, el estudiante y la titulación. `e2e`
- «Siguiente paso»: lanzar la fase que falta con el harness de Ajustes, verla en curso y detenerla. `http`
- Si la ejecución falla o no avanza: el registro abierto, «Copiar registro» y «Enviar registro por correo».
- Pestañas: ficha de lectura `e2e`, secciones, grado y preguntas `e2e`; filtrar las preguntas por categoría.
- Cada afirmación lleva su página y abre el lector en ella.
- Un JSON no válido se enseña como error, sin romper la página.

## C. Lector

- «Leer memoria» abre el lector; Esc lo cierra. `e2e`
- ←/→ y los botones cambian de página; «PDF n/N» y la página impresa. `e2e` (botón)
- Zoom y «Ocultar la ficha».
- Seleccionar texto abre «Resaltar», «Nota personal», «Preguntar al agente» y «Para las preguntas»; la nota queda con su cita y su página. `e2e` (Preguntar al agente)
- «Nota en esta página», sin selección.
- Editar y borrar una nota; sobrevive a cerrar y recargar. `e2e` (recargar)
- «Enviar N preguntas al agente» y ver la respuesta bajo la nota. `e2e`
- Las notas personales no llegan a ningún agente. `http`

## D. Grados (`#grados`, `#grados/<id>`)

- Crear un grado con nombre e importar uno de Deusto. `http`
- Subir programas (PDF, txt, html), pegar URL y ver cómo bajan una a una. `http`
- Borrar un programa o el grado. `http`
- Contrastar un PFG con su grado desde la pestaña Grado. `http`

## E. Ajustes (`#ajustes`)

- Harness, modelo y esfuerzo por fase; solo Antigravity salvo `todos_los_harnesses`. `http`
- «Comprobar de nuevo» vuelve a detectar los harnesses. `http`
- Versión y «Actualizar», que reinicia el dashboard. `http`

## F. Onboarding de Antigravity

- Sin agy: «Prepara Antigravity», con el paso 1 activo. `http`
- Instalar, iniciar sesión, «Comprobar de nuevo», «Configurar después». `http`
- Con agy y sesión, la lista directamente. `e2e`

## G. App de escritorio

- El primer arranque copia el código a `Documentos/Tribunal PFG` y conserva lo que cambió el docente. `instalar`
- La ventana abre el dashboard; cerrarla para el servidor; tras actualizar, vuelve a arrancar.
