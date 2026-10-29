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

    respuesta = {"nota": "¿Frente a qué?", "respuesta": [{"texto": "Frente a 100 usuarios.", "pdf": 12, "pag": "10"}]}
    (d / "respuestas.json").write_text(json.dumps({"k3f9a2c1": respuesta}))
    assert pfg.validar(d) == [], pfg.validar(d)
    (d / "respuestas.json").write_text(json.dumps({"k3f9a2c1": {**respuesta, "respuesta": [{"texto": "sin página"}]}}))
    assert any("respuestas.json.k3f9a2c1.respuesta[0]: faltan pdf" in p for p in pfg.validar(d))
    (d / "respuestas.json").write_text(json.dumps([respuesta]))
    assert any("respuestas.json: se esperaba un objeto" in p for p in pfg.validar(d))
    (d / "respuestas.json").unlink()

    # Sin etiquetas de página la marca solo lleva el número del PDF.
    pdf(Path(tmp) / "plano" / "memoria.pdf", 3)
    pfg.trocear("plano")
    assert "[[pdf:2]]" in (Path(tmp) / "plano" / "secciones" / "00.txt").read_text()

    # Lo que lee el lector del dashboard: tamaño y etiqueta de cada página, y las palabras en el orden de NN.txt.
    pfg.paginas("demo")
    paginas = json.loads((d / "paginas" / "indice.json").read_text())
    assert len(paginas) == 60 and paginas[0] == {"w": 595.0, "h": 842.0, "pag": "i"} and paginas[2]["pag"] == "1"
    pfg.paginas("plano")
    assert json.loads((Path(tmp) / "plano" / "paginas" / "indice.json").read_text())[0]["pag"] is None
    doc = pymupdf.open(d / "memoria.pdf")
    doc[11].insert_font(fontname="F0", fontbuffer=pymupdf.Font("cjk").buffer)  # Helvetica no tiene la ligadura «ﬁ»
    doc[11].insert_text((72, 300), "La eﬁciencia n.º 3 en m²", fontname="F0")
    doc.saveIncr()
    pfg.imagen("demo", 12)
    palabras = json.loads((d / "paginas" / "p012.json").read_text())["palabras"]
    assert [w[4] for w in palabras] == "Contenido de la página 12 La eficiencia n.º 3 en m²".split(), palabras
    assert " ".join(w[4] for w in palabras[:5]) in (d / "secciones" / "01.txt").read_text()  # la sección 01 empieza en el pdf 10
    x0, y0, x1, y1, _ = palabras[0]
    assert 0 < x0 < x1 < 1 and 0 < y0 < y1 < 1 and abs(x0 - 72 / 595) < .01, palabras[0]
    assert (d / "paginas" / "p012.png").read_bytes().startswith(b"\x89PNG")
    assert pymupdf.Pixmap(d / "paginas" / "p012.png").width == round(595 * pfg.DPI / 72)
    assert not [f for f in (d / "paginas").iterdir() if f.name.startswith(".")], "sin temporales"

print("ok")
