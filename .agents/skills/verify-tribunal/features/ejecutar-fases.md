# Ejecutar fases y ajustes

El docente elige en Ajustes qué harness (Claude Code, Antigravity o Pi), qué modelo y qué esfuerzo de razonamiento ejecuta cada fase. Después pulsa el botón de la fase («Leer la memoria con …», «Generar las preguntas con …» o «Clasificar las preguntas con …») en la tarjeta o en el detalle, y el dashboard lanza el agente en modo no interactivo. La tarjeta muestra la ejecución en curso con un botón «Detener». Al terminar se ve el resultado, y en el detalle aparece el registro de la ejecución.

## Sub-features

- `ajustes-guardar`: guardar el harness y el modelo de cada fase en `config/ejecucion.json`.
- `ajustes-validar`: un modelo que empieza por `-` o lleva espacios se rechaza con `modelo no válido`.
- `ajustes-esfuerzo`: el desplegable «Esfuerzo» ofrece los niveles del harness y del modelo (`--effort` en claude y agy, `--thinking` en pi). Con agy y un modelo que no lo admite (`claude-opus-4-6-thinking`) queda desactivado con `este modelo no lo admite`. La API rechaza un nivel que no toca con `no admite el esfuerzo`.
- `ajustes-avisos`: la lista de harnesses avisa si falta un binario o, en el caso de agy, la regla de permisos.
- `ejecutar-lanzar`: «Leer la memoria con <harness>» lanza la fase siguiente; la tarjeta pasa a `Ejecutando: <fase> con <harness> (<modelo>, esfuerzo <nivel>)`.
- `ejecutar-terminar`: la fase avanza (Leído, Preguntas sin clasificar o Listo) y el botón pasa a la fase siguiente.
- `ejecutar-sin-avance`: si sale con 0 sin que el PFG cambie de fase, aparece `Terminó sin completar la fase` y el registro se abre solo.
- `ejecutar-detener`: «Detener» mata el grupo de procesos y la tarjeta muestra `Detenida`.
- `ejecutar-origen`: un POST con `Origin` de otra web recibe 403.

## How to get to it (user POV)

- Pulsar «Ajustes» en la cabecera (`#ajustes`).
- Pulsar «<acción> con <harness>» en una tarjeta o en el bloque «Siguiente paso» del detalle.
- Pulsar «Detener» mientras se ejecuta.

## Driving it with verificar.py

Preconditions:

- `$V doctor` sin fallos. La copia incluye `.agents/`, `AGENTS.md` y los enlaces de `.claude/`, porque los agentes los necesitan.
- `claude`, `agy` y `pi` en el PATH y con sesión iniciada. Los recorridos gastan tokens reales: usa modelos baratos (`haiku`, `openai-codex/gpt-6-luna`).
- Memorias sintéticas subidas por la UI (ver [subir-pfg](./subir-pfg.md)).

- **Guardar.** En `#ajustes`, `page.get_by_label("Harness de Lectura de la memoria").select_option("claude")` y `page.get_by_label("Modelo de Lectura de la memoria").fill("haiku")`. Haz lo mismo con «Preguntas para la defensa» (`pi`, `openai-codex/gpt-6-luna`) y pulsa `Guardar`. El estado es `Ajustes guardados.` y `json.loads((pfgs.parent / "config" / "ejecucion.json").read_text())` contiene los dos valores.
- **Esfuerzo.** Con `claude`, `get_by_label("Esfuerzo de Lectura de la memoria")` ofrece `low`…`max`. Cambia a `agy` y quedan `low`, `medium` y `high`. Escribe `claude-opus-4-6-thinking` en el modelo y el desplegable se desactiva. Tras guardar, `ejecucion.json` lleva `esfuerzo`, y la primera línea del registro de una ejecución lleva `--effort <nivel>`.
- **Validar.** Rellena el modelo con `--dangerously-skip-permissions` y guarda. El estado contiene `modelo no válido` y el archivo no cambia.
- **Lanzar y terminar.** En la tarjeta, `get_by_role("button", name="Leer la memoria con Claude Code").click()`. Aparece `Ejecutando: Lectura de la memoria con Claude Code (haiku)` y el botón `Detener`. Espera con `page.get_by_text("Ejecutando:").wait_for(state="detached", timeout=900_000)`. La insignia pasa a `Leído` y `uv run "$($V estado app)/scripts/pfg.py" validar <id>` imprime `ok`. Luego pulsa «Generar las preguntas con Pi». Con la memoria sintética, el resultado esperado es `Terminó sin completar la fase` y un registro en el que el agente se niega a inventar preguntas (ver Gotchas).
- **Detener.** Lanza otra memoria y pulsa `Detener`. El estado es `Ejecución detenida.`, la tarjeta muestra `Detenida: …` y `pgrep -fl "<id>"` no encuentra procesos.
- **Sin avance.** Pon agy en la lectura y ejecútalo sin la regla de permisos. La tarjeta muestra `Terminó sin completar la fase: Lectura de la memoria con Antigravity (agy)` y en el detalle `pre.log` contiene `auto-denied`.
- **Origen.** `page.request.post(url + "/api/config", data="{}", headers={"Origin": "https://evil.example"})` devuelve 403.

## Gotchas

- La configuración y las ejecuciones son de la copia desechable. `config/ejecucion.json` del repo no se toca y está en `.gitignore`.
- El estado de las ejecuciones vive en la memoria del servidor: al reiniciarlo desaparece el bloque de ejecución, pero los archivos y los registros de `pfgs/<id>/ejecuciones/` siguen ahí.
- `claude -p` y `pi -p` solo escriben en el registro al terminar. Mientras tanto, el avance se ve en el contador de secciones.
- agy sale con 0 cuando se le deniega un comando. Por eso el resultado se deduce de si el PFG avanzó de fase, no del código de salida.
- El servidor lee `index.html` del disco en cada petición, pero su propio código solo al arrancar. Un dashboard arrancado antes de actualizar enseña el enlace Ajustes y responde 404 a `/api/config`. La página muestra entonces `El dashboard no ha podido cargar esta página` y sugiere reiniciar. Para reproducirlo, usa `page.route("**/api/config", lambda r: r.fulfill(status=404, content_type="application/json", body='{"error": "no encontrado"}'))`.
- agy valida la pareja modelo y esfuerzo: los modelos con el nivel en el nombre (`gemini-3.8-flash-high`) y los de Claude o GPT-OSS rechazan `--effort`. Si agy añade modelos, actualiza su tabla `modelos` en `dashboard/server.py` (pruébalos con `agy -p ok --model <m> --effort <nivel>`).
- `claude` atrapa el SIGTERM de «Detener» y sale con 143, así que su tarjeta muestra `Falló: … código 143` en vez de `Detenida`. agy sí muestra `Detenida`.
- No pruebes agy con `--dangerously-skip-permissions`: el dashboard no lo usa nunca.
- `$V pdf` solo tiene texto de relleno. `leer-pfg` termina con una ficha casi vacía, pero `preguntas-pfg` se niega con razón a inventar preguntas, así que con estos datos la fase de preguntas no llega a `Listo`. Para recorrerla entera hace falta una memoria sintética con contenido real, que la semilla aún no tiene.
