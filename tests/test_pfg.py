#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf>=1.24"]
# ///
"""Self-check de scripts/pfg.py con PDFs sintéticos. Uso: uv run tests/test_pfg.py"""
import json
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pfg  # noqa: E402


def pdf(ruta, n, toc=None, etiquetas=None):
    doc = pymupdf.open()
    for i in range(n):
        doc.new_page().insert_text((72, 72), f"Contenido de la página {i + 1}")
    if toc:
        doc.set_toc(toc)
    if etiquetas:
        doc.set_page_labels(etiquetas)
    ruta.parent.mkdir(parents=True)
    doc.save(ruta)


# Capítulos, preliminares y un capítulo largo que se divide por sus subapartados.
toc = [[1, "Introducción", 3], [1, "Desarrollo", 10], [2, "Diseño", 20], [2, "Pruebas", 35],
       [1, "Conclusiones", 50]]
assert pfg.secciones(toc, 60) == [
    ("Preliminares / Introducción", 0, 8), ("Desarrollo", 9, 18),
    ("Desarrollo › Diseño", 19, 33), ("Desarrollo › Pruebas", 34, 48), ("Conclusiones", 49, 59)]
# Sin marcador: trozos fijos.
assert [s[1:] for s in pfg.secciones([], 30)] == [(0, 11), (12, 23), (24, 29)]
# Capítulo largo sin subapartados: se parte en trozos.
assert len(pfg.secciones([[1, "Único", 1]], 50)) == 5
# Dos entradas en la misma página se fusionan; las secciones cortas se juntan sin pasar de TROZO.
assert pfg.rangos([("Índice", 0), ("Figuras", 0), ("Cap. 1", 1)], 4) == [
    ("Índice / Figuras", 0, 0), ("Cap. 1", 1, 4)]
assert pfg.secciones([[1, "A", 1], [1, "B", 3], [1, "C", 5], [1, "D", 12], [1, "E", 30], [1, "F", 40]], 40) == [
    ("A / B / C", 0, 10), ("D", 11, 28), ("E / F", 29, 39)]

with tempfile.TemporaryDirectory() as tmp:
    pfg.PFGS = Path(tmp)
    d = Path(tmp) / "demo"
    pdf(d / "memoria.pdf", 60, toc, [{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
                                     {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1}])
    pfg.trocear("demo")
    indice = json.loads((d / "secciones" / "indice.json").read_text())
    assert indice[0]["titulo"] == "Preliminares / Introducción" and indice[1]["pdf_ini"] == 10
    texto = (d / "secciones" / "00.txt").read_text()
    assert texto.startswith("# Preliminares") and "[[pdf:1 pág:i]]" in texto and "[[pdf:3 pág:1]]" in texto

    assert "secciones/00.json: falta" in pfg.validar(d)
    for s in indice:
        (d / "secciones" / f"{s['n']:02d}.json").write_text(json.dumps(
            {"resumen": "x", "puntos_clave": [{"texto": "x", "pdf": s["pdf_ini"], "pag": None}],
             "decisiones": [], "resultados": [], "no_legible": [],
             "tensiones": [{"tipo": "sin_evidencia", "texto": "x", "pdf": s["pdf_ini"], "pag": None}]}))
    assert pfg.validar(d) == [], pfg.validar(d)

    pregunta = {"id": "P1", "prioridad": 1, "pregunta": "¿?", "por_que_importa": "", "buena_respuesta": "",
                "senal_alarma": "", "repregunta": "",
                "anclaje": {"pdf": 12, "pag": "10", "seccion": "Desarrollo", "cita": "…"}}
    (d / "preguntas.json").write_text(json.dumps([pregunta, {**pregunta, "id": "P2", "categoria": "x"}]))
    assert any("no debe llevar categoría" in p for p in pfg.validar(d))
    (d / "preguntas.json").write_text(json.dumps([pregunta]))
    (d / "clasificacion.json").write_text(json.dumps({"P1": {"categoria": "inventada", "motivo": ""}}))
    assert any("categoría desconocida" in p for p in pfg.validar(d))
    (d / "clasificacion.json").write_text(json.dumps({"P1": {"categoria": "validacion", "motivo": ""}}))
    assert pfg.validar(d) == [], pfg.validar(d)

    # Sin etiquetas de página la marca solo lleva el número del PDF.
    pdf(Path(tmp) / "plano" / "memoria.pdf", 3)
    pfg.trocear("plano")
    assert "[[pdf:2]]" in (Path(tmp) / "plano" / "secciones" / "00.txt").read_text()

print("ok")
