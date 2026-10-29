#!/usr/bin/env python3
"""Self-check del dashboard: fases con un agente falso y notas del lector. Uso: uv run tests/test_dashboard.py"""
import json
import sys
import tempfile
import threading
import time
import urllib.error
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

assert server.origen_local("127.0.0.1:8765", None, 8765)
assert server.origen_local("localhost:8765", "http://localhost:8765", 8765)
assert not server.origen_local("127.0.0.1:8765", "https://evil.example", 8765), "CSRF desde otra web"
assert not server.origen_local("evil.example:8765", None, 8765), "DNS rebinding"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    server.PFGS, server.CONFIG_EJECUCION = tmp / "pfgs", tmp / "ejecucion.json"
    agente = tmp / "agente"
    agente.write_text('#!/bin/sh\ncase "$2" in *salir-mal*) exit 3;; *dormir*) sleep 30;; esac\necho "hecho: $2"\n')
    agente.chmod(0o755)
    server.HARNESSES["claude"]["bin"] = str(agente)
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
    agente.write_text('#!/bin/sh\ncase "$2" in *salir-mal*) exit 3;; *dormir*) sleep 30;; '
                      '*avanzar*) echo "{\\"titulo\\": \\"T\\"}" > "$PFG/analisis.json";; esac\necho "hecho: $2"\n')
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

    agente.write_text('#!/bin/sh\nP="$PFGS/$(echo "$2" | sed "s/.*con el PFG \\([a-z0-9-]*\\).*/\\1/")"\n'
                      'case "$2" in *dormir*|*"PFG lenta"*) sleep 30;; '
                      '*"PFG rota"*) echo "{\\"titulo\\": \\"T\\"}" > "$P/analisis.json"; exit 3;; '
                      '*leer-pfg*) sleep 0.5; echo "{\\"titulo\\": \\"T\\"}" > "$P/analisis.json";; '
                      '*preguntas-pfg*) sleep 0.3; echo "[]" > "$P/preguntas.json"; echo "{}" > "$P/clasificacion.json";; '
                      'esac\necho "hecho: $2"\n')
    server.os.environ["PFGS"] = str(server.PFGS)
    server.PROMPT = "{comando} cola"
    otra, rota, lenta = (server.PFGS / n for n in ["otra", "rota", "lenta"])
    for p in (otra, rota, lenta):
        p.mkdir()
        (p / "memoria.pdf").write_bytes(b"%PDF")
    threading.Thread(target=server.preparar_cola, daemon=True).start()

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

    preparar(rota, otra, hasta=lambda r: r["otra"]["estado"] == "clasificadas")
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
    archivo = lambda nombre: json.loads((d / nombre).read_text()) if (d / nombre).exists() else {}  # noqa: E731
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
    codigo, cuerpo = pedir("/pfgs/notas/paginas/p003.json")
    assert codigo == 200 and json.loads(cuerpo)["palabras"][1][4] == "latencia"
    assert pedir("/pfgs/notas/paginas/indice.json")[0] == 200
    assert pedir("/pfgs/notas/paginas/p3.png")[0] == 404 and pedir("/pfgs/notas/paginas/../memoria.pdf")[0] == 404
    srv.shutdown()

print("ok")
