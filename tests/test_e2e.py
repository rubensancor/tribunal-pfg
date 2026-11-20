#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.49", "pymupdf>=1.24"]
# ///
"""E2E del dashboard en un navegador: el servidor de verdad, sobre una copia instalada como la de la app, con un agy
falso en el PATH. Recorre los caminos de tests/features.md. Uso: uv run tests/test_e2e.py [--ver] [--capturas <carpeta>] [--dejar]"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pymupdf
from playwright.sync_api import expect, sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import instalar  # noqa: E402

VER = "--ver" in sys.argv  # con ventana, para mirar el recorrido
CAPTURAS = Path(sys.argv[sys.argv.index("--capturas") + 1]) if "--capturas" in sys.argv else None  # una PNG por paso
DEJAR = "--dejar" in sys.argv  # al terminar, el dashboard de prueba sigue abierto para explorarlo a mano
expect.set_options(timeout=60_000)  # la primera página del lector instala pymupdf con uv

# Con dependencias del sistema solo en el CI de Linux: allí hace falta sudo y en local no.
deps = ["--with-deps"] if os.environ.get("CI") and sys.platform.startswith("linux") else []
subprocess.run([sys.executable, "-m", "playwright", "install", *deps, "chromium"], check=True)

# Lo que escribiría cada skill. Pasa `pfg.py validar`: si el contrato cambia, este test lo nota.
categoria = json.loads((RAIZ / "config" / "categorias.json").read_text(encoding="utf-8"))[0]["id"]
ancla = {"pdf": 2, "pag": "2"}
FALSO = {
    "leer-pfg": {"analisis.json": {
        "titulo": "Caché distribuida para el campus", "estudiante": "Estudiante de prueba",
        "titulacion": "Grado en Ingeniería Informática", "director": "", "paginas": 3, "desfase_paginas": 0,
        "que_hace": "Diseña una caché distribuida y mide su latencia.", "aportacion_propia": "La caché y sus medidas.",
        "decisiones": [{"texto": "Usa una caché en memoria.", **ancla}],
        "resultados": [{"texto": "La latencia baja un 30 %.", **ancla}],
        "fortalezas": [{"texto": "Mide antes y después.", **ancla}],
        "debilidades": [{"texto": "No dice frente a qué carga.", **ancla}],
        "leer_al_menos": "pág. 2", "coherencia": [], "notas_tribunal": []}},
    "preguntas-pfg": {
        "preguntas.json": [{"id": "P1", "prioridad": 1, "pregunta": "¿Frente a qué carga baja la latencia un 30 %?",
                            "anclaje": {**ancla, "seccion": "Resultados", "cita": "La latencia baja un 30 %"},
                            "por_que_importa": "Sin la carga, la cifra no se puede comparar.",
                            "buena_respuesta": "Usuarios simultáneos y repeticiones.",
                            "senal_alarma": "No sabe con qué carga midió.", "repregunta": "¿Cuántas repeticiones?"}],
        "clasificacion.json": {"P1": {"categoria": categoria, "motivo": "Pregunta por la medida."}}},
}
AGY = '''import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
if sys.argv[1:] == ["models"]:  # el onboarding pregunta así si hay sesión
    print("gemini-3.8-flash")
    sys.exit(0)
skill, pfg = re.search(r"usa la skill ([a-z-]+) con el PFG ([a-z0-9-]+)", " ".join(sys.argv)).groups()
d = Path("pfgs") / pfg  # el servidor lanza el agente en la raíz del proyecto
poner = lambda nombre, obj: (d / nombre).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
if skill == "anotaciones-pfg":
    notas = json.loads((d / "anotaciones.json").read_text(encoding="utf-8"))
    poner("respuestas.json", {aid: {"nota": n["nota"], "respuesta": [{"texto": "Respuesta del agente falso.", "pdf": n["pdf"], "pag": n["pag"]}]}
                              for aid, n in notas.items() if n["tipo"] == "agente"})
else:
    for nombre, obj in json.loads(Path(__file__).with_name("falso.json").read_text(encoding="utf-8"))[skill].items():
        poner(nombre, obj)
print("hecho:", skill)
'''


def agy_falso(carpeta):
    """agy en `carpeta`: un #!/bin/sh o, en Windows, un .cmd como los de npm, que lanzan agy.py."""
    carpeta.mkdir()
    (carpeta / "falso.json").write_text(json.dumps(FALSO, ensure_ascii=False), encoding="utf-8")
    (py := carpeta / "agy.py").write_text(AGY, encoding="utf-8")
    if os.name == "nt":
        (carpeta / "agy.cmd").write_text(f'@"{sys.executable}" "{py}" %*\n')
    else:
        (carpeta / "agy").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n')
        (carpeta / "agy").chmod(0o755)


def memoria(ruta):
    doc = pymupdf.open()
    for texto in ["Caché distribuida para el campus", "La latencia baja un 30 % frente a la versión anterior", "Conclusiones"]:
        doc.new_page().insert_text((72, 72), texto)
    doc.save(ruta)


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:  # Windows: el error de verdad, no el del borrado
    tmp = Path(tmp)
    raiz = tmp / "Tribunal PFG"  # con espacio, como Documentos/Tribunal PFG
    instalar.instalar(RAIZ, raiz)
    agy_falso(tmp / "bin")
    memoria(pdf := tmp / "memoria-prueba.pdf")
    puerto = puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    # TRIBUNAL_APP: no abre el navegador y se para al cerrar su stdin, igual en Windows
    servidor = subprocess.Popen(["uv", "run", "dashboard/server.py", str(puerto)], cwd=raiz, stdin=subprocess.PIPE,
                                env={**os.environ, "TRIBUNAL_APP": "1",
                                     "PATH": str(tmp / "bin") + os.pathsep + os.environ["PATH"]})
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/version")
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise AssertionError("el servidor no arranca")

        with sync_playwright() as pw:
            navegador = pw.chromium.launch(headless=not VER, slow_mo=300 if VER else 0)
            pag = navegador.new_page(viewport={"width": 1280, "height": 900})
            errores = []
            pag.on("pageerror", lambda e: errores.append(str(e)))
            foto = lambda nombre: CAPTURAS and pag.screenshot(path=CAPTURAS / f"{nombre}.png")  # noqa: E731
            pag.goto(base)

            # A. Lista vacía; subir con «Leer y preguntar al cargar» pasa por la cola hasta «Listo».
            expect(pag.get_by_text("Aún no hay ningún PFG")).to_be_visible()
            foto("1-lista-vacia")
            pag.get_by_label("Leer y preguntar al cargar").check()
            pag.locator("#archivo").set_input_files(pdf)
            fila = pag.locator("article.fila", has_text="Caché distribuida para el campus")
            expect(fila.locator(".estado-texto")).to_have_text("Listo")
            expect(pag.locator(".resumen")).to_contain_text("1 listo para la defensa")
            foto("2-lista-lista")
            pfg_id = next((raiz / "pfgs").glob("*/memoria.pdf")).parent.name

            # B. La ficha de lectura y las preguntas, con su página.
            fila.get_by_role("link", name="Caché distribuida para el campus").click()
            expect(pag.locator(".det-head .badge")).to_have_text("Listo")
            expect(pag.get_by_text("Diseña una caché distribuida y mide su latencia.")).to_be_visible()
            foto("3-ficha")
            pag.get_by_role("link", name=re.compile(r"^Preguntas · 1")).click()
            expect(pag.get_by_text("¿Frente a qué carga baja la latencia un 30 %?")).to_be_visible()

            foto("4-preguntas")

            # C. El lector: página 2, seleccionar «latencia baja», preguntar al agente y enviarlo.
            pag.get_by_role("link", name="Leer memoria").click()
            lector = pag.locator("#lector")
            expect(lector).to_be_visible()
            lector.get_by_label("Página siguiente").click()
            expect(pag.locator("#donde")).to_contain_text("PDF 2/3")
            palabra = lambda t: pag.locator('#hojas [data-pdf="2"] .capa span').filter(has_text=re.compile(f"^{t}$"))
            expect(palabra("latencia")).to_be_attached()
            a, b = palabra("latencia").bounding_box(), palabra("baja").bounding_box()
            pag.mouse.move(a["x"] + 1, a["y"] + a["height"] / 2)
            pag.mouse.down()
            pag.mouse.move(b["x"] + b["width"] - 1, b["y"] + b["height"] / 2, steps=5)
            pag.mouse.up()
            foto("5-seleccion")
            pag.locator("#pop").get_by_role("button", name="Preguntar al agente").click()
            nota = pag.locator("#lista-notas textarea").first
            expect(nota).to_be_focused()
            nota.fill("¿Frente a qué versión?")
            nota.blur()
            expect(lector.locator("[data-ver-notas]")).to_have_text("Notas · 1")
            lector.get_by_role("button", name=re.compile(r"^Enviar 1 pregunta al agente")).click()
            expect(pag.locator("#lista-notas")).to_contain_text("Respuesta del agente falso.")
            foto("6-respuesta")
            guardada = json.loads((raiz / "pfgs" / pfg_id / "anotaciones.json").read_text(encoding="utf-8"))
            assert [(n["tipo"], n["pdf"], n["cita"], n["nota"]) for n in guardada.values()] == \
                [("agente", 2, "latencia baja", "¿Frente a qué versión?")], guardada

            # La nota sigue ahí tras cerrar el lector y recargar.
            pag.keyboard.press("Escape")
            expect(lector).to_be_hidden()
            pag.reload()
            pag.get_by_role("link", name="Leer memoria").click()
            expect(pag.locator("#lista-notas")).to_contain_text("Respuesta del agente falso.")
            expect(pag.locator("#lista-notas textarea").first).to_have_value("¿Frente a qué versión?")

            lector.get_by_label("Página siguiente").click()
            pag.wait_for_function("document.querySelector('#hojas [data-pdf=\"2\"] img')?.naturalWidth > 0")  # la página se ve
            foto("7-tras-recargar")
            assert not errores, errores
            navegador.close()

        r = subprocess.run(["uv", "run", "scripts/pfg.py", "validar", pfg_id], cwd=raiz, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        print("E2E OK", flush=True)
        if DEJAR:  # sin pfgs/ de verdad: aquí no hay memorias de nadie
            print(f"Dashboard de prueba en {base}, con el PFG {pfg_id} y su nota. Ctrl+C para cerrarlo.", flush=True)
            try:
                servidor.wait()
            except KeyboardInterrupt:
                pass
    finally:
        servidor.stdin.close()
        servidor.wait(timeout=30)

