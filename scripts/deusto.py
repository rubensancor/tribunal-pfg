#!/usr/bin/env python3
"""Rehace config/deusto.json con las asignaturas de cada grado de Deusto, de la consulta pública de guías docentes (gaude).

Uso: uv run scripts/deusto.py [año]   (el año académico que empieza, p. ej. 2026 para 2026/2027; por defecto, el actual)
Pide de una en una y con pausa: no saturar el servidor de la universidad.
"""
import datetime
import json
import re
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


def simple(nombre):
    return re.sub(r"\s*\(\d{4}\)$", "", nombre)  # «Grado en Filosofía, Política y Economía (2018)»: el año del plan sobra


def completar_dobles(estudios):
    """gaude da a cada doble grado solo parte de sus asignaturas: le suma las de cada «Grado en …» que lo forma,
    las del mismo campus (primera cifra del código) si existe ahí y si no las del otro. Devuelve los que no encuentra."""
    simples = {}
    for c, e in sorted(estudios.items()):
        if " + " not in e["nombre"]:
            simples.setdefault(simple(e["nombre"]), []).append(c)
    faltan = []
    for c, e in estudios.items():
        if " + " not in e["nombre"]:
            continue
        for parte in e["nombre"].split(" + "):
            if not parte.startswith("Grado"):
                continue  # «+ Programa en …», «+ Diploma …»: no es un grado
            cs = simples.get(simple(parte))
            if not cs:
                faltan.append(f"{c} {parte}")
                continue
            origen = next((x for x in cs if x[0] == c[0]), cs[0])
            e["asignaturas"] = dict(sorted((estudios[origen]["asignaturas"] | e["asignaturas"]).items()))
    return faltan


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
    for falta in completar_dobles(estudios):
        print(f"doble grado sin su grado simple en el catálogo: {falta}", file=sys.stderr)
    SALIDA.write_text(json.dumps({"ano": ano, "estudios": estudios}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(estudios)} grados en {SALIDA}", file=sys.stderr)


if __name__ == "__main__":
    main()
