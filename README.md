# Tribunal PFG

Prepara las defensas de Proyecto Fin de Grado:

- Un **dashboard local** donde cargas las memorias en PDF.
- La skill **`leer-pfg`** trocea cada memoria, la resume por secciones con un modelo barato y escribe la ficha de lectura con el modelo potente.
- La skill **`grado-pfg`** contrasta cada memoria con los programas de las asignaturas de su grado: qué aplica de lo que se imparte y dónde va más allá.
- La skill **`preguntas-pfg`** genera preguntas para la defensa y después las clasifica por categorías.
- Un **lector** en el dashboard para leer la memoria y anotarla. La skill **`anotaciones-pfg`** responde las notas que dirijas al agente.

Funciona con Claude Code, Codex, Pi, Antigravity y OpenCode: las skills están en `.agents/skills/`. La IA prepara y el tribunal juzga: el sistema no pone notas.

Las memorias contienen datos personales y trabajo sin publicar. Se quedan en tu ordenador, en `pfgs/`, pero su contenido llega al proveedor del modelo que use tu agente: usa la herramienta de IA que autorice tu universidad.

## Instalación con la app

Es la forma más sencilla. Descarga el instalador de tu sistema desde la [última versión](https://github.com/rubensancor/tribunal-pfg/releases/latest):

| Sistema | Archivo |
|---|---|
| macOS con Apple Silicon (M1 o posterior) | `Tribunal-PFG-X.Y.Z-mac-arm64.dmg` |
| macOS con Intel | `Tribunal-PFG-X.Y.Z-mac-x64.dmg` |
| Windows | `Tribunal-PFG-X.Y.Z-win-x64.exe` |
| Linux | `Tribunal-PFG-X.Y.Z-linux-x86_64.AppImage` |

La app trae todo lo que necesita el dashboard: no hace falta terminal, ni uv, ni git. Solo te falta un agente: sigue el paso [4. Instala un agente](#4-instala-un-agente).

La app todavía no está firmada, así que la primera vez el sistema te avisa:

- **macOS**: abre el `.dmg` y arrastra Tribunal PFG a Aplicaciones. Al abrirla, macOS dice que no puede comprobar el desarrollador. Ve a **Ajustes del Sistema → Privacidad y seguridad**, baja hasta el aviso de Tribunal PFG y pulsa **Abrir igualmente**. En macOS 14 o anterior basta con clic derecho en la app → **Abrir**. Solo la primera vez.
- **Windows**: al ejecutar el instalador sale «Windows protegió su PC». Pulsa **Más información → Ejecutar de todos modos**. Se instala en tu usuario, sin permisos de administrador, y aparece en el menú Inicio.
- **Linux**: da permiso de ejecución al archivo (`chmod +x Tribunal-PFG-*.AppImage`, o en sus propiedades) y ábrelo. Si no arranca, instala FUSE: `sudo apt install libfuse2t64` en Ubuntu 24.04 o posterior, `libfuse2` en 22.04. Si se queja del sandbox, ábrelo con `--no-sandbox`.

La primera vez tarda un minuto, mientras descarga Python y pymupdf. Tus memorias, grados y ajustes se guardan en **Documentos/Tribunal PFG**. Es la carpeta del proyecto: abre ahí tu agente si quieres lanzar las skills a mano.

## Instalación con agente

Si ya tienes un agente (Claude Code, Codex u otro), deja que lo instale él. Abre el agente en la carpeta donde quieras guardar la herramienta y pega este texto.

```text
Instala Tribunal PFG en esta carpeta, paso a paso. Antes de instalar cualquier
cosa en el sistema, dime qué vas a instalar y con qué comando, y espera a que lo confirme.

1. Comprueba si uv está instalado (uv --version). Si falta, propón el instalador
   oficial de https://docs.astral.sh/uv/getting-started/installation/ para mi sistema.
2. Comprueba si git está instalado (git --version). Si falta, dime cómo instalarlo
   desde https://git-scm.com/downloads, o descarga el ZIP del repositorio.
3. Clona el repositorio: git clone https://github.com/rubensancor/tribunal-pfg.git tribunal-pfg
4. Entra en tribunal-pfg y arranca el dashboard en segundo plano: uv run dashboard/server.py
5. Abre http://127.0.0.1:8765 en el navegador.
6. Abre la pantalla Ajustes del dashboard y dime qué harnesses aparecen como
   instalados y cuáles faltan. No instales ninguno sin preguntarme.
```

Al terminar tendrás el dashboard abierto. Sigue en [Uso diario](#uso-diario).

## Instalación manual

Necesitas un terminal: en macOS, la app **Terminal**; en Windows, **PowerShell**. Copia cada comando, pégalo y pulsa Intro.

### 1. Instala uv

[uv](https://docs.astral.sh/uv/) se encarga de Python y de la única dependencia, pymupdf. Comprueba si ya lo tienes con `uv --version`. Si no, instálalo con el [instalador oficial](https://docs.astral.sh/uv/getting-started/installation/):

- macOS y Linux:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- Windows (PowerShell):

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Después, cierra el terminal y abre otro, para que encuentre `uv`.

### 2. Descarga Tribunal PFG

Con [git](https://git-scm.com/downloads):

```bash
git clone https://github.com/rubensancor/tribunal-pfg.git tribunal-pfg
cd tribunal-pfg
```

Sin git, descarga el ZIP desde la página del repositorio en GitHub (**Code → Download ZIP**), descomprímelo y entra en esa carpeta con `cd`. En Windows, lee antes [Windows](#windows).

### 3. Arranca el dashboard

Dentro de la carpeta `tribunal-pfg`:

```bash
uv run dashboard/server.py
```

La primera vez tarda un poco: uv descarga Python y pymupdf. Abre http://127.0.0.1:8765 en el navegador. Deja el terminal abierto mientras lo uses; para pararlo, pulsa Ctrl+C. Si quieres otro puerto, añádelo al final: `uv run dashboard/server.py 8770`.

Cada día, para volver a usarlo, abre un terminal, entra en la carpeta con `cd` y repite este paso.

### 4. Instala un agente

Las skills necesitan un agente, que aquí llamamos harness. Basta con uno. En **Ajustes** el dashboard muestra qué harnesses tienes, con su versión, y para los que faltan el comando de instalación de tu sistema y su página oficial. Después de instalar uno, pulsa **Comprobar de nuevo**.

Los comandos oficiales:

| Harness | macOS y Linux | Windows (PowerShell) |
|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/setup) | `curl -fsSL https://claude.ai/install.sh \| bash` | `irm https://claude.ai/install.ps1 \| iex` |
| [Codex](https://learn.chatgpt.com/docs/codex/cli) | `curl -fsSL https://chatgpt.com/codex/install.sh \| sh` | mira su página |
| [Pi](https://pi.dev) | `curl -fsSL https://pi.dev/install.sh \| sh` | `powershell -c "irm https://pi.dev/install.ps1 \| iex"` |
| [Antigravity](https://antigravity.google/docs/getting-started?tab=cli) | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` | `irm https://antigravity.google/cli/install.ps1 \| iex` |
| [OpenCode](https://opencode.ai/docs) | `curl -fsSL https://opencode.ai/v2/install \| bash` | sin instalador: descarga el binario de su página |

Con Pi, instala también [pi-subagents](https://github.com/tintinweb/pi-subagents) para que los lectores usen un modelo barato. Con Antigravity, revisa los permisos en [Detalles de cada harness](#detalles-de-cada-harness).

## Uso diario

1. Arrastra los PDF al dashboard.
2. Cada tarjeta muestra el siguiente paso. Pulsa su botón, como **Leer la memoria con Claude Code**, o copia el comando y pégalo en tu agente, abierto en la carpeta del proyecto (`tribunal-pfg`, o `Documentos/Tribunal PFG` si usas la app):
   - `usa la skill leer-pfg con el PFG <id>`
   - `usa la skill grado-pfg con el PFG <id>`, si has cargado programas en **Grados**
   - `usa la skill preguntas-pfg con el PFG <id>`
3. El dashboard se actualiza solo. Imprime la pestaña Preguntas para llevarla a la defensa.

Si marcas **Leer y preguntar al cargar**, cada PDF que subas se lee, se contrasta con su grado si hay programas y genera sus preguntas, con los harnesses de Ajustes.

Usa el modelo más capaz como modelo principal de la sesión: Opus, GPT-6 o Gemini Pro.

### Ejecutar desde el dashboard

El botón de cada tarjeta lanza el agente en modo no interactivo y la tarjeta muestra el avance. En **Ajustes** eliges el harness, el modelo y el esfuerzo de razonamiento de cada fase; se guardan en `config/ejecucion.json`, que no se sube a git. El registro de cada ejecución queda en `pfgs/<id>/ejecuciones/`. Al parar el dashboard se detienen las ejecuciones en curso.

### Leer y anotar la memoria

Pulsa **Leer memoria** o cualquier enlace `pág. N` del detalle: la memoria se abre a la derecha, en esa página, y la ficha o la pregunta sigue a la vista. Con ⌘ o Ctrl más clic se abre el visor del navegador.

Selecciona texto y elige qué hacer con él:

| Botón | Para quién | Dónde se guarda |
|---|---|---|
| **Resaltar** o **Nota personal** | solo para ti; ningún agente la lee | `notas-personales.json` |
| **Preguntar al agente** | la skill `anotaciones-pfg`, que responde con páginas | `anotaciones.json` → `respuestas.json` |
| **Para las preguntas** | la skill `preguntas-pfg`, como duda del tribunal | `anotaciones.json` |

**Nota en esta página** sirve para figuras y tablas. Puedes cambiar el tipo de una nota en cualquier momento. **Enviar N preguntas al agente** lanza `anotaciones-pfg` con el harness de la fila «Respuestas a tus notas» de Ajustes; si editas una nota respondida, vuelve a quedar pendiente.

### Programas del grado

En **Grados → Nuevo grado** escribe el nombre exacto de la titulación, como aparece en la portada de las memorias, por ejemplo «Grado en Ingeniería Informática». Un doble grado es un grado aparte, con su propia lista de asignaturas. Después añade las guías docentes de sus asignaturas en el mismo panel:

- **Archivos**: suelta o elige PDF, `.txt` o `.html` (la página de la guía guardada desde el navegador).
- **URL**: una por línea. Al pulsar **Descargar** el dashboard las pone en cola y las descarga en segundo plano, de una en una (http o https también tras las redirecciones, 20 s y 5 MB como máximo por guía). Debajo muestra el estado de cada URL y el motivo de las que fallen. Si la URL trae `_codAsignatura`, como las de Deusto, esa asignatura sustituye a la anterior con el mismo código.
- **Pegar texto**: con un nombre opcional; sin nombre, se usa la primera línea.

Carga las guías de la promoción de los PFG: de cada grado se guarda una sola versión. Los programas se leen con un modelo barato la primera vez que se contrasta un PFG de ese grado. Tras la lectura de una memoria, el siguiente paso es **Contrastar con el grado**: un agente barato identifica la titulación en la portada y el modelo principal escribe la pestaña **Grado**, con lo que va más allá de lo que se imparte y lo que aplica, cada cosa con su página y su asignatura y tema. Es un mapa para el tribunal, no una valoración, y solo lista lo que el PFG usa. Si cambias los programas después, la pestaña lo avisa y ofrece **Rehacer el contraste**. Si no se identifica el grado, el PFG sigue a las preguntas.

Todo queda en `grados/`, que no se sube a git.

### Categorías

Están en `config/categorias.json`; edítalas libremente. Las preguntas se generan **sin conocer las categorías** y un agente aparte las clasifica después. Así no aparece una pregunta por categoría solo porque la categoría existe. Que una categoría se quede vacía es normal.

## Actualizar

Al arrancar, el dashboard pregunta a GitHub cuál es la última versión publicada. Esa consulta solo envía tu IP a GitHub, nada de tus memorias. Si hay una versión nueva, **Ajustes** la muestra con un enlace a las novedades y el botón **Actualizar**. El botón baja la versión con git y reinicia el dashboard. Para que funcione, no puede haber ninguna ejecución en curso ni nada en la cola. Tus memorias, grados y ajustes no se tocan. Si has editado un archivo que la versión nueva también cambia, como `config/categorias.json`, no actualiza y te dice cuál es. **Comprobar de nuevo** vuelve a consultar.

Con la app, Ajustes te lleva a la página de la versión: descarga el instalador nuevo e instálalo encima. Tus memorias, grados y ajustes siguen en `Documentos/Tribunal PFG`. Si has editado un archivo que la versión nueva también cambia, como `config/categorias.json`, la app conserva el tuyo y te avisa al abrirse.

Si descargaste el ZIP, Ajustes te lleva a la página de la versión. Descarga el ZIP nuevo y copia `pfgs/`, `grados/` y `config/ejecucion.json` a la carpeta nueva.

Si instalaste antes de que existiera el botón, actualiza una vez a mano: `git pull` dentro de la carpeta `tribunal-pfg`, o pídeselo a tu agente. Después reinicia el dashboard.

## Privacidad

Las memorias y tus notas se quedan en `pfgs/`, que no se sube a git. Las notas personales no las lee ningún agente. Para quitar una, pulsa **Borrar** en su detalle; para quitar varias, márcalas en la lista y pulsa **Borrar seleccionados**. En los dos casos se borran el PDF y todo lo generado a partir de él. El dashboard solo escucha en `127.0.0.1`. El contenido sí llega al proveedor del modelo que use tu agente: usa la herramienta de IA que autorice tu universidad.

## Detalles de cada harness

### Permisos al ejecutar desde el dashboard

| Harness | Se lanza con | Permisos |
|---|---|---|
| Claude Code | `claude -p … --permission-mode dontAsk` | solo `uv run scripts/pfg.py` y `python3 -m json.tool`; el resto se deniega |
| Antigravity | `agy -p … --mode accept-edits` | los de tu `settings.json` de agy: añade `"command(uv run scripts/pfg.py)"` y `"command(python3 -m json.tool)"` a `permissions.allow`, o terminará sin hacer nada |
| Codex | `codex exec -c default_permissions="tribunal" …` | cualquier comando, pero en su sandbox: sin red, sin leer tus notas personales y escribiendo solo en el proyecto y en la caché de uv; el perfil `tribunal` se fija con `-c` |
| Pi | `pi -p … --no-session --approve` | ninguno: puede ejecutar cualquier comando |
| OpenCode | `opencode run --standalone --auto -m <modelo>#<esfuerzo>` | solo `uv run scripts/pfg.py` y `python3 -m json.tool`, sin web, sin archivos fuera del proyecto y sin leer tus notas personales (por eso tampoco usa grep); se fijan en `OPENCODE_CONFIG_CONTENT` |

Las memorias son texto ajeno que el agente lee: con Pi, una instrucción escondida en un PDF podría ejecutar comandos. Para memorias que no conoces, prefiere Claude Code.

OpenCode solo admite los modelos gratuitos de OpenCode Zen que no entrenan con lo que reciben: `opencode/glm-5.3-flash-free` (el de por defecto), `opencode/deepseek-v4.1-flash-free` y `opencode/beam-free`. Los demás gratuitos pueden usar los datos para mejorar el modelo o piden no enviarles datos personales ([condiciones de Zen](https://opencode.ai/docs/zen/)).

### Modelos baratos

| Harness | Dónde se fija |
|---|---|
| Claude Code | `.agents/agents/*.md` (`model: sonnet` / `haiku`), visible a través de `.claude/agents` |
| Pi + pi-subagents | los mismos `.agents/agents/*.md` |
| Codex | `.codex/agents/*.toml` (`model = "gpt-6-luna"`) |
| OpenCode | `.opencode/agents/*.md`: heredan el modelo gratuito de la sesión |
| Antigravity | sin subagentes: el agente principal lee las secciones una a una |

## Windows

`.claude/skills` y `.claude/agents` son enlaces simbólicos. Si git los clona como archivos de texto, activa `git config core.symlinks true` (requiere el modo desarrollador) o copia esas carpetas desde `.agents/`. Si descargaste el ZIP y las skills no aparecen en tu agente, haz lo mismo: copia esas carpetas desde `.agents/`. La app ya trae esas carpetas.

## Desarrollo

```bash
uv run tests/test_pfg.py
uv run tests/test_dashboard.py
uv run tests/test_instalar.py
```

El workflow **Tests** los pasa en Linux, macOS y Windows en cada PR y en `main`.

La app de escritorio necesita Node: `npm install` y `npx electron .` para probarla, y `npm run dist -- --mac --win --linux` para dejar los instaladores en `dist/`.

Para publicar una versión, sube el número en `VERSION` (semver `0.x`), haz commit en `main` y ejecuta `git tag vX.Y.Z && git push origin main vX.Y.Z && gh release create vX.Y.Z --generate-notes`. Al publicarse la release, el workflow **Instaladores** construye los cuatro instaladores en un runner de macOS y los cuelga en ella; tarda unos minutos y falla si la tag no coincide con `VERSION`. El botón Actualizar avanza hasta esa tag, no hasta el último commit de `main`. Cada versión debe seguir leyendo los `pfgs/` de las anteriores.

## Licencia

[MIT](LICENSE). La dependencia pymupdf tiene su propia licencia, AGPL-3.0.
