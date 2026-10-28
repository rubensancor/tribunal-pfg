# CLI pfg.py

`scripts/pfg.py` trocea la memoria en secciones, valida los JSON que escriben los agentes y renderiza páginas a PNG. Las skills la llaman, y el docente o el agente pueden ejecutarla directamente. El dashboard muestra lo que produce.

## Sub-features

- `cli-trocear`: `memoria.pdf` → `secciones/indice.json` + `NN.txt` con marcas `[[pdf:N pág:M]]`.
- `cli-trocear-repetido`: se niega a trocear dos veces.
- `cli-validar`: imprime `ok` y sale con 0, o lista los problemas y sale con 1.
- `cli-imagen`: `paginas/pNNN.png` de una página.
- `cli-id-invalido`: rechaza ids que no cumplen `[a-z0-9-]+` o que no tienen PDF.

## How to get to it (user POV)

- `uv run scripts/pfg.py trocear|validar <id>` y `uv run scripts/pfg.py imagen <id> <página>`. En verificación, siempre con la copia: `P="$($V estado app)/scripts/pfg.py"`.

## Driving it with verificar.py

Preconditions:

- `memoria-demo-verificacion` subido por la UI y sin trocear.
- `P="$($V estado app)/scripts/pfg.py"` y `D="$($V estado pfgs)/memoria-demo-verificacion"`.
- Guarda cada comando con su salida y su código: `{ uv run "$P" … ; echo "exit $?"; } > "$($V estado evidencia)/cli-<sub>.txt" 2>&1`.

- **Trocear.** `uv run "$P" trocear memoria-demo-verificacion` imprime `3 secciones en …` y sale con 0. `$D/secciones/indice.json` tiene 3 entradas y `$D/secciones/00.txt` contiene `[[pdf:1 pág:i]]`. En el dashboard, la tarjeta pasa a `Leyendo` con `0/3 secciones leídas`.
- **Trocear dos veces.** El mismo comando sale con 1 y el mensaje `memoria-demo-verificacion ya está troceado`.
- **Validar incompleto.** `uv run "$P" validar memoria-demo-verificacion` sale con 1 y lista `secciones/00.json: falta`.
- **Validar completo.** `$V fase memoria-demo-verificacion clasificadas` termina con `ok` y código 0. Para el caso negativo, añade `"categoria": "x"` a una pregunta de `$D/preguntas.json`: `validar` sale con 1 y el mensaje `no debe llevar categoría`.
- **Imagen.** `uv run "$P" imagen memoria-demo-verificacion 3` imprime la ruta `$D/paginas/p003.png`, que existe y es un PNG. Con la página `999` sale con 1 y el mensaje `la página 999 no existe`.
- **Id inválido.** `uv run "$P" validar No_Valido` sale con 1 y el mensaje `id no válido: No_Valido`.

## Gotchas

- `uv run scripts/pfg.py` sin la copia actúa sobre el `pfgs/` real del repo. No lo hagas.
- `trocear` usa los marcadores del PDF. `$V pdf` crea tres capítulos más los preliminares, que se fusionan con la introducción por ser cortos. Por eso salen 3 secciones, no 4.
- La primera ejecución tarda: uv instala pymupdf.
