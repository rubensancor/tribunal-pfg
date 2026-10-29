# Tribunal PFG

Prepara las defensas de Proyecto Fin de Grado:

- Un **dashboard local** donde cargas las memorias en PDF.
- La skill **`leer-pfg`** trocea cada memoria, la resume por secciones con un modelo barato y escribe la ficha de lectura con el modelo potente.
- La skill **`preguntas-pfg`** genera preguntas para la defensa y después las clasifica por categorías.

Funciona con Claude Code, Codex, Pi y Antigravity: las skills están en `.agents/skills/`. La IA prepara y el tribunal juzga: el sistema no pone notas.

## Requisitos

- [uv](https://docs.astral.sh/uv/), que se encarga de Python y de la única dependencia, pymupdf.
- Uno de los agentes: Claude Code, Codex, Pi (con [pi-subagents](https://github.com/tintinweb/pi-subagents) para que los lectores usen un modelo barato) o Antigravity.

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

Usa el modelo más capaz como modelo principal de la sesión: Opus, GPT-6 o Gemini Pro.

## Ejecutar desde el dashboard

En vez de copiar el comando, puedes pulsar **Ejecutar con …**: el dashboard lanza el agente en modo no interactivo y la tarjeta muestra el avance. En **Ajustes** eliges el harness, el modelo y el esfuerzo de razonamiento de cada fase; se guardan en `config/ejecucion.json`, que no se sube a git. El registro de cada ejecución queda en `pfgs/<id>/ejecuciones/`. Al parar el dashboard se detienen las ejecuciones en curso.

| Harness | Se lanza con | Permisos |
|---|---|---|
| Claude Code | `claude -p … --permission-mode dontAsk` | solo `uv run scripts/pfg.py` y `python3 -m json.tool`; el resto se deniega |
| Antigravity | `agy -p … --mode accept-edits` | los de tu `settings.json` de agy: añade `"command(uv run scripts/pfg.py)"` y `"command(python3 -m json.tool)"` a `permissions.allow`, o terminará sin hacer nada |
| Pi | `pi -p … --no-session --approve` | ninguno: puede ejecutar cualquier comando |

Las memorias son texto ajeno que el agente lee: con Pi, una instrucción escondida en un PDF podría ejecutar comandos. Para memorias que no conoces, prefiere Claude Code.

## Modelos baratos por harness

| Harness | Dónde se fija |
|---|---|
| Claude Code | `.agents/agents/*.md` (`model: sonnet` / `haiku`), visible a través de `.claude/agents` |
| Pi + pi-subagents | los mismos `.agents/agents/*.md` |
| Codex | `.codex/agents/*.toml` (`model = "gpt-6-luna"`) |
| Antigravity | sin subagentes: el agente principal lee las secciones una a una |

## Categorías

Están en `config/categorias.json`; edítalas libremente. Las preguntas se generan **sin conocer las categorías** y un agente aparte las clasifica después. Así no aparece una pregunta por categoría solo porque la categoría existe. Que una categoría se quede vacía es normal.

## Privacidad

Las memorias se quedan en `pfgs/`, que no se sube a git. Para quitar una, pulsa **Borrar** en su detalle: se borran el PDF y todo lo generado a partir de él. El dashboard solo escucha en `127.0.0.1`. El contenido sí llega al proveedor del modelo que use tu agente: usa la herramienta de IA que autorice tu universidad.

## Windows

`.claude/skills` y `.claude/agents` son enlaces simbólicos. Si git los clona como archivos de texto, activa `git config core.symlinks true` (requiere el modo desarrollador) o copia esas carpetas desde `.agents/`.

## Desarrollo

```bash
uv run tests/test_pfg.py
uv run tests/test_dashboard.py
```
