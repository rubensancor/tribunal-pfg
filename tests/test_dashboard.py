#!/usr/bin/env python3
"""Self-check de la ejecución de fases del dashboard con un agente falso. Uso: uv run tests/test_dashboard.py"""
import sys
import tempfile
import threading
import time
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

    preparar(lenta, otra, hasta=lambda r: (r["lenta"]["ejecucion"] or {}).get("estado") == "en_curso" and r["otra"]["cola"])
    server.borrar(otra)
    assert "otra" not in server.COLA and not otra.exists(), "borrar saca el PFG de la cola"
    server.detener(server.EJECUCIONES["lenta"])
    for _ in range(50):
        if server.resumen(lenta)["ejecucion"]["estado"] == "detenida":
            break
        time.sleep(0.1)
    server.borrar(lenta)
    server.borrar(rota)
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

print("ok")
