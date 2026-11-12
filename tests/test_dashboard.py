#!/usr/bin/env python3
"""Self-check del dashboard: fases con un agente falso y notas del lector. Uso: uv run tests/test_dashboard.py"""
import functools
import json
import os
import socket
import sys
import tarfile
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import server  # noqa: E402


def falla(f, *args):
    try:
        f(*args)
    except ValueError as e:
        return str(e)
    raise AssertionError(f"{f.__name__}{args} debía fallar")


# escribir aguanta que otro hilo tenga abierto el archivo: en Windows, os.replace fallaba con WinError 5.
with tempfile.TemporaryDirectory() as tmp:
    ruta = Path(tmp) / "grado.json"
    server.escribir(ruta, {"v": 1})
    with ruta.open(encoding="utf-8"):
        hilo = threading.Thread(target=server.escribir, args=(ruta, {"v": 2}))
        hilo.start()
        time.sleep(0.1)
    hilo.join()
    assert server.leer(ruta) == {"v": 2}

# Lo que todo agente falso tiene a mano: el prompt (claude -p <prompt>) y la carpeta del PFG que nombra.
PRELUDIO = '''import os, re, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
prompt = sys.argv[2] if len(sys.argv) > 2 else ""
def carpeta():
    return Path(os.environ["PFGS"]) / re.search(r"con el PFG ([a-z0-9-]*)", prompt).group(1)
'''


def agente_falso(ruta, codigo):
    """Un agente falso escrito en Python. Lo lanza un #!/bin/sh con exec (mismo PID, para killpg) o, en Windows, un
    .cmd como los que instala npm: Popen no ejecuta un script sin extensión. Devuelve la ruta que hay que lanzar."""
    py = ruta.with_name(ruta.name + "-falso.py")  # otro nombre: shutil.which("codex") no debe dar con codex.py
    py.write_text(PRELUDIO + codigo, encoding="utf-8")
    if os.name == "nt":
        ruta = ruta.with_name(ruta.name + ".cmd")
        ruta.write_text(f'@"{sys.executable}" "{py}" %*\n')
    else:
        ruta.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n')
        ruta.chmod(0o755)
    return str(ruta)


assert server.validar_config({}) == {f: {"harness": "claude", "modelo": "", "esfuerzo": ""} for f in server.FASES}
assert server.validar_config({"leer-pfg": {"harness": "pi", "modelo": "openai-codex/gpt-6-luna"}})["leer-pfg"]["harness"] == "pi"
assert "harness desconocido" in falla(server.validar_config, {"leer-pfg": {"harness": "bash"}})
assert "modelo no válido" in falla(server.validar_config, {"leer-pfg": {"modelo": "--dangerously-skip-permissions"}})
assert "modelo no válido" in falla(server.validar_config, {"leer-pfg": {"modelo": "opus; rm -rf /"}})
assert server.validar_config({"leer-pfg": {"harness": "pi", "esfuerzo": "minimal"}})["leer-pfg"]["esfuerzo"] == "minimal"
assert "Claude Code no admite el esfuerzo 'minimal'" in falla(server.validar_config, {"leer-pfg": {"esfuerzo": "minimal"}})
assert server.validar_config({"leer-pfg": {"harness": "agy", "esfuerzo": "high"}})["leer-pfg"]["esfuerzo"] == "high"
assert "por defecto" in falla(server.validar_config, {"leer-pfg": {"harness": "agy", "esfuerzo": "max"}})
assert "claude-opus-4-6-thinking" in falla(server.validar_config, {"leer-pfg": {"harness": "agy", "modelo": "claude-opus-4-6-thinking", "esfuerzo": "low"}})
assert "esfuerzo" in falla(server.validar_config, {"leer-pfg": {"esfuerzo": "--dangerously-skip-permissions"}})

argv = server.comando_agente("claude", "opus", "high", "usa la skill leer-pfg con el PFG demo")
assert argv[:2] == ["claude", "-p"] and argv[2].startswith("usa la skill leer-pfg con el PFG demo. ")
assert "dontAsk" in argv and "Bash(uv run scripts/pfg.py:*)" in argv[-1] and argv[argv.index("--model") + 1] == "opus"
assert argv[argv.index("--effort") + 1] == "high"
assert "--model" not in server.comando_agente("pi", "", "", "x") and "--no-session" in server.comando_agente("pi", "", "", "x")
assert "--thinking" not in server.comando_agente("pi", "", "", "x")
assert server.comando_agente("pi", "", "low", "x")[-2:] == ["--thinking", "low"]
assert server.comando_agente("agy", "m", "", "x")[-2:] == ["--model", "m"]
assert server.comando_agente("agy", "m", "max", "x")[-4:] == ["--model", "m", "--effort", "max"]

argv = server.comando_agente("codex", "gpt-6-luna", "xhigh", "x")
assert argv[:2] == ["codex", "exec"] and "--sandbox" not in argv, "--sandbox y default_permissions no se combinan"
assert '"**/notas-personales.json"="deny"' in argv[argv.index('permissions.tribunal.extends=":workspace"') + 2]
assert argv[-3:-1] == ["-c", 'model_reasoning_effort="xhigh"']
assert "solo puedes ejecutar" not in argv[-1] and ".agents/skills" in argv[-1], "Codex lee con la shell"
assert server.HARNESSES["codex"]["env"] == {"UV_OFFLINE": "1"}
assert not any("reasoning" in a for a in server.comando_agente("codex", "", "", "x")) and "--model" not in server.comando_agente("codex", "", "", "x")
assert server.validar_config({"leer-pfg": {"harness": "codex", "modelo": "gpt-5.6-terra", "esfuerzo": "ultra"}})["leer-pfg"]["esfuerzo"] == "ultra"
assert "no admite el esfuerzo" in falla(server.validar_config, {"leer-pfg": {"harness": "codex", "esfuerzo": "ultra"}})

assert server.validar_config({"leer-pfg": {"harness": "opencode", "modelo": "opencode/beam-free", "esfuerzo": "xhigh"}})["leer-pfg"]["esfuerzo"] == "xhigh"
assert "solo admite" in falla(server.validar_config, {"leer-pfg": {"harness": "opencode", "modelo": "opencode/big-pickle"}})
assert "solo admite" in falla(server.validar_config, {"leer-pfg": {"harness": "opencode", "modelo": "anthropic/claude-opus-5-5"}})
assert "no admite el esfuerzo" in falla(server.validar_config, {"leer-pfg": {"harness": "opencode", "esfuerzo": "medium"}})
argv = server.comando_agente("opencode", "", "", "x")
assert argv[:4] == ["opencode", "run", "--standalone", "--auto"] and argv[argv.index("-m") + 1] == "opencode/glm-5.3-flash-free"
assert server.comando_agente("opencode", "opencode/beam-free", "low", "x")[-2] == "opencode/beam-free#low"
permisos = server.json.loads(server.HARNESSES["opencode"]["env"]["OPENCODE_CONFIG_CONTENT"])["permission"]
assert permisos["bash"]["*"] == "deny" and permisos["bash"]["uv run scripts/pfg.py *"] == "allow" and permisos["execute"] == "deny"
assert permisos["read"]["*notas-personales.json"] == "deny" and permisos["grep"] == "deny", "las notas personales no llegan al agente"
assert list(permisos["bash"].items())[-1] == ("*notas-personales.json*", "deny"), "en opencode gana la última regla que encaja"

assert server.origen_local("127.0.0.1:8765", None, 8765)
assert server.origen_local("localhost:8765", "http://localhost:8765", 8765)
assert not server.origen_local("127.0.0.1:8765", "https://evil.example", 8765), "CSRF desde otra web"
assert not server.origen_local("evil.example:8765", None, 8765), "DNS rebinding"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    server.PFGS, server.CONFIG_EJECUCION, server.GRADOS = tmp / "pfgs", tmp / "ejecucion.json", tmp / "grados"
    agente = tmp / "agente"
    server.HARNESSES["claude"]["bin"] = agente_falso(agente, '''
if "salir-mal" in prompt:
    sys.exit(3)
if "dormir" in prompt:
    time.sleep(30)
print("hecho: " + prompt)
''')
    d = server.PFGS / "demo"
    d.mkdir(parents=True)
    (d / "memoria.pdf").write_bytes(b"%PDF")

    def esperar(estado):
        for _ in range(50):
            paso = server.resumen(d)["paso"]
            if server.ejecucion("demo", paso)["estado"] == estado:
                return server.ejecucion("demo", paso, con_log=True)
            time.sleep(0.1)
        raise AssertionError(f"no llegó a {estado}: {server.ejecucion('demo', server.resumen(d)['paso'])}")

    server.lanzar(d)
    e = esperar("sin_avance")
    assert e["fase"] == "Lectura de la memoria" and e["paso"] == "leer-pfg" and "hecho: usa la skill leer-pfg con el PFG demo." in e["log"], e["log"]
    assert server.resumen(d)["ejecutor"] == "Claude Code"
    server.PROMPT = "{comando} avanzar"
    agente_falso(agente, '''
if "salir-mal" in prompt:
    sys.exit(3)
if "dormir" in prompt:
    time.sleep(30)
elif "avanzar" in prompt:
    Path(os.environ["PFG"], "analisis.json").write_text('{"titulo": "T"}')
print("hecho: " + prompt)
''')
    server.os.environ["PFG"] = str(d)
    server.lanzar(d)
    esperar("terminada")
    (d / "analisis.json").unlink()

    server.PROMPT = "{comando} salir-mal"
    server.lanzar(d)
    assert esperar("fallida")["codigo"] == 3

    server.PROMPT = "{comando} dormir"
    server.lanzar(d)
    assert "en curso" in falla(server.lanzar, d), "una sola ejecución por PFG"
    server.detener(server.EJECUCIONES["demo"])
    esperar("detenida")

    # Con el índice y sin el análisis, «leyendo» solo mientras vive una lectura; si no, se quedó a medias.
    (d / "secciones").mkdir()
    (d / "secciones" / "indice.json").write_text(json.dumps([{"n": 1}, {"n": 2}]))
    (d / "secciones" / "01.json").write_text("{}")
    r = server.resumen(d)
    assert (r["estado"], r["paso"], r["leidas"], r["secciones"]) == ("a_medias", "leer-pfg", 1, 2), r
    server.EJECUCIONES.pop("demo")  # como tras reiniciar el servidor
    assert server.resumen(d)["estado"] == "a_medias", "sin ejecución viva no está leyendo"
    server.lanzar(d)
    assert server.resumen(d)["estado"] == "leyendo", "con la lectura en curso sí"
    server.detener(server.EJECUCIONES["demo"])
    esperar("detenida")
    assert server.resumen(d)["estado"] == "a_medias"
    server.shutil.rmtree(d / "secciones")

    agente_falso(agente, '''
P = carpeta()
if "dormir" in prompt or "PFG lenta" in prompt:
    time.sleep(30)
elif "PFG rota" in prompt:
    (P / "analisis.json").write_text('{"titulo": "T"}')
    sys.exit(3)
elif "leer-pfg" in prompt:
    time.sleep(0.5)
    (P / "analisis.json").write_text('{"titulo": "T"}')
elif "preguntas-pfg" in prompt:
    time.sleep(0.3)
    (P / "preguntas.json").write_text("[]")
    (P / "clasificacion.json").write_text("{}")
print("hecho: " + prompt)
''')
    server.os.environ["PFGS"] = str(server.PFGS)
    server.PROMPT = "{comando} cola"
    otra, rota, lenta = (server.PFGS / n for n in ["otra", "rota", "lenta"])
    for p in (otra, rota, lenta):
        p.mkdir()
        (p / "memoria.pdf").write_bytes(b"%PDF")
    threading.Thread(target=server.preparar_cola, daemon=True).start()
    threading.Thread(target=server.descargar_cola, daemon=True).start()

    def preparar(*dirs, hasta):
        for p in dirs:
            server.encolar(p)
        vistos = []
        for _ in range(100):
            r = {p.name: server.resumen(p) for p in dirs}
            en_curso = [k for k, v in r.items() if (v["ejecucion"] or {}).get("estado") == "en_curso"]
            assert len(en_curso) < 2, f"de uno en uno: {en_curso}"
            vistos.append((en_curso, r))
            if hasta(r):
                return vistos
            time.sleep(0.05)
        raise AssertionError(f"la cola no terminó: {r}")

    vistos = preparar(d, otra, hasta=lambda r: all(v["estado"] == "clasificadas" for v in r.values()))
    leyendo = [r for en_curso, r in vistos if en_curso == ["demo"] and r["demo"]["ejecucion"]["fase"] == "Lectura de la memoria"]
    assert leyendo, "se vio leer a demo"
    assert all(r["otra"]["cola"] == 1 and r["otra"]["ejecucion"] is None for r in leyendo), "otra espera su turno"
    assert leyendo[0]["demo"]["ejecucion"]["despues"] == "Preguntas para la defensa"
    assert server.EJECUCIONES["otra"]["fase"] == "preguntas-pfg" and server.resumen(otra)["cola"] is None
    for p in (d, otra):
        for f in ["analisis.json", "preguntas.json", "clasificacion.json"]:
            (p / f).unlink()

    # otra puede llegar a clasificadas antes de que salga el proceso de rota: espera también a su fallo.
    preparar(rota, otra, hasta=lambda r: r["otra"]["estado"] == "clasificadas"
             and (r["rota"]["ejecucion"] or {}).get("estado") == "fallida")
    assert server.EJECUCIONES["rota"]["fase"] == "leer-pfg", "una fase fallida no lanza la siguiente"
    assert server.resumen(rota)["ejecucion"]["estado"] == "fallida"
    for f in ["analisis.json", "preguntas.json", "clasificacion.json"]:
        (otra / f).unlink()

    preparar(lenta, otra, d, rota, hasta=lambda r: (r["lenta"]["ejecucion"] or {}).get("estado") == "en_curso" and r["rota"]["cola"])
    antes = {p.name: server.EJECUCIONES.get(p.name) for p in (otra, d)}
    server.desencolar(otra)
    assert server.resumen(otra)["cola"] is None and (otra / "memoria.pdf").exists(), "sacar de la cola no borra el PFG"
    assert server.resumen(d)["cola"] == 1, "el siguiente sube un puesto"
    server.desencolar(otra)
    server.borrar(rota)
    assert "rota" not in server.COLA and not rota.exists(), "borrar saca el PFG de la cola"
    server.desencolar()
    assert not server.COLA and server.resumen(d)["cola"] is None, "vaciar la cola"
    server.detener(server.EJECUCIONES["lenta"])
    for _ in range(50):
        if server.resumen(lenta)["ejecucion"]["estado"] == "detenida":
            break
        time.sleep(0.1)
    time.sleep(0.5)
    assert {p.name: server.EJECUCIONES.get(p.name) for p in (otra, d)} == antes, "lo sacado de la cola no se lanza"
    server.borrar(lenta)
    server.borrar(otra)
    assert not server.COLA

    (d / "clasificacion.json").write_text("{}")
    assert "todas las fases" in falla(server.lanzar, d)

    server.PROMPT = "{comando} dormir"
    (d / "clasificacion.json").unlink()
    server.lanzar(d)
    assert "detén la ejecución" in falla(server.borrar, d) and (d / "memoria.pdf").exists(), "no borra con un agente en marcha"
    server.detener(server.EJECUCIONES["demo"])
    esperar("detenida")
    server.borrar(d)
    assert not d.exists() and "demo" not in server.EJECUCIONES

    # Notas del lector. Las páginas son las que escribiría `pfg.py paginas` e `imagen`.
    d = server.PFGS / "notas"
    (d / "paginas").mkdir(parents=True)
    (d / "memoria.pdf").write_bytes(b"%PDF")
    (d / "paginas" / "indice.json").write_text(json.dumps([{"w": 595, "h": 842, "pag": None}] * 2 + [{"w": 595, "h": 842, "pag": "1"}]))
    (d / "paginas" / "p003.json").write_text(json.dumps({"palabras": [[.1, .1, .2, .12, w] for w in
                                                                      "La latencia baja un 30 %".split()]}))
    archivo = lambda nombre: json.loads((d / nombre).read_text(encoding="utf-8")) if (d / nombre).exists() else {}  # noqa: E731
    notas = lambda: {n["id"]: n for n in server.anotaciones(d)}  # noqa: E731

    server.guardar_anotacion(d, "aaaa1111", {"tipo": "agente", "pdf": 3, "palabras": [1, 2], "nota": "", "cita": "inventada"})
    assert archivo("anotaciones.json")["aaaa1111"]["cita"] == "latencia baja", "la cita sale de la página, no del navegador"
    assert notas()["aaaa1111"]["pag"] == "1" and not notas()["aaaa1111"]["pendiente"], "sin texto no hay nada que preguntar"
    assert "no hay notas pendientes" in falla(server.lanzar, d, "anotaciones-pfg")

    server.guardar_anotacion(d, "bbbb2222", {"tipo": "personal", "pdf": 1, "palabras": None, "nota": "Releer con calma"})
    assert set(archivo("notas-personales.json")) == {"bbbb2222"} and "bbbb2222" not in archivo("anotaciones.json")
    assert not notas()["bbbb2222"]["pendiente"]

    server.guardar_anotacion(d, "aaaa1111", {"tipo": "agente", "pdf": 3, "palabras": [1, 2], "nota": "¿Frente a qué?"})
    assert notas()["aaaa1111"]["pendiente"] and notas()["aaaa1111"]["respuesta"] is None
    (d / "respuestas.json").write_text(json.dumps({"aaaa1111": {"nota": "¿Frente a qué?", "respuesta": [
        {"texto": "Frente al sistema anterior.", "pdf": 3, "pag": "1"}]}}))
    assert not notas()["aaaa1111"]["pendiente"] and notas()["aaaa1111"]["respuesta"][0]["pdf"] == 3
    server.guardar_anotacion(d, "aaaa1111", {"tipo": "agente", "pdf": 3, "palabras": [1, 2], "nota": "¿Con qué carga?"})
    assert notas()["aaaa1111"]["pendiente"] and notas()["aaaa1111"]["respuesta"], "editada: pendiente otra vez, con la respuesta vieja"

    creada = notas()["aaaa1111"]["creada"]
    server.guardar_anotacion(d, "aaaa1111", {"tipo": "personal", "pdf": 3, "palabras": [1, 2], "nota": "¿Con qué carga?"})
    assert "aaaa1111" not in archivo("anotaciones.json") and "aaaa1111" in archivo("notas-personales.json")
    assert notas()["aaaa1111"]["creada"] == creada and not notas()["aaaa1111"]["pendiente"], "el id y la fecha se conservan"
    server.guardar_anotacion(d, "aaaa1111", {"tipo": "preguntas", "pdf": 3, "palabras": [1, 2], "nota": "¿Con qué carga?"})
    assert archivo("anotaciones.json")["aaaa1111"]["tipo"] == "preguntas" and "aaaa1111" not in archivo("notas-personales.json")
    assert not notas()["aaaa1111"]["tarde"]
    (d / "preguntas.json").write_text("[]")
    time.sleep(0.01)
    server.guardar_anotacion(d, "cccc3333", {"tipo": "preguntas", "pdf": 3, "palabras": [0, 0], "nota": "Duda"})
    assert notas()["cccc3333"]["tarde"] and not notas()["aaaa1111"]["tarde"], "solo las creadas después de generar las preguntas"
    assert list(notas()) == ["bbbb2222", "cccc3333", "aaaa1111"], "por página y posición"

    for aid, raw, motivo in [
            ("../x", {"tipo": "agente", "pdf": 3, "palabras": None}, "id de nota"),
            ("dddd4444", {"tipo": "secreta", "pdf": 3, "palabras": None}, "tipo de nota"),
            ("dddd4444", {"tipo": "agente", "pdf": 4, "palabras": None}, "la página no existe"),
            ("dddd4444", {"tipo": "agente", "pdf": "3", "palabras": None}, "la página no existe"),
            ("dddd4444", {"tipo": "agente", "pdf": 3, "palabras": [0, 6]}, "no están en esa página"),
            ("dddd4444", {"tipo": "agente", "pdf": 3, "palabras": [2, 1]}, "no están en esa página"),
            ("dddd4444", {"tipo": "agente", "pdf": 3, "palabras": None, "nota": "x" * 4001}, "4000 caracteres")]:
        assert motivo in falla(server.guardar_anotacion, d, aid, raw), (raw, motivo)
    assert "dddd4444" not in notas()

    server.borrar_anotacion(d, "bbbb2222")
    server.borrar_anotacion(d, "bbbb2222")
    assert "bbbb2222" not in notas() and archivo("notas-personales.json") == {}

    server.PROMPT = "{comando}"
    server.guardar_anotacion(d, "eeee5555", {"tipo": "agente", "pdf": 3, "palabras": None, "nota": "¿Y la figura?"})
    server.lanzar(d, "anotaciones-pfg")
    assert server.EJECUCIONES["notas"]["proc"].wait() == 0
    e = server.ejecucion("notas", server.resumen(d)["paso"], con_log=True)
    assert e["estado"] == "sin_avance" and "usa la skill anotaciones-pfg con el PFG notas" in e["log"], e
    (d / "respuestas.json").write_text(json.dumps({"eeee5555": {"nota": "¿Y la figura?", "respuesta": []}}))
    assert server.ejecucion("notas", server.resumen(d)["paso"])["estado"] == "terminada"
    assert server.resumen(d)["paso"] == "preguntas-pfg", "responder notas no es un paso del flujo"
    assert "a demanda" in falla(server.lanzar, d, "leer-pfg")

    # Las rutas HTTP, con el mismo control de origen que el resto.
    srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"

    def pedir(ruta, cuerpo=None, origen=None):
        req = urllib.request.Request(base + ruta, None if cuerpo is None else json.dumps(cuerpo).encode(),
                                     {"Origin": origen} if origen else {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    assert pedir("/api/pfgs/notas/anotaciones/ffff6666", {"tipo": "agente", "pdf": 3, "palabras": [4, 5], "nota": "?"})[0] == 200
    codigo, cuerpo = pedir("/api/pfgs/notas")
    assert codigo == 200 and any(n["id"] == "ffff6666" and n["cita"] == "30 %" and n["pendiente"]
                                 for n in json.loads(cuerpo)["anotaciones"])
    assert pedir("/api/pfgs/notas/ejecutar", {"fase": "anotaciones-pfg"})[0] == 201
    server.EJECUCIONES["notas"]["proc"].wait()
    assert pedir("/api/pfgs/notas/anotaciones/ffff6666", {"tipo": "agente", "pdf": 9, "palabras": None})[0] == 409
    assert pedir("/api/pfgs/notas/anotaciones/ffff6666/borrar", {}, "https://evil.example")[0] == 403
    assert pedir("/api/pfgs/notas/anotaciones/ffff6666/borrar", {})[0] == 200 and "ffff6666" not in notas()
    assert pedir("/api/pfgs/notas/ejecutar", {"fase": "anotaciones-pfg"})[0] == 409, "ya no queda nada pendiente"
    codigo, cuerpo = pedir("/fuentes/Geist-Variable.woff2")
    assert codigo == 200 and cuerpo.startswith(b"wOF2")
    codigo, cuerpo = pedir("/pfgs/notas/paginas/p003.json")
    assert codigo == 200 and json.loads(cuerpo)["palabras"][1][4] == "latencia"
    assert pedir("/pfgs/notas/paginas/indice.json")[0] == 200
    assert pedir("/pfgs/notas/paginas/p3.png")[0] == 404 and pedir("/pfgs/notas/paginas/../memoria.pdf")[0] == 404

    # Harnesses instalados, con un PATH simulado: codex responde a --version, pi no está, opencode se cuelga
    # y agy está pero le falta el permiso. --version se pide una vez por binario hasta «Comprobar de nuevo».
    bins = tmp / "bin"
    bins.mkdir()
    llamadas = tmp / "llamadas"
    agente_falso(bins / "codex", f'''
with open({str(llamadas)!r}, "a") as f:
    f.write("x")
print("codex-cli 9.1.0")
''')
    agente_falso(bins / "opencode", "time.sleep(10)\n")
    agente_falso(bins / "agy", "sys.exit(1)\n")
    path, claude_bin, requisito = server.os.environ["PATH"], server.HARNESSES["claude"]["bin"], server.HARNESSES["agy"]["requisito"]
    server.os.environ["PATH"] = str(bins)
    server.HARNESSES["claude"]["bin"] = "claude"
    server.HARNESSES["agy"]["requisito"] = lambda: "Añade el permiso."
    server.VERSIONES.clear()
    inicio = time.time()
    hs = server.detectar()
    assert time.time() - inicio < 5, "un --version colgado no frena la carga más que su timeout"
    assert {k: v["estado"] for k, v in hs.items()} == {"claude": "no_instalado", "agy": "requisito", "pi": "no_instalado",
                                                      "codex": "instalado", "opencode": "instalado"}
    assert hs["codex"] == {"estado": "instalado", "version": "codex-cli 9.1.0", "problema": None}
    assert hs["opencode"]["version"] is None and hs["agy"]["version"] is None, "sin versión, pero instalado"
    assert hs["pi"]["problema"] == "No se encuentra «pi» en el PATH." and hs["agy"]["problema"] == "Añade el permiso."
    codigo, cuerpo = pedir("/api/config")
    c = json.loads(cuerpo)
    assert codigo == 200 and set(c) == {"fases", "error", "sistema", "version", "harnesses"} and list(c["harnesses"]) == list(server.HARNESSES)
    assert c["sistema"] == {"id": server.SISTEMA, "nombre": server.SISTEMAS[server.SISTEMA]}
    assert server.SISTEMA == {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    for k, v in c["harnesses"].items():
        assert set(v) == {"nombre", "modelos", "esfuerzos", "nota", "instalar", "estado", "version", "problema"}, k
        assert set(v["instalar"]) == {"comando", "url"} and v["instalar"]["url"].startswith("https://"), k
    # Cada sistema ve solo su comando: curl en macOS y Linux, PowerShell en Windows. OpenCode no tiene en Windows.
    sistema = server.SISTEMA
    for so in ["macos", "linux", "windows"]:
        server.SISTEMA = so
        c = server.vista_config()
        assert c["sistema"]["nombre"] == {"macos": "macOS", "linux": "Linux", "windows": "Windows"}[so]
        for k, v in c["harnesses"].items():
            cmd = v["instalar"]["comando"]
            if so != "windows":
                assert cmd.startswith("curl -fsSL https://"), (so, k)
            elif k == "opencode":
                assert cmd is None and v["instalar"]["url"] == "https://opencode.ai/docs", "solo el enlace"
            else:
                assert "irm https://" in cmd and cmd.endswith(("| iex", '| iex"')), k
    server.SISTEMA = sistema
    assert c["harnesses"]["codex"]["version"] == "codex-cli 9.1.0" and c["harnesses"]["pi"]["estado"] == "no_instalado"
    assert llamadas.read_text(encoding="utf-8").count("x") == 1, "la versión sale de la caché"
    agente_falso(bins / "pi", 'print("0.9")\n')
    assert server.detectar()["pi"] == {"estado": "instalado", "version": "0.9", "problema": None}, "lo recién instalado se ve sin reiniciar"
    assert pedir("/api/config/detectar", {}, "https://evil.example")[0] == 403
    codigo, cuerpo = pedir("/api/config/detectar", {})
    assert codigo == 200 and json.loads(cuerpo)["harnesses"]["codex"]["estado"] == "instalado"
    assert llamadas.read_text(encoding="utf-8").count("x") == 2, "«Comprobar de nuevo» vuelve a pedir la versión"
    server.os.environ["PATH"] = path
    server.HARNESSES["claude"]["bin"], server.HARNESSES["agy"]["requisito"] = claude_bin, requisito

    # Programas del grado. Las guías se descargan de un servidor local, no de internet. La de Deusto tarda 2 s.
    simultaneas, pedidas = {"ahora": 0, "max": 0}, []
    contar = threading.Lock()

    class Guias(BaseHTTPRequestHandler):
        def do_GET(self):
            ruta = urllib.parse.urlparse(self.path).path
            with contar:
                pedidas.append(ruta)
                simultaneas["ahora"] += 1
                simultaneas["max"] = max(simultaneas.values())
            try:
                if ruta in ("/a-ftp", "/a-file", "/a-guia"):
                    self.send_response(302)
                    self.send_header("Location", {"/a-ftp": "ftp://127.0.0.1/guia", "/a-file": "file:///etc/passwd", "/a-guia": "/guia"}[ruta])
                    self.end_headers()
                    return
                if ruta.startswith("/doa/"):
                    time.sleep(2)
                guia = "<p>Contenidos</p><p>TEMA 1: Redes</p><p>Estrategia de enseñanza</p>".encode("iso-8859-15")
                cuerpo = {"/doa/look%5bconpub%5dMostrarPubGuiaDocAs": guia, "/guia": guia,
                          "/grande": b"x" * (server.MAX_PROGRAMA + 1), "/guia.pdf": b"%PDF-1.4 guia"}.get(ruta)
                self.send_response(200 if cuerpo else 404)
                self.end_headers()
                self.wfile.write(cuerpo or b"no")
            finally:
                with contar:
                    simultaneas["ahora"] -= 1

        def log_message(self, *args):
            pass

    guias = server.ThreadingHTTPServer(("127.0.0.1", 0), Guias)
    threading.Thread(target=guias.serve_forever, daemon=True).start()
    web = f"http://127.0.0.1:{guias.server_port}"

    d = server.PFGS / "contrastar"
    d.mkdir()
    (d / "memoria.pdf").write_bytes(b"%PDF")
    (d / "analisis.json").write_text(json.dumps({"titulo": "T"}))
    assert server.resumen(d)["paso"] == "preguntas-pfg", "sin grados, como siempre"
    assert "carga antes los programas" in falla(server.lanzar, d, "grado-pfg")
    codigo, cuerpo = pedir("/api/grados", {"nombre": "  Grado en Ingeniería Informática "})
    assert codigo == 201 and json.loads(cuerpo) == {"id": "grado-en-ingenieria-informatica"}
    g = server.GRADOS / "grado-en-ingenieria-informatica"
    assert json.loads((g / "grado.json").read_text(encoding="utf-8")) == {"nombre": "Grado en Ingeniería Informática", "fuentes": {}}
    assert pedir("/api/grados", {"nombre": "Grado en Ingeniería Informática"})[0] == 409, "ya existe"
    assert pedir("/api/grados", {"nombre": " "})[0] == 409
    assert server.resumen(d)["paso"] == "preguntas-pfg", "un grado sin programas no cambia el flujo"

    def subir(nombre, datos):
        req = urllib.request.Request(f"{base}/api/grados/{g.name}/programas?nombre={urllib.parse.quote(nombre)}", datos)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    assert subir("Redes II.pdf", b"%PDF-1.4 redes") == (201, {"slug": "redes-ii"})
    assert subir("Sistemas Operativos.txt", "Tema 1. Procesos".encode()) == (201, {"slug": "sistemas-operativos"})
    assert subir("falso.pdf", b"hola")[0] == 409 and subir("guia.docx", b"PK")[0] == 409
    pagina = b"<p>Tema 1. Consultas</p><script>fetch('/api/pfgs')</script>"
    for nombre in ("guia.html", "guia.htm"):
        assert subir(nombre, pagina) == (201, {"slug": "guia"}), nombre
        assert (g / "programas" / "guia.html").read_bytes() == pagina, nombre
        dg = json.loads(pedir(f"/api/grados/{g.name}")[1])
        assert [a["origen"] for a in dg["asignaturas"] if a["slug"] == "guia"] == ["HTML"], dg
        with urllib.request.urlopen(f"{base}/grados/{g.name}/programas/guia.html") as r:
            assert r.headers["Content-Type"] == "text/plain; charset=utf-8" and r.read() == pagina
            assert r.headers["X-Content-Type-Options"] == "nosniff", "una página subida nunca se ejecuta como HTML"
    assert sorted(p.name for p in (g / "programas").iterdir()) == ["guia.html", "redes-ii.pdf", "sistemas-operativos.txt"]
    assert server.resumen(d)["paso"] == "grado-pfg", "con programas, tras la lectura toca contrastar"
    assert server.detalle(d)["contrastable"] and not server.detalle(d)["desfase"]

    deusto = f"{web}/doa/look%5bconpub%5dMostrarPubGuiaDocAs"

    def descargas(gid, hasta=lambda ds: all(x["estado"] in ("hecha", "fallida") for x in ds)):
        vistas = []
        for _ in range(200):
            ds = json.loads(pedir(f"/api/grados/{gid}")[1])["descargas"]
            vistas.append([x["estado"] for x in ds])
            assert vistas[-1].count("descargando") <= 1, vistas[-1]
            if hasta(ds):
                return ds, vistas
            time.sleep(0.05)
        raise AssertionError(vistas[-1])

    antes = time.monotonic()
    codigo, cuerpo = pedir(f"/api/grados/{g.name}/urls", {"urls": [
        f"{deusto}?_codAsignatura=145320&_anyoAcad=2026", f"{web}/no-existe", f"{web}/grande", f"{web}/guia.pdf",
        "file:///etc/passwd", f"{web}/a-ftp", f"{web}/a-file", ""]})
    assert codigo == 202 and time.monotonic() - antes < 1, "responde sin esperar a la guía de 2 s"
    assert [x["estado"] for x in json.loads(cuerpo)] == ["en_cola"] * 7
    r, vistas = descargas(g.name)
    assert ["descargando"] + ["en_cola"] * 6 in vistas, "mientras baja la lenta, las demás esperan"
    assert [x["estado"] for x in r] == ["hecha", "fallida", "fallida", "hecha", "fallida", "fallida", "fallida"], r
    assert [x.get("slug") for x in r] == ["145320", None, None, "guia", None, None, None], r
    assert "404" in r[1]["error"] and "5 MB" in r[2]["error"] and "http o https" in r[4]["error"]
    assert "redirige a ftp://127.0.0.1/guia" in r[5]["error"] and "redirige a file:///etc/passwd" in r[6]["error"], r
    assert simultaneas["max"] == 1, "de una en una"
    assert sorted(p.name for p in (g / "programas").iterdir()) == ["145320.html", "guia.pdf", "redes-ii.pdf", "sistemas-operativos.txt"]
    assert (g / "programas" / "145320.html").read_bytes().startswith(b"<p>Contenidos") and (g / "programas" / "guia.pdf").exists()
    assert json.loads((g / "grado.json").read_text(encoding="utf-8"))["fuentes"] == {"145320": r[0]["url"], "guia": f"{web}/guia.pdf"}

    (g / "asignaturas").mkdir()
    ficha = {"asignatura": "Arquitectura", "codigo": "145320", "curso": 3, "caracter": "optativa",
             "temas": [{"id": "TEMA 2", "texto": "Jerarquía de memoria"}, {"id": "TEMA 3", "texto": "Procesadores"}]}
    (g / "asignaturas" / "145320.json").write_text(json.dumps(ficha))
    (g / "asignaturas" / "redes-ii.json").write_text(json.dumps({**ficha, "asignatura": "Redes II", "curso": 2}))
    dg = json.loads(pedir(f"/api/grados/{g.name}")[1])
    assert [(a["slug"], a["origen"], bool(a["ficha"])) for a in dg["asignaturas"]] == [
        ("redes-ii", "PDF", True), ("145320", "URL", True), ("guia", "URL", False), ("sistemas-operativos", "Texto", False)], dg
    assert dg["asignaturas"][1]["fuente"] == r[0]["url"] and (dg["programas"], dg["leidos"], dg["pfgs"]) == (4, 2, [])
    codigo, cuerpo = pedir(dg["asignaturas"][3]["fuente"])
    assert (codigo, cuerpo) == (200, "Tema 1. Procesos".encode())
    codigo, cuerpo = pedir(f"/grados/{g.name}/programas/145320.html")
    assert codigo == 200 and cuerpo.startswith(b"<p>Contenidos")
    with urllib.request.urlopen(f"{base}/grados/{g.name}/programas/145320.html") as r:
        assert r.headers["X-Content-Type-Options"] == "nosniff", "el navegador no debe adivinar HTML en el texto plano"
    assert pedir(f"/grados/{g.name}/programas/../grado.json")[0] == 404

    # Rehacer la ficha: misma asignatura, otra guía, tras una redirección http.
    codigo, cuerpo = pedir(f"/api/grados/{g.name}/urls", {"urls": [f"{web}/a-guia?_codAsignatura=145320"]})
    assert codigo == 202 and len(json.loads(cuerpo)) == 1, "las descargas terminadas se olvidan"
    assert [x["estado"] for x in descargas(g.name)[0]] == ["hecha"]
    assert not (g / "asignaturas" / "145320.json").exists(), "un programa sustituido pierde su ficha"
    (g / "asignaturas" / "145320.json").write_text(json.dumps(ficha))
    assert pedir(f"/api/grados/{g.name}/programas/guia/borrar", {})[0] == 200
    assert not (g / "programas" / "guia.pdf").exists() and "guia" not in json.loads((g / "grado.json").read_text(encoding="utf-8"))["fuentes"]

    # El contraste. El agente falso escribe lo que escribiría grado-pfg.
    agente_falso(agente, '''
if "nada" not in prompt and "grado-pfg" in prompt:
    (carpeta() / "contraste.json").write_text("{}")
print("hecho: " + prompt)
''')
    server.PROMPT = "{comando} nada"
    server.lanzar(d)
    assert server.EJECUCIONES["contrastar"]["fase"] == "grado-pfg" and server.EJECUCIONES["contrastar"]["proc"].wait() == 0
    assert server.ejecucion("contrastar", server.resumen(d)["paso"])["estado"] == "sin_avance"
    (d / "grado.json").write_text(json.dumps({"grado": g.name, "titulacion": "Grado en Ingeniería Informática", "pdf": 1, "pag": "i"}))
    (d / "contraste.json").write_text(json.dumps({"grado": g.name, "motivo": "", "extiende": [], "aplica": [
        {"texto": "Usa caché.", "pdf": 3, "pag": "1", "temas": [{"asignatura": "145320", "tema": "TEMA 2"}]}]}))
    assert server.resumen(d)["paso"] == "preguntas-pfg", "contrastado: siguen las preguntas"
    det = server.detalle(d)
    assert det["grado_nombre"] == "Grado en Ingeniería Informática" and det["grado_programas"] == 3 and not det["desfase"]
    assert det["catalogo"] == {"145320": {"asignatura": "Arquitectura", "caracter": "optativa",
                                          "temas": {"TEMA 2": "Jerarquía de memoria", "TEMA 3": "Procesadores"}}}, "solo las asignaturas que usa"
    assert json.loads(pedir(f"/api/grados/{g.name}")[1])["pfgs"] == [{"id": "contrastar", "titulo": "T"}]
    time.sleep(0.01)
    assert subir("Bases de datos.txt", b"Tema 1. SQL")[0] == 201
    assert server.detalle(d)["desfase"], "un programa nuevo deja el contraste desfasado"
    assert server.resumen(d)["paso"] == "preguntas-pfg", "el desfase es un aviso, no un estado"

    server.PROMPT = "{comando}"
    assert pedir("/api/pfgs/contrastar/ejecutar", {"fase": "grado-pfg"})[0] == 201, "rehacer el contraste a demanda"
    server.EJECUCIONES["contrastar"]["proc"].wait()
    assert server.ejecucion("contrastar", server.resumen(d)["paso"])["estado"] == "terminada"
    assert not server.detalle(d)["desfase"]

    (d / "grado.json").write_text(json.dumps({"grado": None, "titulacion": "Grado en ADE + Grado en Informática", "pdf": 1}))
    (d / "contraste.json").write_text(json.dumps({"grado": None, "motivo": "Doble grado sin cargar.", "aplica": [], "extiende": []}))
    det = server.detalle(d)
    assert det["paso"] == "preguntas-pfg" and det["grado_nombre"] is None and not det["desfase"], "sin grado también cuenta como hecho"

    # La cola contrasta entre la lectura y las preguntas.
    agente_falso(agente, '''
P = carpeta()
if "leer-pfg" in prompt:
    (P / "analisis.json").write_text('{"titulo": "T"}')
elif "grado-pfg" in prompt:
    (P / "contraste.json").write_text("{}")
elif "preguntas-pfg" in prompt:
    (P / "preguntas.json").write_text("[]")
    (P / "clasificacion.json").write_text("{}")
''')
    for f in ["analisis.json", "contraste.json", "grado.json"]:
        (d / f).unlink()
    server.encolar(d)
    for _ in range(100):
        if server.resumen(d)["estado"] == "clasificadas":
            break
        time.sleep(0.05)
    assert server.resumen(d)["estado"] == "clasificadas" and (d / "contraste.json").exists()

    # Borrar el grado con descargas pendientes: la que baja y las que esperan fallan sin guardar nada.
    pdfs = pedidas.count("/guia.pdf")
    assert pedir(f"/api/grados/{g.name}/urls", {"urls": [f"{deusto}?_codAsignatura=999", f"{web}/guia.pdf"]})[0] == 202
    descargas(g.name, lambda ds: ds[0]["estado"] == "descargando")
    assert pedir(f"/api/grados/{g.name}/borrar", {})[0] == 200 and not g.exists()
    for _ in range(100):
        if server.DESCARGAS[g.name][0]["estado"] != "descargando":
            break
        time.sleep(0.05)
    assert [(x["estado"], x["error"]) for x in server.DESCARGAS[g.name]] == [("fallida", "este grado ya no existe")] * 2
    assert not g.exists(), "la descarga en curso no recrea el grado"
    assert pedidas.count("/guia.pdf") == pdfs, "las que esperaban ni se piden"
    assert json.loads(pedir("/api/grados")[1]) == [] and server.resumen(d)["paso"] is None
    guias.shutdown()
    srv.shutdown()

# Actualizar: solo un avance directo hasta la release, nunca con cambios del docente ni con algo en marcha.
assert server.semver(server.VERSION), "VERSION debe ser x.y.z"
assert server.semver("v0.10.0") > server.semver("0.9.3") and server.semver("v1.2") is None and server.semver(None) is None
with tempfile.TemporaryDirectory() as tmp:
    tmp, raiz = Path(tmp), server.RAIZ

    def sh(*args, cwd=tmp):
        server.subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)

    sh("init", "-q", "-b", "main", "origen")
    (tmp / "origen" / "categorias.json").write_text("{}")
    sh("add", "categorias.json", cwd=tmp / "origen")
    for v in ("0.1.0", "0.2.0"):
        (tmp / "origen" / "VERSION").write_text(v + "\n")
        sh("add", "VERSION", cwd=tmp / "origen")
        sh("commit", "-qm", v, cwd=tmp / "origen")
        sh("tag", "v" + v, cwd=tmp / "origen")
    (tmp / "origen" / "VERSION").write_text("0.3.0-sin-publicar\n")
    sh("commit", "-qam", "sin publicar", cwd=tmp / "origen")
    sh("clone", "-q", "origen", "copia")
    copia = tmp / "copia"
    sh("reset", "-q", "--hard", "v0.1.0", cwd=copia)
    (copia / "pfgs").mkdir()
    (copia / "pfgs" / "dato").write_text("del docente")  # sin ignorar en este repo: tampoco bloquea
    server.RAIZ, server.VERSION, server.ULTIMA = copia, "0.1.0", {"version": "0.2.0", "url": "https://x"}
    try:
        assert server.estado_version() | {"url": None} == {"actual": "0.1.0", "ultima": "0.2.0", "url": None, "error": None,
                                                         "nueva": True, "modo": "git"}
        (copia / "VERSION").write_text("tocado\n")
        assert "VERSION" in falla(server.actualizar) and not server.CERROJO.locked()
        sh("checkout", "-q", "VERSION", cwd=copia)

        class Viva:
            def poll(self):
                return None
        server.EJECUCIONES["viva"] = {"proc": Viva()}
        assert "ejecuciones en curso" in falla(server.actualizar) and not server.CERROJO.locked()
        del server.EJECUCIONES["viva"]
        (copia / "categorias.json").write_text('{"mias": 1}')  # la versión nueva no lo cambia: se conserva

        reinicios = []
        server.reiniciar = lambda: reinicios.append(1)
        srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"
        assert pedir("/api/actualizar", {}, "https://evil.example")[0] == 403 and not reinicios
        assert pedir("/api/actualizar", {}) == (202, b'{"ok": true}') and reinicios == [1]
        assert (copia / "VERSION").read_text(encoding="utf-8") == "0.2.0\n", "llega a la release, no al último commit"
        assert (copia / "pfgs" / "dato").read_text(encoding="utf-8") == "del docente"
        assert (copia / "categorias.json").read_text(encoding="utf-8") == '{"mias": 1}'
        assert server.CERROJO.locked(), "nada empieza hasta el reinicio"
        server.CERROJO.release()

        server.VERSION = "0.2.0"
        assert not server.estado_version()["nueva"] and "última versión" in falla(server.actualizar)
        assert json.loads(pedir("/api/version")[1])["actual"] == "0.2.0"
        server.RAIZ, server.VERSION = tmp, "0.1.0"
        assert server.estado_version()["modo"] == "zip" and "no se instaló con git" in falla(server.actualizar)
        server.APP = True  # la app empaquetada: su carpeta de trabajo no es un clon de git
        assert server.estado_version()["modo"] == "app"

        # En la app, el botón baja de GitHub el tarball de la release y lo instala como el instalador de la app.
        paquete, casa, rel = tmp / "paquete", tmp / "casa", tmp / "rel" / "usuario-tribunal-pfg-abc123"
        for d, v in ((paquete, "0.1.0"), (rel, "0.2.0")):
            (d / "config").mkdir(parents=True)
            (d / "VERSION").write_text(v + "\n")
            (d / "config" / "categorias.json").write_text("{}" if v == "0.1.0" else '{"v": 2}')
        (rel / "scripts").mkdir()
        (rel / "scripts" / "codigo.json").write_text('["VERSION", "config/categorias.json"]')
        server.instalador.instalar(paquete, casa)
        tarballs = tmp / "web" / "repos" / server.REPO / "tarball"
        tarballs.mkdir(parents=True)
        with tarfile.open(tarballs / "v0.2.0", "w:gz") as tar:
            tar.add(rel, rel.name)

        class Silencio(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        web = server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Silencio, directory=str(tmp / "web")))
        threading.Thread(target=web.serve_forever, daemon=True).start()
        server.GITHUB, server.RAIZ = f"http://127.0.0.1:{web.server_port}", casa
        (casa / "config" / "categorias.json").write_text('{"mias": 1}')
        codigo, cuerpo = pedir("/api/actualizar", {})
        assert codigo == 409 and "config/categorias.json" in json.loads(cuerpo)["error"] and reinicios == [1]
        assert (casa / "VERSION").read_text() == "0.1.0\n" and not server.CERROJO.locked(), "no instala nada"
        (casa / "config" / "categorias.json").unlink()
        assert pedir("/api/actualizar", {}) == (202, b'{"ok": true}') and reinicios == [1, 1]
        assert (casa / "VERSION").read_text() == "0.2.0\n" and (casa / "config" / "categorias.json").read_text() == '{"v": 2}'
        assert not (casa / "scripts").exists(), "solo lo que lista codigo.json"
        assert server.CERROJO.locked(), "nada empieza hasta el reinicio"
        server.CERROJO.release()
        server.ULTIMA = {"version": "0.3.0"}  # sin tarball: GitHub responde 404
        assert "no se ha podido descargar" in falla(server.actualizar) and not server.CERROJO.locked()
        web.shutdown()
        srv.shutdown()
    finally:
        server.RAIZ, server.VERSION = raiz, (raiz / "VERSION").read_text(encoding="utf-8").strip()
        server.APP, server.GITHUB = False, "https://api.github.com"

# Lanzado por la app de escritorio: no abre el navegador y para cuando la app cierra su stdin.
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
proc = server.subprocess.Popen([sys.executable, str(Path(server.__file__)), str(puerto)], stdin=server.subprocess.PIPE,
                               stdout=server.subprocess.DEVNULL, env={**server.os.environ, "TRIBUNAL_APP": "1"})
for _ in range(100):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{puerto}/", timeout=1)
        break
    except OSError:
        time.sleep(0.1)
else:
    proc.kill()
    raise AssertionError("el servidor de la app no ha arrancado")
proc.stdin.close()
assert proc.wait(timeout=10) == 0, "al cerrar la app, el servidor para limpio"

print("ok")
