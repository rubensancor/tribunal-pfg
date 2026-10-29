# Tribunal PFG

Prepara las defensas de Proyecto Fin de Grado:

- Un **dashboard local** donde cargas las memorias en PDF.
- La skill **`leer-pfg`** trocea cada memoria, la resume por secciones con un modelo barato y escribe la ficha de lectura con el modelo potente.
- La skill **`preguntas-pfg`** genera preguntas para la defensa y después las clasifica por categorías.
- Un **lector** en el dashboard para leer la memoria y anotarla. La skill **`anotaciones-pfg`** responde las notas que dirijas al agente.

Funciona con Claude Code, Codex, Pi, Antigravity y OpenCode: las skills están en `.agents/skills/`. La IA prepara y el tribunal juzga: el sistema no pone notas.

## Requisitos

- [uv](https://docs.astral.sh/uv/), que se encarga de Python y de la única dependencia, pymupdf.
- Uno de los agentes: Claude Code, Codex, Pi (con [pi-subagents](https://github.com/tintinweb/pi-subagents) para que los lectores usen un modelo barato), Antigravity u OpenCode.

## Uso

```bash
git clone <repo> tribunal-pfg && cd tribunal-pfg
uv run dashboard/server.py        # abre http://127.0.0.1:8765
```

1. Arrastra los PDF al dashboard.
2. Cada tarjeta muestra el siguiente paso. Cópialo y pégalo en tu agente, abierto en esta carpeta:
   - `usa la skill leer-pfg con el PFG <id>`
   - `usa la skill preguntas-pfg con el PFG <id>`
3. El dashboard se actualiza solo. Imprime la pestaña Preguntas para llevarla a la defensa.

### Leer y anotar la memoria

Pulsa **Leer memoria** o cualquier enlace `pág. N` del detalle: la memoria se abre a la derecha, en esa página, y la ficha o la pregunta sigue a la vista. Con ⌘ o Ctrl más clic se abre el visor del navegador.

Selecciona texto y elige qué hacer con él:

| Botón | Para quién | Dónde se guarda |
|---|---|---|
| **Resaltar** o **Nota personal** | solo para ti; ningún agente la lee | `notas-personales.json` |
| **Preguntar al agente** | la skill `anotaciones-pfg`, que responde con páginas | `anotaciones.json` → `respuestas.json` |
| **Para las preguntas** | la skill `preguntas-pfg`, como duda del tribunal | `anotaciones.json` |

**Nota en esta página** sirve para figuras y tablas. Puedes cambiar el tipo de una nota en cualquier momento. **Enviar N preguntas al agente** lanza `anotaciones-pfg` con el harness de la fila «Respuestas a tus notas» de Ajustes; si editas una nota respondida, vuelve a quedar pendiente.

Usa el modelo más capaz como modelo principal de la sesión: Opus, GPT-6 o Gemini Pro.

## Ejecutar desde el dashboard

En vez de copiar el comando, puedes pulsar **Ejecutar con …**: el dashboard lanza el agente en modo no interactivo y la tarjeta muestra el avance. En **Ajustes** eliges el harness, el modelo y el esfuerzo de razonamiento de cada fase; se guardan en `config/ejecucion.json`, que no se sube a git. El registro de cada ejecución queda en `pfgs/<id>/ejecuciones/`. Al parar el dashboard se detienen las ejecuciones en curso.

| Harness | Se lanza con | Permisos |
|---|---|---|
| Claude Code | `claude -p … --permission-mode dontAsk` | solo `uv run scripts/pfg.py` y `python3 -m json.tool`; el resto se deniega |
| Antigravity | `agy -p … --mode accept-edits` | los de tu `settings.json` de agy: añade `"command(uv run scripts/pfg.py)"` y `"command(python3 -m json.tool)"` a `permissions.allow`, o terminará sin hacer nada |
| Pi | `pi -p … --no-session --approve` | ninguno: puede ejecutar cualquier comando |
| OpenCode | `opencode run --standalone --auto -m <modelo>#<esfuerzo>` | solo `uv run scripts/pfg.py` y `python3 -m json.tool`, sin web ni archivos fuera del proyecto; se fijan en `OPENCODE_CONFIG_CONTENT` |

Las memorias son texto ajeno que el agente lee: con Pi, una instrucción escondida en un PDF podría ejecutar comandos. Para memorias que no conoces, prefiere Claude Code.

OpenCode solo admite los modelos gratuitos de OpenCode Zen que no entrenan con lo que reciben: `opencode/glm-5.3-flash-free` (el de por defecto), `opencode/deepseek-v4.1-flash-free` y `opencode/beam-free`. Los demás gratuitos pueden usar los datos para mejorar el modelo o piden no enviarles datos personales ([condiciones de Zen](https://opencode.ai/docs/zen/)).

## Modelos baratos por harness

| Harness | Dónde se fija |
|---|---|
| Claude Code | `.agents/agents/*.md` (`model: sonnet` / `haiku`), visible a través de `.claude/agents` |
| Pi + pi-subagents | los mismos `.agents/agents/*.md` |
| Codex | `.codex/agents/*.toml` (`model = "gpt-6-luna"`) |
| OpenCode | `.opencode/agents/*.md`: heredan el modelo gratuito de la sesión |
| Antigravity | sin subagentes: el agente principal lee las secciones una a una |

## Categorías

Están en `config/categorias.json`; edítalas libremente. Las preguntas se generan **sin conocer las categorías** y un agente aparte las clasifica después. Así no aparece una pregunta por categoría solo porque la categoría existe. Que una categoría se quede vacía es normal.

## Privacidad

Las memorias y tus notas se quedan en `pfgs/`, que no se sube a git. Las notas personales no las lee ningún agente. Para quitar una, pulsa **Borrar** en su detalle; para quitar varias, márcalas en la lista y pulsa **Borrar seleccionados**. En los dos casos se borran el PDF y todo lo generado a partir de él. El dashboard solo escucha en `127.0.0.1`. El contenido sí llega al proveedor del modelo que use tu agente: usa la herramienta de IA que autorice tu universidad.

## Windows

`.claude/skills` y `.claude/agents` son enlaces simbólicos. Si git los clona como archivos de texto, activa `git config core.symlinks true` (requiere el modo desarrollador) o copia esas carpetas desde `.agents/`.

## Desarrollo

```bash
uv run tests/test_pfg.py
uv run tests/test_dashboard.py
```
