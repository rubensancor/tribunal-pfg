#!/usr/bin/env python3
"""Self-check de la copia de la app a la carpeta de trabajo. Uso: uv run tests/test_instalar.py"""
import json
import os
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from instalar import CODIGO, MANIFIESTO, desde_release, instalar  # noqa: E402


def escribe(p, texto):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texto)


with tempfile.TemporaryDirectory() as tmp:
    app, casa = Path(tmp) / "app", Path(tmp) / "Tribunal PFG"
    escribe(app / "VERSION", "0.1.0\n")
    escribe(app / "dashboard" / "server.py", "v1")
    escribe(app / "config" / "categorias.json", "v1")
    escribe(app / "scripts" / "viejo.py", "v1")
    escribe(app / "scripts" / "mio.py", "v1")
    escribe(app / ".agents" / "skills" / "leer-pfg" / "SKILL.md", "v1")
    escribe(app / "scripts" / "__pycache__" / "x.pyc", "basura")
    (app / ".claude").mkdir()
    try:  # como en el repo: .claude/skills -> ../.agents/skills
        os.symlink(os.path.join("..", ".agents", "skills"), app / ".claude" / "skills", target_is_directory=True)
    except OSError:  # Windows sin permisos para enlaces: se prueba el resto
        pass

    assert instalar(app, casa) == {"version": "0.1.0", "conflictos": []}
    assert (casa / "dashboard" / "server.py").read_text() == "v1" and (casa / "VERSION").read_text() == "0.1.0\n"
    assert not (casa / "scripts" / "__pycache__").exists()
    if (app / ".claude" / "skills").is_symlink():
        assert (casa / ".claude" / "skills" / "leer-pfg" / "SKILL.md").read_text() == "v1"
        assert not (casa / ".claude" / "skills").is_symlink(), "el enlace se copia como carpeta, también vale en Windows"

    # Lo del docente: nada de esto viene en la app.
    escribe(casa / "pfgs" / "demo" / "memoria.pdf", "del docente")
    escribe(casa / "config" / "ejecucion.json", "{}")
    escribe(casa / "grados" / "gid" / "grado.json", "{}")
    # Cambia uno que la versión nueva también cambia, otro que no cambia y otro que la versión nueva quita.
    escribe(casa / "config" / "categorias.json", "mias")
    escribe(casa / "dashboard" / "server.py", "parche")
    escribe(casa / "scripts" / "mio.py", "mio")
    (casa / ".agents" / "skills" / "leer-pfg" / "SKILL.md").unlink()

    escribe(app / "VERSION", "0.2.0\n")
    escribe(app / "config" / "categorias.json", "v2")
    escribe(app / "scripts" / "nuevo.py", "v2")
    (app / "scripts" / "viejo.py").unlink()
    (app / "scripts" / "mio.py").unlink()
    assert instalar(app, casa) == {"version": "0.2.0", "conflictos": ["config/categorias.json"]}
    assert (casa / "config" / "categorias.json").read_text() == "mias", "el cambio del docente se conserva"
    assert (casa / "dashboard" / "server.py").read_text() == "parche", "la versión nueva no lo cambia: sin aviso"
    assert (casa / "scripts" / "nuevo.py").read_text() == "v2"
    assert not (casa / "scripts" / "viejo.py").exists(), "lo que la app ya no trae se borra"
    assert (casa / "scripts" / "mio.py").read_text() == "mio", "salvo si lo cambió el docente"
    assert (casa / ".agents" / "skills" / "leer-pfg" / "SKILL.md").read_text() == "v1", "lo borrado se repone"
    assert (casa / "pfgs" / "demo" / "memoria.pdf").read_text() == "del docente"
    assert (casa / "config" / "ejecucion.json").read_text() == "{}" and (casa / "grados" / "gid" / "grado.json").exists()
    assert not list(casa.rglob("*.tmp"))

    # El conflicto se avisa una vez: la versión siguiente ya no lo cambia y el docente sigue con el suyo.
    assert instalar(app, casa)["conflictos"] == []
    assert json.loads((casa / MANIFIESTO).read_text())["version"] == "0.2.0"

    # Por la línea de comandos, como lo llama app/main.js.
    salida = subprocess.run([sys.executable, str(RAIZ / "scripts" / "instalar.py"), str(app), str(casa)],
                            capture_output=True, text=True, check=True).stdout
    assert json.loads(salida) == {"version": "0.2.0", "conflictos": []}

    # El botón Actualizar baja el tarball de la release: todo el repo bajo una carpeta, con enlaces y lo de desarrollo.
    def tarball(version, categorias):
        ruta = Path(tmp) / f"release-{version}.tar.gz"
        with tarfile.open(ruta, "w:gz") as tar:
            def mete(nombre, texto):
                info = tarfile.TarInfo("usuario-tribunal-pfg-abc123/" + nombre)
                info.size = len(texto.encode())
                tar.addfile(info, io.BytesIO(texto.encode()))
            mete(CODIGO, json.dumps(["VERSION", "config/categorias.json", "dashboard", ".agents/skills/leer-pfg"]))
            mete("VERSION", version + "\n")
            mete("config/categorias.json", categorias)
            mete("dashboard/server.py", "v3")
            mete(".agents/skills/leer-pfg/SKILL.md", "v3")
            mete(".agents/skills/de-desarrollo/SKILL.md", "de desarrollo")
            mete("tests/test_pfg.py", "de desarrollo")
            mete("dashboard/../../fuera.txt", "se sale")
            mete("dashboard/..\\..\\fuera.txt", "se sale en Windows")
            enlace = tarfile.TarInfo("usuario-tribunal-pfg-abc123/.claude/skills")
            enlace.type, enlace.linkname = tarfile.SYMTYPE, "../.agents/skills"
            tar.addfile(enlace)
        return ruta

    try:
        desde_release(tarball("0.3.0", "v3"), casa)
        raise AssertionError("la versión nueva cambia lo que cambió el docente: no instala nada")
    except ValueError as e:
        assert "config/categorias.json, dashboard/server.py" in str(e)
    assert (casa / "VERSION").read_text() == "0.2.0\n" and not (casa / "tests").exists()
    (casa / "config" / "categorias.json").unlink()  # el docente guarda sus copias y los borra
    (casa / "dashboard" / "server.py").unlink()
    assert desde_release(tarball("0.3.0", "v3"), casa) == {"version": "0.3.0", "conflictos": []}
    assert (casa / "VERSION").read_text() == "0.3.0\n" and (casa / "config" / "categorias.json").read_text() == "v3"
    assert (casa / "dashboard" / "server.py").read_text() == "v3"
    assert (casa / ".claude" / "skills" / "leer-pfg" / "SKILL.md").read_text() == "v3", ".agents/ va también en .claude/"
    assert not (casa / "tests").exists() and not (casa / ".agents" / "skills" / "de-desarrollo").exists()
    assert not (casa / "scripts" / "nuevo.py").exists(), "lo que traía la app y la release ya no trae se borra"
    assert (casa / "pfgs" / "demo" / "memoria.pdf").read_text() == "del docente"
    assert not list(Path(tmp).rglob("fuera.txt")) and not list(Path(tmp).rglob("*..*")), "nada se sale de la carpeta"

    # Al abrir otra vez la app, su código (0.2.0) no deshace la actualización.
    assert instalar(app, casa) == {"version": "0.3.0", "conflictos": []}
    assert (casa / "VERSION").read_text() == "0.3.0\n" and not (casa / "scripts" / "nuevo.py").exists()
    escribe(app / "VERSION", "0.4.0\n")  # una app nueva, sí
    assert instalar(app, casa)["version"] == "0.4.0" and (casa / "scripts" / "nuevo.py").exists()

# Lo que lista codigo.json existe: una errata dejaría fuera del paquete y de la actualización una carpeta entera.
for p in json.loads((RAIZ / CODIGO).read_text()):
    assert (RAIZ / p).exists(), p

print("ok")
