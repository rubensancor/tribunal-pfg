#!/usr/bin/env python3
"""Dashboard local del tribunal PFG. Solo stdlib. Uso: uv run dashboard/server.py [puerto]"""
import json
import re
import sys
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
PFGS = RAIZ / "pfgs"
CATEGORIAS = RAIZ / "config" / "categorias.json"
INDEX = Path(__file__).resolve().parent / "index.html"
MAX_SUBIDA = 100 * 1024 * 1024


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
            "preguntas": len(preguntas),
            "comando": f"usa la skill {paso} con el PFG {d.name}" if paso else None,
            "modificado": max(p.stat().st_mtime for p in d.rglob("*"))}


def detalle(d):
    indice = lista(leer(d / "secciones" / "indice.json"))
    return {**resumen(d), "indice": indice,
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

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/":
            return self.responder(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if ruta == "/api/pfgs":
            dirs = [d for d in PFGS.iterdir() if (d / "memoria.pdf").exists()] if PFGS.exists() else []
            return self.responder(200, sorted((resumen(d) for d in dirs), key=lambda r: -r["modificado"]))
        if d := self.pfg(ruta, r"/api/pfgs/([a-z0-9-]+)"):
            return self.responder(200, detalle(d))
        if d := self.pfg(ruta, r"/pfgs/([a-z0-9-]+)/memoria\.pdf"):
            return self.responder(200, (d / "memoria.pdf").read_bytes(), "application/pdf")
        self.responder(404, {"error": "no encontrado"})

    def do_POST(self):
        url = urlparse(self.path)
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
    servidor.serve_forever()


if __name__ == "__main__":
    main()
