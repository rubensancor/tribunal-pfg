---
name: verify
description: Comprueba un cambio del Tribunal PFG en el dashboard de verdad antes de hacer commit. Arranca el servidor en una copia temporal con un agy falso, recorre los caminos de tests/features.md en Chromium, saca capturas y las mira. Úsala antes de cada commit que toque dashboard/, scripts/ o app/, o cuando pidan verificar, probar en el navegador o ver capturas del dashboard.
---

# Verify

Los tests dicen si algo se rompió; las capturas, si lo que ve el docente tiene sentido. Haz las dos cosas. Todo corre en una copia temporal con un agy falso: no arranques el dashboard sobre `pfgs/` ni con un agy de verdad, porque ahí hay memorias de estudiantes.

## 1. Los tests

```bash
uv run tests/test_pfg.py && uv run tests/test_instalar.py && uv run tests/test_dashboard.py
```

Si falla uno, arregla el código, no el test, salvo que el cambio sea justo lo que el test comprobaba.

## 2. El E2E con capturas

Crea una carpeta para las capturas fuera del repo (el scratchpad, si tienes uno) y ejecuta:

```bash
uv run tests/test_e2e.py --capturas <carpeta>
```

Termina con «E2E OK». Si falla, la traza dice qué paso y qué esperaba; la última captura que llegó a guardarse es el último paso que fue bien.

Abre cada PNG en orden (`01-lista-vacia.png`, `02-lista-lista.png`…: el número es el orden del recorrido) con tu herramienta de leer imágenes y míralas como un docente:

- ¿Se ve lo que el paso dice en `tests/features.md`?
- ¿Hay textos cortados o montados, zonas vacías donde debería haber contenido, mensajes de error o algo que no cuadra con tu cambio?

Una captura en blanco puede ser solo que no le dio tiempo a cargar. Antes de darlo por fallo, mira en `tests/test_e2e.py` si el paso espera a ese contenido (`expect(...)` o `wait_for_function`); si no espera, añade la espera al test.

## 3. Lo que tu cambio toca y el E2E no recorre

Busca en `tests/features.md` los caminos de tu cambio. Si alguno no lleva `e2e` (lleva `http`, `instalar` o ninguna marca, que es que no lo cubre ningún test), compruébalo a mano:

```bash
uv run tests/test_e2e.py --dejar
```

Lánzalo en segundo plano con la salida a un archivo. Tras «E2E OK» (10–30 s) imprime «Dashboard de prueba en http://127.0.0.1:<puerto>…»: esa es la URL, con un puerto distinto cada vez. Ahí hay un PFG listo, «Caché distribuida para el campus», con una nota en la página 2.

Recorre el camino con la herramienta de navegador que tengas y saca capturas. Si no tienes ninguna, escribe un script de Playwright fuera del repo y ejecútalo con `uv run --with playwright python <script>`. Copia de `tests/test_e2e.py` cómo se encuentran los botones y los textos (`get_by_role`, `get_by_label`): son los mismos.

Para cerrarlo, para la tarea en segundo plano (o Ctrl+C); el servidor se cierra solo cuando muere el test.

Si el camino es estable y lo vas a querer comprobar otra vez, añádelo a `tests/test_e2e.py` y pon la marca `e2e` al final de su línea en `tests/features.md`.

## 4. Cuándo parar

- Si algo sigue fallando después de tres intentos de arreglarlo, para y cuéntaselo a la persona: qué falla, la traza y la captura.
- Un test que falla a veces no se arregla con esperas fijas ni repitiéndolo hasta que pase. Busca la causa; si no la encuentras, dilo.
- Al terminar, di qué has comprobado (tests, E2E, caminos a mano), en qué sistema, y qué has dejado sin comprobar.
