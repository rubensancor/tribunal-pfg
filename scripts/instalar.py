#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Copia el código de la app de escritorio a la carpeta de trabajo. Lo ejecuta app/main.js en cada arranque.

  uv run scripts/instalar.py <origen> <destino>   imprime {"version", "conflictos"}

La carpeta de trabajo es donde corren el dashboard y los agentes. Solo se tocan los archivos que trae la app, así que
pfgs/, grados/ y config/ejecucion.json nunca. Un archivo que el docente ha cambiado se conserva; si la versión nueva
también lo cambia, sale en «conflictos». Lo que la app trajo y ya no trae se borra, salvo que el docente lo cambiara.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

MANIFIESTO = ".instalacion.json"  # {"version", "archivos": {ruta: sha256 de lo que copió la app}}


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
    os.replace(tmp, hasta)  # nunca queda un archivo a medias si la app se cierra copiando


def instalar(origen, destino):
    origen, destino = Path(origen), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    m = destino / MANIFIESTO
    antes = json.loads(m.read_text(encoding="utf-8"))["archivos"] if m.exists() else {}
    ahora, conflictos = {}, []
    for ruta in sorted(archivos(origen)):
        nuevo, viejo, actual = sha(origen / ruta), antes.get(ruta), sha(destino / ruta)
        ahora[ruta] = nuevo
        if actual == nuevo:
            continue
        if actual is None or actual == viejo:  # falta, o nadie lo ha tocado desde la última copia
            copiar(origen / ruta, destino / ruta)
        elif nuevo != viejo:  # lo cambió el docente y también la versión nueva: se queda el suyo
            conflictos.append(ruta)
    for ruta, viejo in antes.items():
        if ruta not in ahora and sha(destino / ruta) == viejo:
            (destino / ruta).unlink()
    version = (origen / "VERSION").read_text().strip()
    m.write_text(json.dumps({"version": version, "archivos": ahora}, indent=1) + "\n", encoding="utf-8")
    return {"version": version, "conflictos": conflictos}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(json.dumps(instalar(sys.argv[1], sys.argv[2])))  # en ASCII: la consola de Windows no es UTF-8
