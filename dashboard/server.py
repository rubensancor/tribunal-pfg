#!/usr/bin/env python3
"""Dashboard local del tribunal PFG. Solo stdlib. Uso: uv run dashboard/server.py [puerto]"""
import http.client
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import pfg  # noqa: E402  sin pymupdf: solo lo importan sus funciones de PDF

PFGS = RAIZ / "pfgs"
GRADOS = RAIZ / "grados"
CATEGORIAS = RAIZ / "config" / "categorias.json"
CONFIG_EJECUCION = RAIZ / "config" / "ejecucion.json"
INDEX = Path(__file__).resolve().parent / "index.html"
FUENTE = INDEX.parent / "fuentes" / "Geist-Variable.woff2"  # servida aquí: el dashboard no pide nada a internet
MAX_SUBIDA = 100 * 1024 * 1024
MAX_PROGRAMA = 5 * 1024 * 1024
MAX_URLS = 100
ORIGEN = {".pdf": "PDF", ".txt": "Texto", ".html": "HTML"}  # las mismas extensiones que pfg.CONVERSORES

FASES = {"leer-pfg": "Lectura de la memoria", "grado-pfg": "Contraste con el grado",
         "preguntas-pfg": "Preguntas para la defensa", "anotaciones-pfg": "Respuestas a tus notas"}
# Cada tipo de nota vive en el archivo de quien la lee. Las personales van aparte para que ningún agente las abra.
TIPOS = {"personal": "notas-personales.json", "agente": "anotaciones.json", "preguntas": "anotaciones.json"}
AID = re.compile(r"[a-z0-9]{4,32}")
MAX_NOTA = 4000
PAGINA = re.compile(r"indice\.json|p(\d{3,4})\.(png|json)")
COMANDOS_SKILLS = ["uv run scripts/pfg.py", "python3 -m json.tool"]  # lo único que ejecutan las skills
MODELO = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99})?")  # sin «-» inicial: no puede colarse como flag
PROMPT = ("{comando}. Estás en modo no interactivo: nadie va a responder preguntas ni a confirmar nada. "
          "Ejecuta los comandos desde el directorio actual, que es la raíz del proyecto. En la shell solo puedes ejecutar "
          + " y ".join(f"`{c} …`" for c in COMANDOS_SKILLS) +
          ": cualquier otro comando se deniega y corta la ejecución. Para leer, buscar o contar usa tus herramientas "
          "de archivos, no la shell.")
VERSION = (RAIZ / "VERSION").read_text().strip()
REPO = "rubensancor/tribunal-pfg"
APP = os.environ.get("TRIBUNAL_APP") == "1"  # lo lanza la app de escritorio (main.js), que pone la ventana
REINICIO_APP = 75  # tras actualizar, la app vuelve a arrancar el servidor si sale con este código
AGY_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def opcion(flag, valor):
    return [flag, valor] if valor else []


def faltan_permisos_agy():
    rutas = [AGY_SETTINGS, *(Path.home() / ".gemini" / "config" / "projects").glob("**/*.json")]
    texto = "".join(p.read_text(errors="ignore") for p in rutas if p.is_file())
    faltan = [c for c in COMANDOS_SKILLS if f"command({c}" not in texto]
    if faltan:
        return ("Añade " + " y ".join(f'"command({c})"' for c in faltan) +
                f" a permissions.allow en {AGY_SETTINGS}: en modo headless agy deniega lo que no esté permitido.")


def perfil_codex():
    """Perfil de permisos de Codex: el sandbox de :workspace (proyecto, sin red), más la caché de uv, que uv run
    necesita, y sin las notas personales. Es una regla del sandbox: cubre la shell, archivos nuevos, renombrados y enlaces."""
    uv = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True).stdout.strip() or str(Path.home() / ".cache" / "uv")
    fs = "{" + f'":project_roots"={{{json.dumps("**/" + TIPOS["personal"])}="deny"}},{json.dumps(uv)}="write"' + "}"
    return ["-c", 'default_permissions="tribunal"', "-c", 'permissions.tribunal.extends=":workspace"',
            "-c", f"permissions.tribunal.filesystem={fs}"]


ESFUERZOS_CLAUDE = ["low", "medium", "high", "xhigh", "max"]
ESFUERZOS_PI = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]
ESFUERZOS_GEMINI = ["low", "medium", "high"]
ESFUERZOS_CODEX = ["low", "medium", "high", "xhigh", "max"]
# Gratis en OpenCode Zen y sin entrenar con los datos (opencode.ai/docs/zen). Los demás gratuitos pueden usar las
# memorias para mejorar el modelo o piden no enviarles datos personales.
# shortcut: lista fija, revísala cuando Zen cambie sus modelos gratuitos.
OPENCODE_GRATIS = {"opencode/glm-5.3-flash-free": ["low", "high", "max"],
                   "opencode/deepseek-v4.1-flash-free": ["low", "high", "max"],
                   "opencode/beam-free": ["low", "medium", "high", "xhigh", "max"]}
OPENCODE_DEFECTO = "opencode/glm-5.3-flash-free"
# Lo que no está denegado lo aprueba --auto. execute es Code Mode, que trae fetch y se salta webfetch. grep no
# filtra por ruta: con una carpeta concreta devolvería las notas personales aunque read las deniegue.
OPENCODE_PERMISOS = {"bash": {"*": "deny", **{f"{c} *": "allow" for c in COMANDOS_SKILLS},
                              f"*{TIPOS['personal']}*": "deny"}, "execute": "deny",
                     "webfetch": "deny", "websearch": "deny", "external_directory": "deny", "question": "deny",
                     "read": {"*": "allow", f"*{TIPOS['personal']}": "deny"}, "grep": "deny"}

# Cómo lanza cada harness una fase sin interacción. Cada uno controla los permisos a su manera.
# «modelos» son las sugerencias con los niveles de esfuerzo que acepta cada una; «esfuerzos», los del modelo por
# defecto y los que no están en la lista. agy rechaza --effort con los modelos que fijan el nivel en el nombre.
# «instalar» son los comandos oficiales de macOS y Linux (unix) y de PowerShell (windows), copiados de la página de
# «url», o None si no hay. El dashboard solo muestra el del sistema donde corre: nunca los ejecuta.
HARNESSES = {
    "claude": {"nombre": "Claude Code", "bin": "claude",
               "instalar": {"unix": "curl -fsSL https://claude.ai/install.sh | bash", "windows": "irm https://claude.ai/install.ps1 | iex",
                            "url": "https://code.claude.com/docs/en/setup"},
               "modelos": dict.fromkeys(["opus", "sonnet", "haiku"], ESFUERZOS_CLAUDE),
               "esfuerzos": ESFUERZOS_CLAUDE,
               "nota": "Solo puede ejecutar scripts/pfg.py y python3 -m json.tool; deniega el resto sin preguntar.",
               "args": lambda prompt, modelo, esfuerzo: [
                   "-p", prompt, "--permission-mode", "dontAsk", *opcion("--model", modelo),
                   *opcion("--effort", esfuerzo), "--allowedTools",
                   " ".join(["Read", "Write", "Edit", "Glob", "Grep", "Agent", *(f"Bash({c}:*)" for c in COMANDOS_SKILLS)])]},
    "agy": {"nombre": "Antigravity (agy)", "bin": "agy",
            "instalar": {"unix": "curl -fsSL https://antigravity.google/cli/install.sh | bash",
                         "windows": "irm https://antigravity.google/cli/install.ps1 | iex",
                         "url": "https://antigravity.google/docs/getting-started?tab=cli"},
            "modelos": {"gemini-3.8-flash": ESFUERZOS_GEMINI, "gemini-3.8-flash-high": [],
                                                       "claude-opus-4-6-thinking": []},
            "esfuerzos": ESFUERZOS_GEMINI,
            "nota": "Aplica las ediciones sin preguntar y los comandos según los permisos de tu settings.json de agy.",
            "requisito": faltan_permisos_agy,
            "args": lambda prompt, modelo, esfuerzo: ["-p", prompt, "--mode", "accept-edits", *opcion("--model", modelo),
                                                     *opcion("--effort", esfuerzo)]},
    "pi": {"nombre": "Pi", "bin": "pi", "instalar": {"unix": "curl -fsSL https://pi.dev/install.sh | sh",
                                                "windows": 'powershell -c "irm https://pi.dev/install.ps1 | iex"', "url": "https://pi.dev"},
           "modelos": {"openai-codex/gpt-6-luna": ESFUERZOS_PI},
           "esfuerzos": ESFUERZOS_PI,
           "nota": "Pi no tiene permisos: puede ejecutar cualquier comando sin preguntar.",
           "args": lambda prompt, modelo, esfuerzo: ["-p", prompt, "--no-session", "--approve", *opcion("--model", modelo),
                                                     *opcion("--thinking", esfuerzo)]},
    "codex": {"nombre": "Codex", "bin": "codex",
              "instalar": {"unix": "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
                           "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"',
                           "url": "https://learn.chatgpt.com/docs/codex/cli"},
              "modelos": {"gpt-6-luna": ESFUERZOS_CODEX, "gpt-5.6-luna": ESFUERZOS_CODEX,
                                                         "gpt-5.6-terra": [*ESFUERZOS_CODEX, "ultra"]},
              "esfuerzos": ESFUERZOS_CODEX,
              "nota": "Ejecuta cualquier comando sin preguntar, pero en su sandbox: sin red, sin leer tus notas personales "
                      "y escribiendo solo en el proyecto y en la caché de uv.",
              # Codex lee los archivos con la shell, así que el PROMPT general, que la restringe, lo confundiría.
              "prompt": "{comando}. Estás en modo no interactivo: nadie va a responder preguntas ni a confirmar nada. "
                        "Ejecuta los comandos desde el directorio actual, que es la raíz del proyecto. Las skills están en "
                        "`.agents/skills/<nombre>/SKILL.md`. Lee y busca con la shell; tu sandbox no tiene red y "
                        "bloquea las notas personales.",
              # Sin red, uv fallaría al revalidar el índice cuando caduca su caché: que resuelva solo con ella.
              "env": {"UV_OFFLINE": "1"},
              "args": lambda prompt, modelo, esfuerzo: [
                  "exec", "--ephemeral", "--skip-git-repo-check", *perfil_codex(), *opcion("--model", modelo),
                  *opcion("-c", esfuerzo and f'model_reasoning_effort="{esfuerzo}"'), prompt]},
    # --standalone: el servicio de fondo de opencode no vería la configuración de esta carpeta ni la de env.
    "opencode": {"nombre": "OpenCode (modelos gratis)", "bin": "opencode",
                 # En Windows, OpenCode no tiene instalador: solo un binario que se descarga de su página.
                 "instalar": {"unix": "curl -fsSL https://opencode.ai/v2/install | bash", "windows": None,
                              "url": "https://opencode.ai/docs"},
                 "modelos": OPENCODE_GRATIS,
                 "esfuerzos": OPENCODE_GRATIS[OPENCODE_DEFECTO], "solo_modelos": True,
                 "nota": "Solo modelos gratuitos de OpenCode Zen que no entrenan con los datos. Solo puede ejecutar "
                         "scripts/pfg.py y python3 -m json.tool, sin web ni tus notas personales; deniega el resto sin preguntar.",
                 "env": {"OPENCODE_CONFIG_CONTENT": json.dumps({"permission": OPENCODE_PERMISOS})},
                 "args": lambda prompt, modelo, esfuerzo: [
                     "run", "--standalone", "--auto", "-m",
                     (modelo or OPENCODE_DEFECTO) + (f"#{esfuerzo}" if esfuerzo else ""), prompt]},
}

EJECUCIONES = {}  # id -> ejecución en memoria; se pierde al parar el servidor, que además detiene las que sigan en curso
CERROJO = threading.Lock()
COLA = []  # ids de PFG subidos con «Leer y preguntar al cargar», preparados de uno en uno por preparar_cola
HAY_COLA = threading.Condition(CERROJO)
# gid -> URL pegadas en ese grado, cada una en_cola → descargando → hecha (con slug) | fallida (con error).
# shortcut: en memoria, se pierden al reiniciar el servidor; pásalas a disco si hay que reanudar descargas.
DESCARGAS = {}
HAY_DESCARGA = threading.Condition(CERROJO)


def leer(ruta):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        return {"_error": f"{ruta.name}: JSON no válido ({e})"}


def lista(x):
    return x if isinstance(x, list) else []


def objeto(x):
    return x if isinstance(x, dict) and "_error" not in x else {}


def escribir(ruta, obj):
    tmp = ruta.with_name(f".{ruta.name}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reemplazar(tmp, ruta)


def reemplazar(tmp, ruta):
    """En Windows, os.replace falla (WinError 5) mientras otro hilo lee `ruta` sin CERROJO: reintenta un momento."""
    for _ in range(100):
        try:
            return os.replace(tmp, ruta)
        except PermissionError:
            time.sleep(0.01)
    os.replace(tmp, ruta)


def generado(d, nombre):
    """paginas/<nombre>, creado con pfg.py si falta (fuera de CERROJO: tarda). None si la página no existe."""
    ruta = d / "paginas" / nombre
    if not ruta.exists():
        m = PAGINA.fullmatch(nombre)
        cmd = ["imagen", d.name, str(int(m[1]))] if m[1] else ["paginas", d.name]
        try:
            subprocess.run(["uv", "run", str(RAIZ / "scripts" / "pfg.py"), *cmd], cwd=RAIZ, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None
    return ruta if ruta.exists() else None


def anotaciones(d):
    """Las notas del docente unidas a las respuestas del agente. Única definición de «pendiente»."""
    respuestas = objeto(leer(d / "respuestas.json"))
    preguntas = d / "preguntas.json"
    generadas = preguntas.stat().st_mtime if preguntas.exists() else None
    notas = []
    for archivo in set(TIPOS.values()):
        for aid, n in objeto(leer(d / archivo)).items():
            r = respuestas.get(aid) if n["tipo"] == "agente" else None
            r = r if isinstance(r, dict) else None
            notas.append({**n, "id": aid, "respuesta": r and lista(r.get("respuesta")),
                          "pendiente": n["tipo"] == "agente" and bool(n["nota"].strip()) and (r or {}).get("nota") != n["nota"],
                          # preguntas-pfg ya se ejecutó sin ella: cuenta solo si se regeneran las preguntas
                          "tarde": n["tipo"] == "preguntas" and generadas is not None and n["creada"] > generadas})
    return sorted(notas, key=lambda n: (n["pdf"], (n["palabras"] or [-1])[0], n["creada"]))


def guardar_anotacion(d, aid, raw):
    """Crea o actualiza una nota. El servidor deriva cita y pag para que el navegador no pueda inventarlas."""
    if not AID.fullmatch(aid):
        raise ValueError("id de nota no válido")
    if not isinstance(raw, dict) or raw.get("tipo") not in TIPOS:
        raise ValueError(f"tipo de nota no válido; usa uno de {sorted(TIPOS)}")
    pdf, palabras, nota = raw.get("pdf"), raw.get("palabras"), raw.get("nota", "")
    if not isinstance(nota, str) or len(nota) > MAX_NOTA:
        raise ValueError(f"la nota debe ser texto de {MAX_NOTA} caracteres como máximo")
    indice = generado(d, "indice.json")
    if type(pdf) is not int or not indice or not 1 <= pdf <= len(paginas := json.loads(indice.read_text(encoding="utf-8"))):
        raise ValueError("la página no existe")
    cita = ""
    if palabras is not None:
        texto = generado(d, f"p{pdf:03d}.json")
        ws = json.loads(texto.read_text(encoding="utf-8"))["palabras"] if texto else []
        if not (isinstance(palabras, list) and len(palabras) == 2 and all(type(i) is int for i in palabras)
                and 0 <= palabras[0] <= palabras[1] < len(ws)):
            raise ValueError("las palabras seleccionadas no están en esa página")
        cita = " ".join(w[4] for w in ws[palabras[0]:palabras[1] + 1])
    with CERROJO:
        archivos = {a: objeto(leer(d / a)) for a in set(TIPOS.values())}
        previa = next((a[aid] for a in archivos.values() if aid in a), {})
        for a in archivos.values():
            a.pop(aid, None)  # cambiar el tipo puede cambiarla de archivo
        archivos[TIPOS[raw["tipo"]]][aid] = {"tipo": raw["tipo"], "pdf": pdf, "pag": paginas[pdf - 1]["pag"],
                                             "palabras": palabras, "cita": cita, "nota": nota,
                                             "creada": previa.get("creada", time.time())}
        for a, notas in archivos.items():
            if notas or (d / a).exists():
                escribir(d / a, notas)


def borrar_anotacion(d, aid):
    with CERROJO:
        for a in set(TIPOS.values()):
            if aid in (notas := objeto(leer(d / a))):
                del notas[aid]
                escribir(d / a, notas)


def programas_de(g):
    return [p for p in sorted((g / "programas").glob("*")) if p.suffix in pfg.CONVERSORES and not p.name.startswith(".")]


def hay_programas():
    return GRADOS.exists() and any(programas_de(g) for g in GRADOS.iterdir() if (g / "grado.json").exists())


def cambiado(g):
    """Última vez que cambiaron los programas o las fichas, incluidos los borrados (cambian la carpeta)."""
    t = 0
    for r in [g / "programas", g / "asignaturas", *(g / "programas").glob("*"), *(g / "asignaturas").glob("*")]:
        try:
            t = max(t, r.stat().st_mtime)
        except FileNotFoundError:
            pass
    return t


def resumen(d):
    """Estado deducido de los archivos que existen; nadie escribe un campo de estado."""
    cola = COLA.copy()  # sin el cerrojo: lanzar llama a resumen con él cogido
    indice = lista(leer(d / "secciones" / "indice.json"))
    leidas = sum((d / "secciones" / f"{s['n']:02d}.json").exists() for s in indice)
    analisis = leer(d / "analisis.json") or {}
    preguntas = lista(leer(d / "preguntas.json"))
    if (d / "clasificacion.json").exists():
        estado, paso = "clasificadas", None
    elif (d / "preguntas.json").exists():
        estado, paso = "preguntas", "preguntas-pfg"
    elif analisis:
        # Un contraste con grado null también cuenta como hecho: sin grado identificado nada se queda atascado.
        estado, paso = "leido", "grado-pfg" if hay_programas() and not (d / "contraste.json").exists() else "preguntas-pfg"
    elif indice:
        # Los archivos no saben si el lector sigue vivo: sin una lectura en curso, la lectura se quedó a medias.
        e = EJECUCIONES.get(d.name)
        viva = e and e["fase"] == "leer-pfg" and e["proc"].poll() is None
        estado, paso = "leyendo" if viva else "a_medias", "leer-pfg"
    else:
        estado, paso = "pendiente", "leer-pfg"
    return {"id": d.name, "estado": estado, "secciones": len(indice), "leidas": leidas,
            "titulo": analisis.get("titulo") or d.name, "estudiante": analisis.get("estudiante", ""),
            "preguntas": len(preguntas), "paso": paso,
            "comando": f"usa la skill {paso} con el PFG {d.name}" if paso else None,
            "ejecutor": HARNESSES[config_ejecucion()[paso]["harness"]]["nombre"] if paso else None,
            "ejecucion": ejecucion(d.name, paso), "cola": cola.index(d.name) + 1 if d.name in cola else None,
            "modificado": max(p.stat().st_mtime for p in d.rglob("*"))}


def niveles(harness, modelo):
    h = HARNESSES[harness]
    return h["modelos"].get(modelo, h["esfuerzos"])


def validar_config(raw):
    """{fase: {harness, modelo, esfuerzo}} completo; ValueError con el motivo si algo no vale."""
    if not isinstance(raw, dict):
        raise ValueError("se esperaba un objeto {fase: {harness, modelo, esfuerzo}}")
    cfg = {}
    for fase in FASES:
        v = raw.get(fase) or {}
        if not isinstance(v, dict):
            raise ValueError(f"{fase}: se esperaba un objeto")
        harness, modelo, esfuerzo = v.get("harness", "claude"), v.get("modelo", ""), v.get("esfuerzo", "")
        if harness not in HARNESSES:
            raise ValueError(f"{fase}: harness desconocido {harness!r}")
        if not isinstance(modelo, str) or not MODELO.fullmatch(modelo):
            raise ValueError(f"{fase}: modelo no válido {modelo!r}")
        if modelo and HARNESSES[harness].get("solo_modelos") and modelo not in HARNESSES[harness]["modelos"]:
            raise ValueError(f"{fase}: {HARNESSES[harness]['nombre']} solo admite " + ", ".join(HARNESSES[harness]["modelos"]))
        if esfuerzo and esfuerzo not in niveles(harness, modelo):
            raise ValueError(f"{fase}: {HARNESSES[harness]['nombre']} no admite el esfuerzo {esfuerzo!r} con "
                             + (f"el modelo {modelo}" if modelo else "su modelo por defecto"))
        cfg[fase] = {"harness": harness, "modelo": modelo, "esfuerzo": esfuerzo}
    return cfg


def config_ejecucion():
    try:
        return validar_config(leer(CONFIG_EJECUCION) or {})
    except ValueError:
        return validar_config({})


# El servidor corre en el ordenador del docente: su sistema es el del docente.
SISTEMA = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
SISTEMAS = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}
VERSIONES = {}  # ruta del binario -> primera línea de su --version; «Comprobar de nuevo» la vacía


def version(ruta):
    if ruta not in VERSIONES:
        try:
            # No subprocess.run(timeout=): solo mata al hijo, y el nieto (lo que lanza un .cmd de npm en Windows)
            # seguiría con las tuberías abiertas y communicate() lo esperaría. Se baja el árbol entero.
            p = subprocess.Popen([ruta, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                out, err = p.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                matar_arbol(p)
                p.communicate(timeout=3)
                raise
            linea = next((x.strip() for x in (out + "\n" + err).splitlines() if x.strip()), "") if p.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            linea = ""
        VERSIONES[ruta] = linea[:80] or None
    return VERSIONES[ruta]


def detectar(forzar=False):
    """{harness: {estado, version, problema}}. which va en cada llamada (barato, así se ve lo recién instalado);
    --version, una vez por ruta y en paralelo, para no frenar cada carga de Ajustes."""
    if forzar:
        VERSIONES.clear()
    rutas = {k: shutil.which(h["bin"]) for k, h in HARNESSES.items()}
    hilos = [threading.Thread(target=version, args=(r,)) for r in set(rutas.values()) if r and r not in VERSIONES]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()
    r = {}
    for k, h in HARNESSES.items():
        if not rutas[k]:
            r[k] = {"estado": "no_instalado", "version": None, "problema": f"No se encuentra «{h['bin']}» en el PATH."}
        else:
            requisito = (h.get("requisito") or (lambda: None))()
            r[k] = {"estado": "requisito" if requisito else "instalado", "version": VERSIONES.get(rutas[k]), "problema": requisito}
    return r


ULTIMA = {}  # la última release de GitHub, {version, url} o {error}; «Comprobar de nuevo» la vuelve a pedir


def semver(v):
    """«v0.2.0» -> (0, 2, 0); None si no es una versión."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", v) if isinstance(v, str) else None
    return tuple(map(int, m.groups())) if m else None


def comprobar_version():
    """Pide a GitHub la última release. No envía nada del docente ni de las memorias."""
    global ULTIMA
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={"User-Agent": "tribunal-pfg", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            rel = json.load(r)
        if not semver(rel.get("tag_name")):
            raise ValueError
        ULTIMA = {"version": rel["tag_name"].lstrip("v"), "url": rel.get("html_url")}
    except urllib.error.HTTPError as e:  # 404: el repositorio aún no ha publicado ninguna release
        ULTIMA = {} if e.code == 404 else {"error": "No se ha podido comprobar si hay una versión nueva."}
    except (OSError, ValueError, AttributeError):  # sin red o una respuesta rara
        ULTIMA = {"error": "No se ha podido comprobar si hay una versión nueva."}


def estado_version():
    u = ULTIMA.get("version")
    return {"actual": VERSION, "ultima": u, "url": ULTIMA.get("url"), "error": ULTIMA.get("error"),
            "nueva": bool(u) and semver(u) > semver(VERSION),
            "modo": "git" if (RAIZ / ".git").exists() and shutil.which("git") else "app" if APP else "zip"}


def git(*args):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if r.returncode:
        raise ValueError(f"git {args[0]} ha fallado: " + ((r.stderr or r.stdout).strip().splitlines() or ["sin mensaje"])[0])
    return r.stdout


def actualizar():
    """Avanza la copia hasta la última release, solo si es un avance directo. Si sale bien, vuelve con CERROJO
    cogido: nada puede empezar hasta el reinicio."""
    v = estado_version()
    if v["modo"] != "git":
        raise ValueError("esta copia no se instaló con git: descarga la versión nueva desde su página")
    if not v["nueva"]:
        raise ValueError("ya tienes la última versión")
    CERROJO.acquire()
    try:
        if any(e["proc"].poll() is None for e in EJECUCIONES.values()):
            raise ValueError("espera a que terminen las ejecuciones en curso, o detenlas, antes de actualizar")
        if COLA or any(x["estado"] in ("en_cola", "descargando") for xs in DESCARGAS.values() for x in xs):
            raise ValueError("espera a que se vacíe la cola y terminen las descargas: al reiniciar se perderían")
        tag = "v" + v["ultima"]
        git("fetch", "--no-tags", "origin", "tag", tag)
        # Solo bloquea lo que el docente cambió y la versión nueva también (categorias.json, por ejemplo); el resto se
        # conserva. Lo ignorado (pfgs/, grados/, config/ejecucion.json) ni aparece: nunca bloquea ni se toca.
        tocados = set(git("diff", "--name-only", "HEAD", tag).splitlines())
        if choques := [c[3:] for c in git("status", "--porcelain", "--untracked-files=no").splitlines() if c[3:] in tocados]:
            raise ValueError("la versión nueva cambia archivos que tú has modificado: " + ", ".join(choques)
                             + ". Guarda una copia, deshaz esos cambios con git checkout -- <archivo>, actualiza y vuelve a aplicarlos")
        git("merge", "--ff-only", tag)
    except BaseException:
        CERROJO.release()
        raise


def reiniciar():
    """Sustituye este proceso por el servidor nuevo. Con uv, para que instale las dependencias que añada la versión."""
    print("Actualizado. Reiniciando el dashboard…", flush=True)
    if APP:  # la app vigila este proceso: si se sustituyera solo, en Windows lo perdería de vista
        os._exit(REINICIO_APP)
    os.environ["TRIBUNAL_REINICIO"] = "1"
    script = str(Path(__file__).resolve())
    cmd = ([uv, "run", script] if (uv := shutil.which("uv")) else [sys.executable, script]) + sys.argv[1:]
    if os.name == "nt":  # en Windows os.execv no entrecomilla: una ruta con espacios rompería el arranque
        subprocess.Popen(cmd)
        os._exit(0)
    os.execv(cmd[0], cmd)


def vista_config(forzar=False):
    if forzar:
        comprobar_version()
    try:
        validar_config(leer(CONFIG_EJECUCION) or {})
        error = None
    except ValueError as e:
        error = f"{CONFIG_EJECUCION.name} no es válido y se usan los valores por defecto: {e}"
    estados = detectar(forzar)
    so = "windows" if SISTEMA == "windows" else "unix"
    return {"fases": {f: {"nombre": FASES[f], **c} for f, c in config_ejecucion().items()}, "error": error,
            "sistema": {"id": SISTEMA, "nombre": SISTEMAS[SISTEMA]}, "version": estado_version(),
            "harnesses": {k: {"nombre": h["nombre"], "modelos": h["modelos"], "esfuerzos": h["esfuerzos"], "nota": h["nota"],
                              "instalar": {"comando": h["instalar"][so], "url": h["instalar"]["url"]}, **estados[k]}
                          for k, h in HARNESSES.items()}}


def comando_agente(harness, modelo, esfuerzo, comando):
    h = HARNESSES[harness]
    return [h["bin"], *h["args"](h.get("prompt", PROMPT).format(comando=comando), modelo, esfuerzo)]


def ejecucion(pfg_id, paso, con_log=False):
    """Estado de la última ejecución. Salir con 0 sin que el PFG pase de fase no es éxito: algunos harness
    (agy sin permisos) terminan bien sin haber hecho nada."""
    e = EJECUCIONES.get(pfg_id)
    if not e:
        return None
    codigo = e["proc"].poll()
    if e["fase"] == "anotaciones-pfg":
        avanzo = not any(n["pendiente"] for n in anotaciones(PFGS / pfg_id))
    elif e["fase"] == "grado-pfg":  # a demanda, el paso ya era otro antes de empezar
        c = PFGS / pfg_id / "contraste.json"
        avanzo = c.exists() and c.stat().st_mtime >= e["inicio"]
    else:
        avanzo = paso != e["fase"]
    despues = None
    if e["seguir"] and e["fase"] != "preguntas-pfg":
        despues = FASES["grado-pfg" if e["fase"] == "leer-pfg" and hay_programas() else "preguntas-pfg"]
    estado = ("en_curso" if codigo is None else "detenida" if codigo < 0 or e.get("detenida") else "fallida" if codigo
              else "terminada" if avanzo else "sin_avance")
    r = {"paso": e["fase"], "fase": FASES[e["fase"]], "harness": HARNESSES[e["harness"]]["nombre"], "modelo": e["modelo"],
         "esfuerzo": e["esfuerzo"], "inicio": e["inicio"], "estado": estado, "codigo": codigo,
         "despues": despues}
    if con_log:
        with open(e["log"], "rb") as f:
            f.seek(max(f.seek(0, 2) - 6000, 0))
            r["log"] = f.read().decode(errors="replace")
    return r


def binario(harness):
    """La ruta del harness. Se lanza por ruta: en Windows, Popen("codex") solo encuentra un .exe, no el .cmd de npm."""
    if not (ruta := shutil.which(b := HARNESSES[harness]["bin"])):
        raise ValueError(f"no se encuentra «{b}» en el PATH")
    return ruta


def lanzar(d, fase=None, seguir=False):
    """Lanza el agente de `fase` (sin ella, el del siguiente paso) y devuelve su ejecución. ValueError si no se puede."""
    with CERROJO:
        if not (d / "memoria.pdf").exists():
            raise ValueError("este PFG ya no existe")
        if (e := EJECUCIONES.get(d.name)) and e["proc"].poll() is None:
            raise ValueError("ya hay una ejecución en curso para este PFG")
        if fase is None:
            fase = resumen(d)["paso"]
            if not fase:
                raise ValueError("este PFG ya tiene todas las fases hechas")
        elif fase == "grado-pfg":
            if not (d / "analisis.json").exists():
                raise ValueError("lee antes la memoria")
            if not hay_programas():
                raise ValueError("carga antes los programas de algún grado")
        elif fase != "anotaciones-pfg":
            raise ValueError(f"no se puede lanzar la fase {fase!r} a demanda")
        elif not any(n["pendiente"] for n in anotaciones(d)):
            raise ValueError("no hay notas pendientes de respuesta")
        cfg = config_ejecucion()[fase]
        ruta = binario(cfg["harness"])
        argv = comando_agente(cfg["harness"], cfg["modelo"], cfg["esfuerzo"], f"usa la skill {fase} con el PFG {d.name}")
        argv[0] = ruta
        log = d / "ejecuciones" / f"{time.strftime('%Y%m%d-%H%M%S')}-{fase}.log"
        log.parent.mkdir(exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            f.write(f"$ {shlex.join(argv)}\n\n")
            f.flush()
            # Grupo propio para poder detener también los subprocesos del agente. PWD: opencode lo prefiere a cwd.
            proc = subprocess.Popen(argv, cwd=RAIZ, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                    start_new_session=True,
                                    env={**os.environ, "PWD": str(RAIZ), **HARNESSES[cfg["harness"]].get("env", {})})
        EJECUCIONES[d.name] = {"fase": fase, "harness": cfg["harness"], "modelo": cfg["modelo"],
                               "esfuerzo": cfg["esfuerzo"], "inicio": time.time(), "log": log, "proc": proc,
                               "seguir": seguir}
        return EJECUCIONES[d.name]


def encolar(d):
    binario(config_ejecucion()["leer-pfg"]["harness"])
    with HAY_COLA:
        COLA.append(d.name)
        HAY_COLA.notify()


def desencolar(d=None):
    """Saca de la cola el PFG d, o todos sin d. No borra nada; si ya empezó, sigue en marcha."""
    with HAY_COLA:
        if d is None:
            COLA.clear()
        elif d.name in COLA:
            COLA.remove(d.name)


def preparar_cola():
    """Lee y pregunta los PFG de la cola de uno en uno. Una fase fallida, detenida o sin avance pasa al siguiente."""
    while True:
        with HAY_COLA:
            HAY_COLA.wait_for(lambda: COLA)
            d = PFGS / COLA.pop(0)
        fase = None
        try:
            while resumen(d)["paso"] not in (None, fase):
                e = lanzar(d, seguir=True)
                fase = e["fase"]
                if e["proc"].wait() != 0:
                    break
        except (ValueError, OSError):
            pass  # se borró o alguien lanzó la fase a mano mientras esperaba


def borrar(d):
    """Borra el PDF y todo lo generado. ValueError si un agente sigue escribiendo en la carpeta."""
    with CERROJO:
        if (e := EJECUCIONES.get(d.name)) and e["proc"].poll() is None:
            raise ValueError("detén la ejecución en curso antes de borrar este PFG")
        EJECUCIONES.pop(d.name, None)
        if d.name in COLA:
            COLA.remove(d.name)
        shutil.rmtree(d)


def matar_arbol(proc):
    """El proceso y lo que haya lanzado. En POSIX, proc tiene que ir en su propio grupo (start_new_session)."""
    if os.name == "nt":  # sin grupos de procesos: taskkill /T baja el árbol
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # terminó entre poll() y killpg()


def detener(e):
    if e["proc"].poll() is None:
        e["detenida"] = True  # taskkill deja el código 1, no uno negativo: sin esto se vería como fallida
        matar_arbol(e["proc"])


def origen_local(host, origen, puerto):
    """Solo la propia página: otra web abierta en el navegador no puede leer memorias ni lanzar agentes.
    El Host frena el DNS rebinding; el Origin, que el navegador siempre manda entre sitios, frena el CSRF."""
    locales = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}
    return host in locales and (origen is None or origen in {f"http://{h}" for h in locales})


def contraste_de(d):
    """El grado con el que se contrastó un PFG y lo que la pestaña Grado necesita de su catálogo."""
    c = leer(d / "contraste.json")
    gid = objeto(leer(d / "grado.json")).get("grado")
    g = GRADOS / gid if isinstance(gid, str) and re.fullmatch(r"[a-z0-9-]+", gid) else None
    meta = objeto(leer(g / "grado.json")) if g else {}
    usadas = {t.get("asignatura") for campo in ("aplica", "extiende") for e in lista(objeto(c).get(campo))
              for t in lista(objeto(e).get("temas")) if isinstance(t, dict)}
    cat = {s: {"asignatura": f.get("asignatura"), "caracter": f.get("caracter"),
               "temas": {t.get("id"): t.get("texto") for t in lista(f.get("temas")) if isinstance(t, dict)}}
           for s, f in (pfg.catalogo(g).items() if meta else []) if s in usadas and isinstance(f, dict)}
    return {"grado": leer(d / "grado.json"), "contraste": c, "grado_nombre": meta.get("nombre"),
            "grado_programas": len(programas_de(g)) if meta else 0, "catalogo": cat,
            "desfase": bool(c and meta and cambiado(g) > (d / "contraste.json").stat().st_mtime),
            "contrastable": hay_programas() and (d / "analisis.json").exists(),
            "ejecutor_grado": HARNESSES[config_ejecucion()["grado-pfg"]["harness"]]["nombre"]}


def detalle(d):
    indice = lista(leer(d / "secciones" / "indice.json"))
    r = resumen(d)
    return {**r, **contraste_de(d), "ejecucion": ejecucion(d.name, r["paso"], con_log=True), "indice": indice,
            "lecturas": [leer(d / "secciones" / f"{s['n']:02d}.json") for s in indice],
            "analisis": leer(d / "analisis.json"), "preguntas": leer(d / "preguntas.json"),
            "clasificacion": leer(d / "clasificacion.json"), "categorias": leer(CATEGORIAS),
            "anotaciones": anotaciones(d),
            "ejecutor_notas": HARNESSES[config_ejecucion()["anotaciones-pfg"]["harness"]]["nombre"]}


def slug(texto, defecto, largo=60):
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:largo] or defecto


def nuevo_dir(nombre):
    base = slug(Path(nombre).stem, "pfg")
    for i in range(1, 1000):
        d = PFGS / (base if i == 1 else f"{base}-{i}")
        try:
            d.mkdir(parents=True)
            return d
        except FileExistsError:
            continue
    raise RuntimeError("demasiados PFG con el mismo nombre")


def crear_grado(nombre):
    nombre = nombre.strip() if isinstance(nombre, str) else ""
    if not 0 < len(nombre) <= 200:
        raise ValueError("escribe el nombre de la titulación, de 200 caracteres como máximo")
    g = GRADOS / slug(nombre, "grado", 120)
    with CERROJO:
        if g.exists():
            raise ValueError("ya hay un grado con ese nombre")
        (g / "programas").mkdir(parents=True)
        escribir(g / "grado.json", {"nombre": nombre, "fuentes": {}})
    return g


def poner_programa(g, s, ext, datos, fuente=None):
    """Guarda el programa `s`. Si ya existía lo sustituye y borra su texto y su ficha: hay que volver a leerlo."""
    if not datos:
        raise ValueError("el programa está vacío")
    if len(datos) > MAX_PROGRAMA:
        raise ValueError("el programa ocupa más de 5 MB")
    if ext == ".pdf" and not datos.startswith(b"%PDF"):
        raise ValueError("no es un PDF")
    with CERROJO:
        meta = objeto(leer(g / "grado.json"))
        if not meta:
            raise ValueError("este grado ya no existe")
        for viejo in [*(g / "programas").glob(f"{s}.*"), g / "textos" / f"{s}.txt", g / "asignaturas" / f"{s}.json"]:
            viejo.unlink(missing_ok=True)
        tmp = g / "programas" / f".{s}{ext}.tmp"
        tmp.write_bytes(datos)
        reemplazar(tmp, g / "programas" / f"{s}{ext}")
        fuentes = meta.setdefault("fuentes", {})
        if fuente:
            fuentes[s] = fuente
        else:
            fuentes.pop(s, None)
        escribir(g / "grado.json", meta)
    return s


def guardar_programa(g, nombre, datos):
    """Un PDF, un .txt o una página guardada desde el navegador subidos, o un texto pegado (llega como .txt)."""
    ext = Path(nombre).suffix.lower()
    ext = ".html" if ext == ".htm" else ext
    if ext not in ORIGEN:
        raise ValueError("el programa debe ser un PDF, un .txt o un .html")
    return poner_programa(g, slug(Path(nombre).stem, "programa"), ext, datos)


class SoloHttp(urllib.request.HTTPRedirectHandler):
    """urllib sigue redirecciones a ftp:// y rechaza file:// con un mensaje en inglés: aquí ambas fallan igual."""
    def http_error_302(self, req, fp, code, msg, headers):
        destino = urljoin(req.full_url, headers.get("location") or headers.get("uri") or "")
        if urlparse(destino).scheme not in ("http", "https"):
            fp.close()
            raise ValueError(f"redirige a {destino}, que no es una URL http o https")
        return super().http_error_302(req, fp, code, msg, headers)
    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


DESCARGADOR = urllib.request.build_opener(SoloHttp)


def descargar_programa(g, url):
    """Descarga una guía y la guarda con el código de la asignatura si la URL lo trae (Deusto: _codAsignatura)."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("solo se admiten URL http o https")
    try:
        with DESCARGADOR.open(urllib.request.Request(url, headers={"User-Agent": "tribunal-pfg"}), timeout=20) as r:
            datos = r.read(MAX_PROGRAMA + 1)
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise ValueError(f"no se ha podido descargar ({e})")
    cod = parse_qs(u.query).get("_codAsignatura", [""])[0]
    s = cod.lower() if re.fullmatch(r"[A-Za-z0-9-]{1,60}", cod) else slug(Path(u.path).stem or u.netloc, "programa")
    return poner_programa(g, s, ".pdf" if datos.startswith(b"%PDF") else ".html", datos, url)


def encolar_urls(g, urls):
    """Añade las URL a las descargas del grado, olvidando las ya terminadas. Devuelve la lista para la respuesta."""
    with HAY_DESCARGA:
        activas = [x for x in DESCARGAS.get(g.name, []) if x["estado"] in ("en_cola", "descargando")]
        DESCARGAS[g.name] = activas + [{"url": u, "estado": "en_cola"} for u in urls]
        HAY_DESCARGA.notify()
        return [dict(x) for x in DESCARGAS[g.name]]


def descargar_cola():
    """Descarga las URL pegadas de una en una, grado a grado y en el orden pegado: no saturar el servidor de la universidad."""
    while True:
        with HAY_DESCARGA:
            gid, x = HAY_DESCARGA.wait_for(lambda: next(((gid, x) for gid, xs in DESCARGAS.items()
                                                          for x in xs if x["estado"] == "en_cola"), None))
            x["estado"] = "descargando"
        try:
            hecho = {"estado": "hecha", "slug": descargar_programa(GRADOS / gid, x["url"])}
        except Exception as e:  # si el hilo muriera, esta URL se quedaría «descargando» y las demás en cola para siempre
            hecho = {"estado": "fallida", "error": str(e)}
        with CERROJO:
            x.update(hecho)


def borrar_programa(g, s):
    if not re.fullmatch(r"[a-z0-9-]+", s):
        raise ValueError("programa no válido")
    with CERROJO:
        for viejo in [*(g / "programas").glob(f"{s}.*"), g / "textos" / f"{s}.txt", g / "asignaturas" / f"{s}.json"]:
            viejo.unlink(missing_ok=True)
        meta = objeto(leer(g / "grado.json"))
        if meta.get("fuentes", {}).pop(s, None):
            escribir(g / "grado.json", meta)


def borrar_grado(g):
    with CERROJO:
        for x in DESCARGAS.get(g.name, []):
            if x["estado"] == "en_cola":
                x.update(estado="fallida", error="este grado ya no existe")
        shutil.rmtree(g)


def usan_grado(g):
    dirs = [d for d in PFGS.iterdir() if (d / "memoria.pdf").exists()] if PFGS.exists() else []
    return [{"id": d.name, "titulo": objeto(leer(d / "analisis.json")).get("titulo") or d.name}
            for d in dirs if objeto(leer(d / "grado.json")).get("grado") == g.name]


def resumen_grado(g):
    progs = programas_de(g)
    return {"id": g.name, "nombre": objeto(leer(g / "grado.json")).get("nombre", g.name), "programas": len(progs),
            "leidos": sum((g / "asignaturas" / f"{p.stem}.json").exists() for p in progs), "pfgs": usan_grado(g)}


def detalle_grado(g):
    fuentes = objeto(leer(g / "grado.json")).get("fuentes") or {}
    cat = pfg.catalogo(g)
    asignaturas = [{"slug": p.stem, "origen": "URL" if p.stem in fuentes else ORIGEN[p.suffix],
                    "fuente": fuentes.get(p.stem) or f"/grados/{g.name}/programas/{p.name}",
                    "ficha": cat.get(p.stem) if isinstance(cat.get(p.stem), dict) else None} for p in programas_de(g)]
    def orden(a):  # las leídas primero, por curso y nombre
        f = a["ficha"] or {}
        return not f, f.get("curso") if type(f.get("curso")) is int else 99, str(f.get("asignatura") or a["slug"])
    with CERROJO:
        descargas = [dict(x) for x in DESCARGAS.get(g.name, [])]
    return {**resumen_grado(g), "asignaturas": sorted(asignaturas, key=orden), "descargas": descargas}


class Handler(BaseHTTPRequestHandler):
    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        if not isinstance(cuerpo, bytes):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(cuerpo)

    def pfg(self, ruta, patron):
        m = re.fullmatch(patron, ruta)
        d = m and PFGS / m.group(1)
        return d if d and (d / "memoria.pdf").exists() else None

    def grado(self, ruta, patron):
        m = re.fullmatch(patron, ruta)
        g = m and GRADOS / m.group(1)
        return g if g and (g / "grado.json").exists() else None

    def local(self):
        if origen_local(self.headers.get("Host"), self.headers.get("Origin"), self.server.server_port):
            return True
        self.close_connection = True  # no leemos el cuerpo
        self.responder(403, {"error": "solo se admiten peticiones desde el propio dashboard"})
        return False

    def cuerpo_json(self, maximo=10_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > maximo:
            raise ValueError("cuerpo demasiado grande")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON no válido ({e})")

    def do_GET(self):
        if not self.local():
            return
        ruta = urlparse(self.path).path
        if ruta == "/":
            return self.responder(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if ruta == "/fuentes/Geist-Variable.woff2":
            return self.responder(200, FUENTE.read_bytes(), "font/woff2")
        if ruta == "/api/config":
            return self.responder(200, vista_config())
        if ruta == "/api/version":
            return self.responder(200, estado_version())
        if ruta == "/api/pfgs":
            dirs = [d for d in PFGS.iterdir() if (d / "memoria.pdf").exists()] if PFGS.exists() else []
            return self.responder(200, sorted((resumen(d) for d in dirs), key=lambda r: -r["modificado"]))
        if d := self.pfg(ruta, r"/api/pfgs/([a-z0-9-]+)"):
            return self.responder(200, detalle(d))
        if ruta == "/api/grados":
            gs = sorted(g for g in GRADOS.iterdir() if (g / "grado.json").exists()) if GRADOS.exists() else []
            return self.responder(200, [resumen_grado(g) for g in gs])
        if g := self.grado(ruta, r"/api/grados/([a-z0-9-]+)"):
            return self.responder(200, detalle_grado(g))
        # Nunca como HTML: una página subida o descargada ejecutaría sus scripts con acceso a la API del dashboard.
        if (g := self.grado(ruta, r"/grados/([a-z0-9-]+)/programas/([a-z0-9-]+\.(?:pdf|txt|html))")) \
                and (f := g / "programas" / ruta.rsplit("/", 1)[1]).exists():
            if f.suffix == ".pdf":
                return self.responder(200, f.read_bytes(), "application/pdf")
            return self.responder(200, pfg.decodificar(f.read_bytes()).encode(), "text/plain; charset=utf-8")
        if d := self.pfg(ruta, r"/pfgs/([a-z0-9-]+)/memoria\.pdf"):
            return self.responder(200, (d / "memoria.pdf").read_bytes(), "application/pdf")
        if (d := self.pfg(ruta, r"/pfgs/([a-z0-9-]+)/paginas/(.+)")) and PAGINA.fullmatch(nombre := ruta.rsplit("/", 1)[1]) \
                and (f := generado(d, nombre)):
            return self.responder(200, f.read_bytes(), "image/png" if nombre.endswith(".png") else "application/json")
        self.responder(404, {"error": "no encontrado"})

    def do_POST(self):
        if not self.local():
            return
        url = urlparse(self.path)
        try:
            if url.path == "/api/config/detectar":
                return self.responder(200, vista_config(forzar=True))
            if url.path == "/api/actualizar":
                actualizar()
                self.responder(202, {"ok": True})  # sin búfer: la respuesta ya ha salido cuando el proceso se sustituye
                return reiniciar()
            if url.path == "/api/config":
                cfg = validar_config(self.cuerpo_json())
                CONFIG_EJECUCION.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return self.responder(200, vista_config())
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/ejecutar"):
                raw = self.cuerpo_json()
                lanzar(d, raw.get("fase") if isinstance(raw, dict) else None)
                return self.responder(201, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/anotaciones/([^/]+)"):
                guardar_anotacion(d, url.path.rsplit("/", 1)[1], self.cuerpo_json(4 * MAX_NOTA + 1000))
                return self.responder(200, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/anotaciones/([^/]+)/borrar"):
                borrar_anotacion(d, url.path.split("/")[-2])
                return self.responder(200, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/borrar"):
                borrar(d)
                return self.responder(200, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/detener"):
                if e := EJECUCIONES.get(d.name):
                    detener(e)
                return self.responder(200, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/desencolar"):
                desencolar(d)
                return self.responder(200, {"ok": True})
            if url.path == "/api/cola/vaciar":
                desencolar()
                return self.responder(200, {"ok": True})
            if url.path == "/api/grados":
                raw = self.cuerpo_json()
                return self.responder(201, {"id": crear_grado(raw.get("nombre") if isinstance(raw, dict) else None).name})
            if g := self.grado(url.path, r"/api/grados/([a-z0-9-]+)/programas"):
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 < n <= MAX_PROGRAMA:
                    self.close_connection = True  # no leemos el cuerpo
                    return self.responder(413, {"error": "el programa debe ocupar entre 1 byte y 5 MB"})
                nombre = parse_qs(url.query).get("nombre", [""])[0]
                return self.responder(201, {"slug": guardar_programa(g, nombre, self.rfile.read(n))})
            if g := self.grado(url.path, r"/api/grados/([a-z0-9-]+)/urls"):
                raw = self.cuerpo_json(200_000)
                urls = [u.strip() for u in (raw.get("urls") if isinstance(raw, dict) else None) or [] if isinstance(u, str) and u.strip()]
                if not 0 < len(urls) <= MAX_URLS:
                    raise ValueError(f"pega entre 1 y {MAX_URLS} URL, una por línea")
                return self.responder(202, encolar_urls(g, urls))
            if g := self.grado(url.path, r"/api/grados/([a-z0-9-]+)/programas/([a-z0-9-]+)/borrar"):
                borrar_programa(g, url.path.split("/")[-2])
                return self.responder(200, {"ok": True})
            if g := self.grado(url.path, r"/api/grados/([a-z0-9-]+)/borrar"):
                borrar_grado(g)
                return self.responder(200, {"ok": True})
        except ValueError as e:
            return self.responder(409, {"error": str(e)})
        if url.path != "/api/pfgs":
            return self.responder(404, {"error": "no encontrado"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_SUBIDA:
            self.close_connection = True  # no leemos el cuerpo
            return self.responder(413, {"error": "el PDF debe ocupar entre 1 byte y 100 MB"})
        datos = self.rfile.read(n)
        if not datos.startswith(b"%PDF"):
            return self.responder(400, {"error": "no es un PDF"})
        query = parse_qs(url.query)
        d = nuevo_dir(query.get("nombre", ["pfg.pdf"])[0])
        (d / "memoria.pdf").write_bytes(datos)
        if query.get("preparar") == ["1"]:
            try:
                encolar(d)
            except ValueError as e:
                return self.responder(201, {"id": d.name, "error": str(e)})  # el PDF sí se guardó
        self.responder(201, {"id": d.name})

    def log_message(self, *args):
        pass  # el dashboard consulta cada pocos segundos; no llenar la terminal


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    reinicio = os.environ.pop("TRIBUNAL_REINICIO", None)
    for _ in range(40 if reinicio else 1):  # en Windows el proceso anterior puede tardar en soltar el puerto
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)
            break
        except OSError:
            time.sleep(0.25)
    else:
        sys.exit(f"El puerto {puerto} está ocupado: ¿ya está abierto el dashboard? http://127.0.0.1:{puerto}")
    url = f"http://127.0.0.1:{puerto}"
    print(f"Dashboard del tribunal en {url} (versión {VERSION}; Ctrl+C para parar)", flush=True)
    if APP:  # la app cierra este stdin al salir, o al morir: es la señal de parada que funciona igual en Windows
        threading.Thread(target=lambda: (sys.stdin.buffer.read(), servidor.shutdown()), daemon=True).start()
    elif not reinicio:  # tras actualizar, la pestaña abierta se recarga sola
        webbrowser.open(url)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    threading.Thread(target=preparar_cola, daemon=True).start()
    threading.Thread(target=detectar, daemon=True).start()  # las versiones, en caché antes de abrir Ajustes
    threading.Thread(target=descargar_cola, daemon=True).start()
    threading.Thread(target=comprobar_version, daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CERROJO.acquire()  # ninguna fase puede empezar mientras se cierra
        for e in EJECUCIONES.values():  # sin el servidor nadie vería ni podría parar esos agentes
            detener(e)


if __name__ == "__main__":
    main()
