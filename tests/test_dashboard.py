#!/usr/bin/env python3
"""Self-check de la ejecución de fases del dashboard con un agente falso. Uso: uv run tests/test_dashboard.py"""
import sys
import tempfile
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


assert server.validar_config({}) == {f: {"harness": "claude", "modelo": ""} for f in server.FASES}
assert server.validar_config({"leer-pfg": {"harness": "pi", "modelo": "openai-codex/gpt-6-luna"}})["leer-pfg"]["harness"] == "pi"
assert "harness desconocido" in falla(server.validar_config, {"leer-pfg": {"harness": "bash"}})
assert "modelo no válido" in falla(server.validar_config, {"leer-pfg": {"modelo": "--dangerously-skip-permissions"}})
assert "modelo no válido" in falla(server.validar_config, {"leer-pfg": {"modelo": "opus; rm -rf /"}})

argv = server.comando_agente("claude", "opus", "usa la skill leer-pfg con el PFG demo")
assert argv[:2] == ["claude", "-p"] and argv[2].startswith("usa la skill leer-pfg con el PFG demo. ")
assert "dontAsk" in argv and "Bash(uv run scripts/pfg.py:*)" in argv[-1] and argv[argv.index("--model") + 1] == "opus"
assert "--model" not in server.comando_agente("pi", "", "x") and "--no-session" in server.comando_agente("pi", "", "x")
assert server.comando_agente("agy", "m", "x")[-2:] == ["--model", "m"]

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
    assert e["fase"] == "Lectura de la memoria" and "hecho: usa la skill leer-pfg con el PFG demo." in e["log"], e["log"]
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

    (d / "clasificacion.json").write_text("{}")
    assert "todas las fases" in falla(server.lanzar, d)

print("ok")
