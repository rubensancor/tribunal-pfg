#!/usr/bin/env python3
"""Dashboard local del tribunal PFG. Solo stdlib. Uso: uv run dashboard/server.py [puerto]"""
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
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
PFGS = RAIZ / "pfgs"
CATEGORIAS = RAIZ / "config" / "categorias.json"
CONFIG_EJECUCION = RAIZ / "config" / "ejecucion.json"
INDEX = Path(__file__).resolve().parent / "index.html"
MAX_SUBIDA = 100 * 1024 * 1024

FASES = {"leer-pfg": "Lectura de la memoria", "preguntas-pfg": "Preguntas para la defensa"}
COMANDOS_SKILLS = ["uv run scripts/pfg.py", "python3 -m json.tool"]  # lo único que ejecutan las skills
MODELO = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99})?")  # sin «-» inicial: no puede colarse como flag
PROMPT = ("{comando}. Estás en modo no interactivo: nadie va a responder preguntas ni a confirmar nada. "
          "Ejecuta los comandos desde el directorio actual, que es la raíz del proyecto.")
AGY_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def con_modelo(modelo):
    return ["--model", modelo] if modelo else []


def faltan_permisos_agy():
    rutas = [AGY_SETTINGS, *(Path.home() / ".gemini" / "config" / "projects").glob("**/*.json")]
    texto = "".join(p.read_text(errors="ignore") for p in rutas if p.is_file())
    faltan = [c for c in COMANDOS_SKILLS if f"command({c}" not in texto]
    if faltan:
        return ("Añade " + " y ".join(f'"command({c})"' for c in faltan) +
                f" a permissions.allow en {AGY_SETTINGS}: en modo headless agy deniega lo que no esté permitido.")


# Cómo lanza cada harness una fase sin interacción. Cada uno controla los permisos a su manera.
HARNESSES = {
    "claude": {"nombre": "Claude Code", "bin": "claude", "modelos": ["opus", "sonnet", "haiku"],
               "nota": "Solo puede ejecutar scripts/pfg.py y python3 -m json.tool; deniega el resto sin preguntar.",
               "args": lambda prompt, modelo: [
                   "-p", prompt, "--permission-mode", "dontAsk", *con_modelo(modelo), "--allowedTools",
                   " ".join(["Read", "Write", "Edit", "Glob", "Grep", "Agent", *(f"Bash({c}:*)" for c in COMANDOS_SKILLS)])]},
    "agy": {"nombre": "Antigravity (agy)", "bin": "agy", "modelos": ["gemini-3.8-flash-high", "claude-opus-4-6-thinking"],
            "nota": "Aplica las ediciones sin preguntar y los comandos según los permisos de tu settings.json de agy.",
            "requisito": faltan_permisos_agy,
            "args": lambda prompt, modelo: ["-p", prompt, "--mode", "accept-edits", *con_modelo(modelo)]},
    "pi": {"nombre": "Pi", "bin": "pi", "modelos": ["openai-codex/gpt-6-luna"],
           "nota": "Pi no tiene permisos: puede ejecutar cualquier comando sin preguntar.",
           "args": lambda prompt, modelo: ["-p", prompt, "--no-session", "--approve", *con_modelo(modelo)]},
}

EJECUCIONES = {}  # id -> ejecución en memoria; se pierde al parar el servidor, que además detiene las que sigan en curso
CERROJO = threading.Lock()


def leer(ruta):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        return {"_error": f"{ruta.name}: JSON no válido ({e})"}


def lista(x):
    return x if isinstance(x, list) else []


def resumen(d):
    """Estado deducido de los archivos que existen; nadie escribe un campo de estado."""
    indice = lista(leer(d / "secciones" / "indice.json"))
    leidas = sum((d / "secciones" / f"{s['n']:02d}.json").exists() for s in indice)
    analisis = leer(d / "analisis.json") or {}
    preguntas = lista(leer(d / "preguntas.json"))
    if (d / "clasificacion.json").exists():
        estado, paso = "clasificadas", None
    elif (d / "preguntas.json").exists():
        estado, paso = "preguntas", "preguntas-pfg"
    elif analisis:
        estado, paso = "leido", "preguntas-pfg"
    elif indice:
        estado, paso = "leyendo", "leer-pfg"
    else:
        estado, paso = "pendiente", "leer-pfg"
    return {"id": d.name, "estado": estado, "secciones": len(indice), "leidas": leidas,
            "titulo": analisis.get("titulo") or d.name, "estudiante": analisis.get("estudiante", ""),
            "preguntas": len(preguntas), "paso": paso,
            "comando": f"usa la skill {paso} con el PFG {d.name}" if paso else None,
            "ejecutor": HARNESSES[config_ejecucion()[paso]["harness"]]["nombre"] if paso else None,
            "ejecucion": ejecucion(d.name, paso),
            "modificado": max(p.stat().st_mtime for p in d.rglob("*"))}


def validar_config(raw):
    """{fase: {harness, modelo}} completo; ValueError con el motivo si algo no vale."""
    if not isinstance(raw, dict):
        raise ValueError("se esperaba un objeto {fase: {harness, modelo}}")
    cfg = {}
    for fase in FASES:
        v = raw.get(fase) or {}
        if not isinstance(v, dict):
            raise ValueError(f"{fase}: se esperaba un objeto")
        harness, modelo = v.get("harness", "claude"), v.get("modelo", "")
        if harness not in HARNESSES:
            raise ValueError(f"{fase}: harness desconocido {harness!r}")
        if not isinstance(modelo, str) or not MODELO.fullmatch(modelo):
            raise ValueError(f"{fase}: modelo no válido {modelo!r}")
        cfg[fase] = {"harness": harness, "modelo": modelo}
    return cfg


def config_ejecucion():
    try:
        return validar_config(leer(CONFIG_EJECUCION) or {})
    except ValueError:
        return validar_config({})


def vista_config():
    try:
        validar_config(leer(CONFIG_EJECUCION) or {})
        error = None
    except ValueError as e:
        error = f"{CONFIG_EJECUCION.name} no es válido y se usan los valores por defecto: {e}"
    return {"fases": {f: {"nombre": FASES[f], **c} for f, c in config_ejecucion().items()}, "error": error,
            "harnesses": {k: {"nombre": h["nombre"], "modelos": h["modelos"], "nota": h["nota"],
                              "problema": (None if shutil.which(h["bin"]) else f"No se encuentra «{h['bin']}» en el PATH.")
                              or (h.get("requisito") or (lambda: None))()}
                          for k, h in HARNESSES.items()}}


def comando_agente(harness, modelo, comando):
    h = HARNESSES[harness]
    return [h["bin"], *h["args"](PROMPT.format(comando=comando), modelo)]


def ejecucion(pfg_id, paso, con_log=False):
    """Estado de la última ejecución. Salir con 0 sin que el PFG pase de fase no es éxito: algunos harness
    (agy sin permisos) terminan bien sin haber hecho nada."""
    e = EJECUCIONES.get(pfg_id)
    if not e:
        return None
    codigo = e["proc"].poll()
    estado = ("en_curso" if codigo is None else "detenida" if codigo < 0 else "fallida" if codigo
              else "sin_avance" if paso == e["fase"] else "terminada")
    r = {"fase": FASES[e["fase"]], "harness": HARNESSES[e["harness"]]["nombre"], "modelo": e["modelo"],
         "inicio": e["inicio"], "estado": estado, "codigo": codigo}
    if con_log:
        with open(e["log"], "rb") as f:
            f.seek(max(f.seek(0, 2) - 6000, 0))
            r["log"] = f.read().decode(errors="replace")
    return r


def lanzar(d):
    """Lanza el agente configurado para el siguiente paso del PFG. ValueError si no se puede."""
    with CERROJO:
        if (e := EJECUCIONES.get(d.name)) and e["proc"].poll() is None:
            raise ValueError("ya hay una ejecución en curso para este PFG")
        r = resumen(d)
        if not r["paso"]:
            raise ValueError("este PFG ya tiene todas las fases hechas")
        cfg = config_ejecucion()[r["paso"]]
        argv = comando_agente(cfg["harness"], cfg["modelo"], r["comando"])
        if not shutil.which(argv[0]):
            raise ValueError(f"no se encuentra «{argv[0]}» en el PATH")
        log = d / "ejecuciones" / f"{time.strftime('%Y%m%d-%H%M%S')}-{r['paso']}.log"
        log.parent.mkdir(exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            f.write(f"$ {shlex.join(argv)}\n\n")
            f.flush()
            # Grupo propio para poder detener también los subprocesos del agente.
            proc = subprocess.Popen(argv, cwd=RAIZ, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        EJECUCIONES[d.name] = {"fase": r["paso"], "harness": cfg["harness"], "modelo": cfg["modelo"],
                               "inicio": time.time(), "log": log, "proc": proc}


def detener(e):
    if e["proc"].poll() is None:
        try:
            os.killpg(e["proc"].pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # terminó entre poll() y killpg()


def origen_local(host, origen, puerto):
    """Solo la propia página: otra web abierta en el navegador no puede leer memorias ni lanzar agentes.
    El Host frena el DNS rebinding; el Origin, que el navegador siempre manda entre sitios, frena el CSRF."""
    locales = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}
    return host in locales and (origen is None or origen in {f"http://{h}" for h in locales})


def detalle(d):
    indice = lista(leer(d / "secciones" / "indice.json"))
    r = resumen(d)
    return {**r, "ejecucion": ejecucion(d.name, r["paso"], con_log=True), "indice": indice,
            "lecturas": [leer(d / "secciones" / f"{s['n']:02d}.json") for s in indice],
            "analisis": leer(d / "analisis.json"), "preguntas": leer(d / "preguntas.json"),
            "clasificacion": leer(d / "clasificacion.json"), "categorias": leer(CATEGORIAS)}


def nuevo_dir(nombre):
    base = unicodedata.normalize("NFKD", Path(nombre).stem).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60] or "pfg"
    for i in range(1, 1000):
        d = PFGS / (base if i == 1 else f"{base}-{i}")
        try:
            d.mkdir(parents=True)
            return d
        except FileExistsError:
            continue
    raise RuntimeError("demasiados PFG con el mismo nombre")


class Handler(BaseHTTPRequestHandler):
    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        if not isinstance(cuerpo, bytes):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def pfg(self, ruta, patron):
        m = re.fullmatch(patron, ruta)
        d = m and PFGS / m.group(1)
        return d if d and (d / "memoria.pdf").exists() else None

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
        if ruta == "/api/config":
            return self.responder(200, vista_config())
        if ruta == "/api/pfgs":
            dirs = [d for d in PFGS.iterdir() if (d / "memoria.pdf").exists()] if PFGS.exists() else []
            return self.responder(200, sorted((resumen(d) for d in dirs), key=lambda r: -r["modificado"]))
        if d := self.pfg(ruta, r"/api/pfgs/([a-z0-9-]+)"):
            return self.responder(200, detalle(d))
        if d := self.pfg(ruta, r"/pfgs/([a-z0-9-]+)/memoria\.pdf"):
            return self.responder(200, (d / "memoria.pdf").read_bytes(), "application/pdf")
        self.responder(404, {"error": "no encontrado"})

    def do_POST(self):
        if not self.local():
            return
        url = urlparse(self.path)
        try:
            if url.path == "/api/config":
                cfg = validar_config(self.cuerpo_json())
                CONFIG_EJECUCION.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return self.responder(200, vista_config())
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/ejecutar"):
                lanzar(d)
                return self.responder(201, {"ok": True})
            if d := self.pfg(url.path, r"/api/pfgs/([a-z0-9-]+)/detener"):
                if e := EJECUCIONES.get(d.name):
                    detener(e)
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
        d = nuevo_dir(parse_qs(url.query).get("nombre", ["pfg.pdf"])[0])
        (d / "memoria.pdf").write_bytes(datos)
        self.responder(201, {"id": d.name})

    def log_message(self, *args):
        pass  # el dashboard consulta cada pocos segundos; no llenar la terminal


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)
    except OSError:
        sys.exit(f"El puerto {puerto} está ocupado: ¿ya está abierto el dashboard? http://127.0.0.1:{puerto}")
    url = f"http://127.0.0.1:{puerto}"
    print(f"Dashboard del tribunal en {url} (Ctrl+C para parar)", flush=True)
    webbrowser.open(url)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for e in EJECUCIONES.values():  # sin el servidor nadie vería ni podría parar esos agentes
            detener(e)


if __name__ == "__main__":
    main()
