#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf>=1.24"]
# ///
"""Self-check de scripts/pfg.py con PDFs sintéticos. Uso: uv run tests/test_pfg.py"""
import contextlib
import io
import json
import sys
import tempfile
import time
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

    # Programas de un grado: lo que escribiría el dashboard en grados/<gid>/.
    pfg.RAIZ, pfg.GRADOS = Path(tmp), Path(tmp) / "grados"

    def cli(*args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                pfg.main(list(args))
                codigo = 0
            except SystemExit as e:
                codigo = e.code
        return codigo, out.getvalue()

    assert cli("grados") == (0, "[]\n")
    g = pfg.GRADOS / "grado-en-informatica"
    (g / "programas").mkdir(parents=True)
    (g / "grado.json").write_text(json.dumps({"nombre": "Grado en Informática", "fuentes": {}}))
    assert json.loads(cli("grados")[1]) == [{"id": "grado-en-informatica", "nombre": "Grado en Informática"}]
    # Como las guías de Deusto: ISO-8859-15, la versión inglesa delante y el bloque de contenidos repetido.
    bloque = ("<div>Titulación:</div><div>14402 - Grado en Informática</div><div>Curso académico:</div><div>2026/27</div>"
              "<div>Asignatura:</div><div>145320 - Arquitectura</div><div>Curso:</div><div>2024 - Grado en Informática: 3</div>"
              "<div>Tipo:</div><div>Obligatoria</div><div>Créditos ECTS:</div><div>6.0</div><div>Justificación</div><p>Profesorado y competencias</p>"
              "<div>Contenidos</div><p>TEMA 1: Rendimiento (Amdahl)</p><p>TEMA 2: Jerarquía de memoria</p>"
              "<div>Estrategia de enseñanza-aprendizaje, sistema de evaluación y documentación</div><p>Examen final €</p>")
    html = f"<html><head><style>p {{}}</style><script>var x;</script></head><body><div>Study:</div><div>Teaching/learning strategy</div>{bloque}{bloque}</body></html>"
    (g / "programas" / "145320.html").write_bytes(html.encode("iso-8859-15"))
    (g / "programas" / "redes.txt").write_text("Redes\nTema 1. TCP/IP\n")
    guia = pymupdf.open()
    guia.new_page().insert_text((72, 72), "Sistemas operativos")
    guia.new_page().insert_text((72, 72), "Tema 1. Procesos")
    guia.save(g / "programas" / "so.pdf")
    codigo, salida = cli("programas", "grado-en-informatica")
    assert codigo == 2 and salida.splitlines()[1:] == [f"grados/grado-en-informatica/textos/{s}.txt grados/grado-en-informatica/asignaturas/{s}.json"
                                                       for s in ("145320", "redes", "so")], salida
    texto = (g / "textos" / "145320.txt").read_text()
    assert texto.splitlines() == ["Asignatura:", "145320 - Arquitectura", "Titulación:", "14402 - Grado en Informática",
                                  "Curso:", "2024 - Grado en Informática: 3", "Tipo:", "Obligatoria", "Contenidos",
                                  "TEMA 1: Rendimiento (Amdahl)", "TEMA 2: Jerarquía de memoria"], texto
    assert "[[pdf:2]]\nTema 1. Procesos" in (g / "textos" / "so.txt").read_text() and (g / "textos" / "redes.txt").read_text() == "Redes\nTema 1. TCP/IP\n"
    assert pfg.texto_html("<p>Sin marcadores</p><p>Tema único</p>".encode()) == "Sin marcadores\nTema único\n", "sin marcadores, todo"

    ficha = {"asignatura": "Arquitectura", "codigo": "145320", "curso": 3, "caracter": "obligatoria",
             "temas": [{"id": "TEMA 1", "texto": "Rendimiento"}, {"id": "TEMA 2", "texto": "Jerarquía de memoria"}]}
    (g / "asignaturas").mkdir()
    (g / "asignaturas" / "145320.json").write_text(json.dumps(ficha))
    (g / "asignaturas" / "redes.json").write_text(json.dumps({**ficha, "codigo": "", "curso": None, "temas": []}))
    (g / "asignaturas" / "so.json").write_text(json.dumps({**ficha, "caracter": "troncal", "curso": "3"}))
    codigo, salida = cli("programas", "grado-en-informatica")
    assert (codigo, salida) == (0, "ninguno\n"), "repetirlo no cambia nada"
    codigo, salida = cli("validar-grado", "grado-en-informatica")
    assert codigo == 1 and "asignaturas/so.json.caracter" in salida and "asignaturas/so.json.curso" in salida, salida
    assert "aviso: asignaturas/redes.json: la guía no tiene contenidos" in salida
    (g / "asignaturas" / "so.json").write_text(json.dumps(ficha))
    assert cli("validar-grado", "grado-en-informatica")[0] == 0, "un aviso no es un error"
    assert json.loads(cli("catalogo", "grado-en-informatica")[1])["145320"] == ficha

    time.sleep(0.01)
    (g / "programas" / "redes.txt").write_text("Redes II\n")
    assert cli("programas", "grado-en-informatica")[1].splitlines()[1:] == [
        "grados/grado-en-informatica/textos/redes.txt grados/grado-en-informatica/asignaturas/redes.json"], "un programa cambiado vuelve a leerse"
    assert (g / "textos" / "redes.txt").read_text() == "Redes II\n"

    # El contraste de un PFG con su grado.
    def contraste(**c):
        (d / "contraste.json").write_text(json.dumps({"grado": "grado-en-informatica", "motivo": "", "aplica": [], "extiende": [], **c}))
        return pfg.validar(d)

    assert "contraste.json: falta grado.json, que dice con qué grado se contrasta" in contraste()
    (d / "grado.json").write_text(json.dumps({"grado": "grado-inventado", "titulacion": "Grado en Informática", "pdf": "1"}))
    problemas = contraste()
    assert any("no existe el grado 'grado-inventado'" in p for p in problemas) and any("grado.json.pdf" in p for p in problemas)
    (d / "grado.json").write_text(json.dumps({"grado": "grado-en-informatica", "titulacion": "Grado en Informática", "pdf": 1, "pag": "i"}))
    aplica = {"texto": "Mide la latencia con caché.", "pdf": 12, "pag": "10", "temas": [{"asignatura": "145320", "tema": "TEMA 2"}]}
    extiende = {"texto": "Usa CRDT.", "pdf": 20, "pag": "18", "temas": [], "mas_alla": "No aparece en los programas cargados."}
    assert contraste(aplica=[aplica], extiende=[extiende]) == []
    assert any("aplica[0].temas: lo que aplica" in p for p in contraste(aplica=[{**aplica, "temas": []}]))
    assert any("no tiene el tema 'TEMA 9'" in p for p in contraste(aplica=[{**aplica, "temas": [{"asignatura": "145320", "tema": "TEMA 9"}]}]))
    assert any("no está en asignaturas/" in p for p in contraste(extiende=[{**extiende, "temas": [{"asignatura": "fisica", "tema": "TEMA 1"}]}]))
    assert any("extiende[0].mas_alla" in p for p in contraste(extiende=[{**extiende, "mas_alla": ""}]))
    assert any("aplica[0].pdf: debe ser un entero" in p for p in contraste(aplica=[{**aplica, "pdf": "12"}]))
    assert any("no coincide con grado.json" in p for p in contraste(grado=None))
    (d / "grado.json").write_text(json.dumps({"grado": None, "titulacion": "Grado en ADE + Grado en Informática", "pdf": 1}))
    assert contraste(grado=None, motivo="Es un doble grado y no hay ninguno cargado.") == []
    assert any("aplica: sin grado debe ir vacía" in p for p in contraste(grado=None, aplica=[aplica]))

print("ok")
