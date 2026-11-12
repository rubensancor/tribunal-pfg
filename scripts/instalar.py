#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Copia el código de la app de escritorio a la carpeta de trabajo. Lo ejecuta app/main.js en cada arranque.

  uv run scripts/instalar.py <origen> <destino>   imprime {"version", "conflictos"}

La carpeta de trabajo es donde corren el dashboard y los agentes. Solo se tocan los archivos que trae la app, así que
pfgs/, grados/ y config/ejecucion.json nunca. Un archivo que el docente ha cambiado se conserva; si la versión nueva
también lo cambia, sale en «conflictos». Lo que la app trajo y ya no trae se borra, salvo que el docente lo cambiara.
Si el botón Actualizar ya dejó la carpeta en una versión más nueva que la de la app, no se toca: no se vuelve atrás.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

MANIFIESTO = ".instalacion.json"  # {"version", "archivos": {ruta: sha256 de lo que copió la app}}
CODIGO = "scripts/codigo.json"  # lo que lleva la app; electron-builder y desde_release leen la misma lista


def version(v):
    """«0.2.0» -> (0, 2, 0); () si no es una versión, que queda por debajo de todas."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(map(int, m.groups())) if m else ()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def archivos(origen):
    """Rutas relativas con «/». Sigue los enlaces (.claude/skills): en Windows no se pueden crear sin permisos."""
    for raiz, dirs, nombres in os.walk(origen, followlinks=True):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in nombres:
            yield (Path(raiz) / n).relative_to(origen).as_posix()


def copiar(desde, hasta):
    hasta.parent.mkdir(parents=True, exist_ok=True)
    tmp = hasta.with_name(hasta.name + ".tmp")
    shutil.copyfile(desde, tmp)
    for _ in range(100):  # en Windows, os.replace falla (WinError 5) mientras el dashboard lee el archivo
        try:
            return os.replace(tmp, hasta)  # nunca queda un archivo a medias si la app se cierra copiando
        except PermissionError:
            time.sleep(0.01)
    os.replace(tmp, hasta)


def instalar(origen, destino, probar=False):
    """Con probar, solo devuelve los conflictos, sin tocar nada."""
    origen, destino = Path(origen), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    m = destino / MANIFIESTO
    hay = json.loads(m.read_text(encoding="utf-8")) if m.exists() else {}
    nueva = (origen / "VERSION").read_text().strip()
    if version(hay.get("version")) > version(nueva):
        return [] if probar else {"version": hay["version"], "conflictos": []}
    antes, ahora, conflictos = hay.get("archivos", {}), {}, []
    for ruta in sorted(archivos(origen)):
        nuevo, viejo, actual = sha(origen / ruta), antes.get(ruta), sha(destino / ruta)
        ahora[ruta] = nuevo
        if actual == nuevo:
            continue
        if actual is None or actual == viejo:  # falta, o nadie lo ha tocado desde la última copia
            if not probar:
                copiar(origen / ruta, destino / ruta)
        elif nuevo != viejo:  # lo cambió el docente y también la versión nueva: se queda el suyo
            conflictos.append(ruta)
    if probar:
        return conflictos
    for ruta, viejo in antes.items():
        if ruta not in ahora and sha(destino / ruta) == viejo:
            (destino / ruta).unlink()
    m.write_text(json.dumps({"version": nueva, "archivos": ahora}, indent=1) + "\n", encoding="utf-8")
    return {"version": nueva, "conflictos": conflictos}


def desde_release(tarball, destino):
    """Instala el código de una release desde el tarball de GitHub (todo el repo bajo <usuario>-<repo>-<sha>/), con los
    mismos archivos que lleva la app. Como el instalador de la app, copia .agents/ también en .claude/. A diferencia de
    él, no instala nada si la versión nueva cambia un archivo que el docente ha cambiado: lanza ValueError."""
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(tarball) as tar:
        nombres = tar.getnames()
        lista = next((n for n in nombres if n.count("/") == 2 and n.endswith("/" + CODIGO)), None)
        if not lista:
            raise ValueError(f"la release no trae {CODIGO}")
        raiz = lista.split("/")[0] + "/"
        codigo = json.load(tar.extractfile(lista))
        for t in tar.getmembers():  # solo archivos: los enlaces (.claude/ en el repo) se rehacen abajo como carpetas
            partes = t.name[len(raiz):].split("/") if t.name.startswith(raiz) else [".."]
            seguro = ".." not in partes and "\\" not in t.name  # nada se sale de tmp, tampoco en Windows
            if t.isfile() and seguro and any("/".join(partes[:len(c.split("/"))]) == c for c in codigo):
                (Path(tmp) / Path(*partes)).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp) / Path(*partes)).write_bytes(tar.extractfile(t).read())
        for p in codigo:
            if p.startswith(".agents/") and (Path(tmp) / p).is_dir():
                shutil.copytree(Path(tmp) / p, Path(tmp) / ".claude" / p[len(".agents/"):], dirs_exist_ok=True)
        if conflictos := instalar(tmp, destino, probar=True):
            raise ValueError("la versión nueva cambia archivos que tú has modificado: " + ", ".join(conflictos)
                             + ". Guarda una copia de los tuyos, bórralos, actualiza y vuelve a aplicar tus cambios")
        return instalar(tmp, destino)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(json.dumps(instalar(sys.argv[1], sys.argv[2])))  # en ASCII: la consola de Windows no es UTF-8
