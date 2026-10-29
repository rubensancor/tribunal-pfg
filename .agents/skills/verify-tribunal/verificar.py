#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.49", "pymupdf>=1.24"]
# ///
"""Arnés de verificación del dashboard del tribunal. Instrucciones en SKILL.md.

  verificar.py arrancar               copia la app a una carpeta desechable y arranca el servidor
  verificar.py doctor                 ¿merece la pena conducir esta instancia?
  verificar.py estado [clave]         imprime el estado (url, puerto, app, pfgs, evidencia) o una clave
  verificar.py pdf <ruta> [paginas]   crea una memoria sintética (nunca uses memorias reales);
                                      una ruta relativa se guarda en la carpeta de evidencia
  verificar.py fase <id> <fase>       simula lo que escriben las skills: troceado|leyendo|leido|preguntas|clasificadas
  verificar.py navegar < guion.py     ejecuta Playwright con page, url, pfgs, evidencia y ev(nombre)
  verificar.py limpiar                para el servidor y borra la copia; conserva la evidencia

La ejecución activa es la de $VERIFY_RUN o, si no está, la última que se arrancó.
"""
import filecmp
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BASE = Path(os.environ.get("TMPDIR", "/tmp")) / "tribunal-pfg-verify"
COPIA = ["dashboard/server.py", "dashboard/index.html", "scripts/pfg.py", "config/categorias.json",
         "AGENTS.md", "CLAUDE.md",  # los agentes que lanza el dashboard necesitan las reglas y las skills
         *sorted(str(p.relative_to(REPO)) for d in (".agents", ".opencode") for p in (REPO / d).rglob("*") if p.is_file())]
FASES = ["troceado", "leyendo", "leido", "preguntas", "clasificadas"]


def run_id():
    rid = os.environ.get("VERIFY_RUN") or ((BASE / "actual").read_text().strip() if (BASE / "actual").exists() else "")
    if not rid or not (BASE / "runs" / rid / "estado.json").exists():
        sys.exit("no hay ninguna ejecución activa: ejecuta primero `verificar.py arrancar`")
    return rid


def estado():
    return json.loads((BASE / "runs" / run_id() / "estado.json").read_text())


def get(url, timeout=2):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode()


def arrancar():
    rid = time.strftime("%Y%m%d-%H%M%S")
    rd, evid = BASE / "runs" / rid, BASE / "evidencia" / rid
    app = rd / "app"
    for f in COPIA:
        (app / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / f, app / f)
    (app / "pfgs").mkdir()
    (app / ".claude").mkdir()
    for enlace in ("skills", "agents"):
        (app / ".claude" / enlace).symlink_to(f"../.agents/{enlace}")
    evid.mkdir(parents=True)
    # El servidor llama a webbrowser.open: lo capturamos en un log en vez de abrir una pestaña.
    abrir = rd / "abrir-navegador"
    abrir.write_text(f'#!/bin/sh\necho "$1" >> "{rd}/navegador.log"\n')
    abrir.chmod(0o755)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    log = open(rd / "servidor.log", "w")
    p = subprocess.Popen(["uv", "run", str(app / "dashboard" / "server.py"), str(puerto)], cwd=app,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                         env={**os.environ, "BROWSER": str(abrir)})
    est = {"run": rid, "puerto": puerto, "url": f"http://127.0.0.1:{puerto}", "pgid": p.pid,
           "app": str(app), "pfgs": str(app / "pfgs"), "evidencia": str(evid)}
    (rd / "estado.json").write_text(json.dumps(est, indent=2))
    (BASE / "actual").write_text(rid)
    for _ in range(60):
        if p.poll() is not None:
            sys.exit(f"el servidor terminó al arrancar:\n{(rd / 'servidor.log').read_text()}")
        try:
            if get(est["url"] + "/api/pfgs") == (200, "[]") and "Dashboard del tribunal en" in (rd / "servidor.log").read_text():
                print(json.dumps(est, indent=2))
                print(f"listo: {est['url']}  (export VERIFY_RUN={rid} para fijar esta ejecución)")
                return
        except OSError:
            pass
        time.sleep(0.5)
    sys.exit(f"el servidor no respondió en 30 s; log en {rd / 'servidor.log'}")


def doctor():
    est = estado()
    rd = BASE / "runs" / est["run"]
    fallos = []

    def check(ok, texto):
        print(("OK    " if ok else "FALLO ") + texto)
        ok or fallos.append(texto)

    try:
        os.killpg(est["pgid"], 0)
        vivo = True
    except OSError:
        vivo = False
    check(vivo, f"proceso del servidor vivo (grupo {est['pgid']})")
    lsof = subprocess.run(["lsof", "-nP", f"-iTCP:{est['puerto']}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True)
    pids = [int(x) for x in lsof.stdout.split()]
    nuestros = bool(pids) and all(os.getpgid(x) == est["pgid"] for x in pids)
    check(nuestros, f"el puerto {est['puerto']} lo escucha nuestro proceso (pids {pids})")
    try:
        _, html = get(est["url"] + "/")
        check("<title>Tribunal PFG</title>" in html, "la página / es el dashboard")
        _, api = get(est["url"] + "/api/pfgs")
        en_api = sorted(p["id"] for p in json.loads(api))
        en_disco = sorted(d.name for d in Path(est["pfgs"]).iterdir() if (d / "memoria.pdf").exists())
        check(en_api == en_disco, f"la API sirve la carpeta desechable {est['pfgs']} ({en_api})")
    except OSError as e:
        check(False, f"el servidor responde ({e})")
    desfase = [f for f in COPIA if not (Path(est["app"]) / f).exists() or not filecmp.cmp(REPO / f, Path(est["app"]) / f, shallow=False)]
    check(not desfase, f"la copia coincide con el checkout{f' (cambiado: {desfase}; vuelve a arrancar)' if desfase else ''}")
    nav = rd / "navegador.log"
    print(f"info  apertura de navegador capturada: {nav.read_text().strip() if nav.exists() else 'ninguna'}")
    print(f"info  evidencia en {est['evidencia']}")
    sys.exit(1 if fallos else 0)


def pdf(ruta, paginas=24):
    import pymupdf
    ruta = Path(estado()["evidencia"]) / ruta  # una ruta relativa queda junto a la evidencia
    doc = pymupdf.open()
    for i in range(paginas):
        doc.new_page().insert_text((72, 72), f"Memoria sintética de verificación. Página {i + 1}.")
    tercio = max(paginas // 3, 1)
    doc.set_toc([[1, "Introducción", 3], [1, "Desarrollo", 3 + tercio], [1, "Conclusiones", min(3 + 2 * tercio, paginas)]])
    doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
                         {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1}])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ruta)
    print(ruta)


def ancla(pdf_n, texto):
    return {"texto": f"[sintético] {texto}", "pdf": pdf_n, "pag": str(max(pdf_n - 2, 1))}


def fase(pfg_id, objetivo):
    if objetivo not in FASES:
        sys.exit(f"fase desconocida {objetivo!r}; usa una de {FASES}")
    est = estado()
    d = Path(est["pfgs"]) / pfg_id
    if not (d / "memoria.pdf").exists():
        sys.exit(f"no existe {d / 'memoria.pdf'}: sube antes el PDF por el dashboard")
    cli = ["uv", "run", str(Path(est["app"]) / "scripts" / "pfg.py")]
    sd = d / "secciones"
    if not (sd / "indice.json").exists():
        subprocess.run(cli + ["trocear", pfg_id], check=True)
    n = FASES.index(objetivo)
    indice = json.loads((sd / "indice.json").read_text())
    # Las fases son acumulativas; se borra lo que corresponde a fases posteriores.
    for f in [*sd.glob("[0-9][0-9].json"), d / "analisis.json", d / "preguntas.json", d / "clasificacion.json"]:
        f.unlink(missing_ok=True)
    leidas = indice[:1] if objetivo == "leyendo" else indice if n >= 2 else []
    for s in leidas:
        (sd / f"{s['n']:02d}.json").write_text(json.dumps({
            "resumen": f"[sintético] Resumen de {s['titulo']}.", "puntos_clave": [ancla(s["pdf_ini"], "Punto clave")],
            "decisiones": [{**ancla(s["pdf_ini"], "Decisión"), "justificada": False}], "resultados": [],
            "tensiones": [{**ancla(s["pdf_ini"], "Tensión"), "tipo": "sin_evidencia"}], "no_legible": []},
            ensure_ascii=False))
    if n >= 2:
        (d / "analisis.json").write_text(json.dumps({
            "titulo": "Memoria sintética de verificación", "estudiante": "Estudiante Sintético",
            "titulacion": "Grado de prueba", "director": "Dirección de prueba", "paginas": indice[-1]["pdf_fin"],
            "desfase_paginas": 2, "que_hace": "[sintético] Qué hace.", "aportacion_propia": "[sintético] Aportación.",
            "decisiones": [ancla(5, "Decisión clave")], "resultados": [ancla(9, "Resultado principal")],
            "fortalezas": [ancla(4, "Fortaleza")], "debilidades": [ancla(10, "Debilidad")],
            "leer_al_menos": "[sintético] Capítulo 2.",
            "coherencia": [{"objetivo": "[sintético] Objetivo 1", "pdf": 3, "pag": "1", "evaluado": "parcial",
                            "evaluacion": {"pdf": 9, "pag": "7"}, "comentario": "[sintético] Comentario."}],
            "notas_tribunal": [ancla(6, "Nota para el tribunal")]}, ensure_ascii=False))
    if n >= 3:
        preguntas = [{"id": f"P{i}", "prioridad": i, "pregunta": f"[sintético] ¿Pregunta {i}?",
                      "anclaje": {"pdf": 4 + i, "pag": str(2 + i), "seccion": "Desarrollo", "cita": f"cita {i}"},
                      "por_que_importa": "x", "buena_respuesta": "x", "senal_alarma": "x", "repregunta": "x"}
                     for i in (1, 2, 3)]
        (d / "preguntas.json").write_text(json.dumps(preguntas, ensure_ascii=False))
    if n >= 4:
        cats = ["validacion", "validacion", "decisiones-diseno"]
        (d / "clasificacion.json").write_text(json.dumps(
            {f"P{i}": {"categoria": c, "motivo": "[sintético]"} for i, c in enumerate(cats, 1)}, ensure_ascii=False))
    if n >= 2:  # a medio leer, validar se queja con razón de las secciones que faltan
        sys.exit(subprocess.run(cli + ["validar", pfg_id]).returncode)


def navegar():
    from playwright.sync_api import sync_playwright
    est = estado()
    guion = sys.stdin.read()
    evid = Path(est["evidencia"])
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)  # Chrome del sistema: sin descargas
        ctx = nav.new_context(viewport={"width": 1280, "height": 900}, locale="es-ES")
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=est["url"])
        page = ctx.new_page()

        def ev(nombre):
            page.screenshot(path=evid / f"{nombre}.png", full_page=True)
            (evid / f"{nombre}.aria.txt").write_text(page.locator("body").aria_snapshot())
            print(f"evidencia: {evid / nombre}.png  {evid / nombre}.aria.txt")

        page.goto(est["url"] + "/")
        page.wait_for_function("document.querySelector('#main').children.length > 0")
        try:
            exec(compile(guion, "<guion>", "exec"), {"page": page, "url": est["url"], "pfgs": Path(est["pfgs"]),
                                                      "evidencia": evid, "ev": ev, "json": json})
        except Exception:
            ev(f"error-{time.strftime('%H%M%S')}")
            raise
        finally:
            nav.close()


def limpiar():
    est = estado()
    rd = BASE / "runs" / est["run"]
    try:
        os.killpg(est["pgid"], signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.25)
            os.killpg(est["pgid"], 0)
        os.killpg(est["pgid"], signal.SIGKILL)
    except OSError:
        pass  # ya no existe el grupo
    shutil.rmtree(rd)
    if (BASE / "actual").exists() and (BASE / "actual").read_text().strip() == est["run"]:
        (BASE / "actual").unlink()
    print(f"limpio: {rd} borrado; evidencia conservada en {est['evidencia']}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["arrancar"]:
        arrancar()
    elif a == ["doctor"]:
        doctor()
    elif a and a[0] == "estado" and len(a) <= 2:
        print(estado()[a[1]] if len(a) == 2 else json.dumps(estado(), indent=2))
    elif len(a) in (2, 3) and a[0] == "pdf":
        pdf(a[1], int(a[2]) if len(a) == 3 else 24)
    elif len(a) == 3 and a[0] == "fase":
        fase(a[1], a[2])
    elif a == ["navegar"]:
        navegar()
    elif a == ["limpiar"]:
        limpiar()
    else:
        sys.exit(__doc__)
