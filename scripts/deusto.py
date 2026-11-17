#!/usr/bin/env python3
"""Rehace config/deusto.json con las asignaturas de cada grado de Deusto, de la consulta pública de guías docentes (gaude).

Uso: uv run scripts/deusto.py [año]   (el año académico que empieza, p. ej. 2026 para 2026/2027; por defecto, el actual)
Pide de una en una y con pausa: no saturar el servidor de la universidad.
"""
import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
from server import DESCARGADOR  # noqa: E402  el mismo TLS que las descargas del dashboard

COMBOS = "https://gaude.deusto.es/doa/consultaPublica/look[conpub]ActualizarCombosPubGuiaDocAs"
SALIDA = Path(__file__).resolve().parent.parent / "config" / "deusto.json"


def combo(accion, **campos):
    datos = {"_accion": accion, "_alumExternos": "N", "entradaPublica": "S", "idiomaPais": "es.ES", **campos}
    pet = urllib.request.Request(COMBOS, urllib.parse.urlencode(datos).encode(), {"User-Agent": "tribunal-pfg"})
    with DESCARGADOR.open(pet, timeout=30) as r:
        time.sleep(0.5)
        return json.loads(r.read().decode("iso-8859-15"))


def sin_codigo(texto):
    return texto.split(" - ", 1)[-1].strip()  # gaude antepone el código: «14402 - Grado en …»


def main():
    hoy = datetime.date.today()
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else hoy.year - (hoy.month < 9)
    estudios = {}
    for centro, nombre_centro in combo("actualizarComboCentros", _anoAcademico=ano)["centros"].items():
        if centro == "-1":
            continue
        for estudio, nombre in combo("actualizarComboEstudios", _anoAcademico=ano, _centro=centro)["estudios"].items():
            if not sin_codigo(nombre).startswith("Grado"):  # fuera másteres y títulos propios
                continue
            asignaturas = {}
            for plan in combo("actualizarComboPlan", _anoAcademico=ano, _centro=centro, _estudio=estudio)["planes"]:
                asignaturas |= {c: sin_codigo(n) for c, n in combo(
                    "actualizarComboAsignaturas", _anoAcademico=ano, _centro=centro, _estudio=estudio,
                    _planEstudio=plan, _curso=-1)["asignaturas"].items()}
            if asignaturas:
                estudios[estudio] = {"nombre": sin_codigo(nombre), "centro": sin_codigo(nombre_centro),
                                     "asignaturas": dict(sorted(asignaturas.items()))}
                print(f"{estudio} {sin_codigo(nombre)}: {len(asignaturas)} asignaturas", file=sys.stderr)
    assert estudios, "gaude no ha devuelto ningún grado: ¿ha cambiado la consulta pública?"
    SALIDA.write_text(json.dumps({"ano": ano, "estudios": estudios}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(estudios)} grados en {SALIDA}", file=sys.stderr)


if __name__ == "__main__":
    main()
