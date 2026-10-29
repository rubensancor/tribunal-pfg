#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf>=1.24"]
# ///
"""Utilidades del tribunal PFG.

  uv run scripts/pfg.py trocear <id>        memoria.pdf -> secciones/indice.json + NN.txt
  uv run scripts/pfg.py validar <id>        comprueba los JSON que escriben los agentes
  uv run scripts/pfg.py imagen <id> <pdf>   paginas/pNNN.png (figuras con datos) y pNNN.json (palabras, para el lector)
  uv run scripts/pfg.py paginas <id>        paginas/indice.json: tamaño y numeración impresa de cada página
"""
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PFGS = RAIZ / "pfgs"
CATEGORIAS = RAIZ / "config" / "categorias.json"
TROZO = 12     # páginas por trozo cuando no hay marcador o una sección es demasiado larga
DIVIDIR = 30   # un capítulo más largo se divide por sus subapartados
MAX_PAGS = 40  # ninguna sección supera esto
MIN_PAGS = 6   # una sección más corta se junta con su vecina: menos lectores para lo mismo
DPI = 200

TENSIONES = {"sin_justificar", "sin_evidencia", "incoherencia", "validacion_debil",
             "limite_no_explorado", "cambio_de_nivel"}
ANALISIS = ["titulo", "estudiante", "titulacion", "director", "paginas", "desfase_paginas",
            "que_hace", "aportacion_propia", "decisiones", "resultados", "fortalezas",
            "debilidades", "leer_al_menos", "coherencia", "notas_tribunal"]
PREGUNTA = ["id", "prioridad", "pregunta", "anclaje", "por_que_importa", "buena_respuesta",
            "senal_alarma", "repregunta"]


def dir_pfg(pfg_id):
    if not re.fullmatch(r"[a-z0-9-]+", pfg_id):
        sys.exit(f"id no válido: {pfg_id}")
    d = PFGS / pfg_id
    if not (d / "memoria.pdf").exists():
        sys.exit(f"no existe {d / 'memoria.pdf'}")
    return d


def rangos(entradas, fin):
    """[(titulo, ini)] -> [(titulo, ini, fin)]; fusiona las que empiezan en la misma página."""
    fus = []
    for t, p in sorted(entradas, key=lambda e: e[1]):
        if fus and fus[-1][1] == p:
            fus[-1] = (f"{fus[-1][0]} / {t}", p)
        else:
            fus.append((t, p))
    return [(t, p, fus[i + 1][1] - 1 if i + 1 < len(fus) else fin) for i, (t, p) in enumerate(fus)]


def secciones(toc, n):
    """Secciones (titulo, ini, fin) con páginas 0-based inclusivas que cubren todo el PDF."""
    toc = [(lvl, t.strip() or "Sin título", p - 1) for lvl, t, p, *_ in toc if 1 <= p <= n]
    if not toc:
        return [(f"Páginas {i + 1}–{min(i + TROZO, n)}", i, min(i + TROZO, n) - 1)
                for i in range(0, n, TROZO)]
    top = min(lvl for lvl, _, _ in toc)
    base = [(t, p) for lvl, t, p in toc if lvl == top]
    if min(p for _, p in base) > 0:
        base.append(("Preliminares", 0))
    out = []
    for t, ini, fin in rangos(base, n - 1):
        hijos = [(f"{t} › {ht}", hp) for lvl, ht, hp in toc if lvl == top + 1 and ini < hp <= fin]
        out += rangos([(t, ini)] + hijos, fin) if fin - ini + 1 > DIVIDIR and hijos else [(t, ini, fin)]
    final = []
    for t, ini, fin in out:
        if fin - ini + 1 <= MAX_PAGS:
            final.append((t, ini, fin))
        else:
            final += [(f"{t} (parte {k})", s, min(s + TROZO - 1, fin))
                      for k, s in enumerate(range(ini, fin + 1, TROZO), 1)]
    juntas = []
    for t, ini, fin in final:
        corta = juntas and min(juntas[-1][2] - juntas[-1][1], fin - ini) + 1 < MIN_PAGS
        if corta and fin - juntas[-1][1] + 1 <= TROZO:
            juntas[-1] = (f"{juntas[-1][0]} / {t}", juntas[-1][1], fin)
        else:
            juntas.append((t, ini, fin))
    return juntas


def marca(page):
    etiqueta = page.get_label()
    return f"[[pdf:{page.number + 1} pág:{etiqueta}]]" if etiqueta else f"[[pdf:{page.number + 1}]]"


def trocear(pfg_id):
    import pymupdf
    d = dir_pfg(pfg_id)
    sd = d / "secciones"
    if (sd / "indice.json").exists():
        sys.exit(f"{pfg_id} ya está troceado; borra {sd} para rehacerlo")
    sd.mkdir(exist_ok=True)
    doc = pymupdf.open(d / "memoria.pdf")
    indice = []
    for n, (titulo, ini, fin) in enumerate(secciones(doc.get_toc(), doc.page_count)):
        partes, sin_texto = [], []
        for i in range(ini, fin + 1):
            texto = doc[i].get_text().strip()
            if len(texto) < 200 and doc[i].get_images():
                sin_texto.append(i + 1)
            partes.append(f"{marca(doc[i])}\n{texto}")
        archivo = f"{n:02d}.txt"
        (sd / archivo).write_text(f"# {titulo}\n\n" + "\n\n".join(partes) + "\n", encoding="utf-8")
        indice.append({"n": n, "titulo": titulo, "pdf_ini": ini + 1, "pdf_fin": fin + 1,
                       "archivo": archivo, "paginas_sin_texto": sin_texto})
    (sd / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(indice)} secciones en {sd}")


def _cargar(ruta, problemas, nombre=None):
    nombre = nombre or ruta.name
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problemas.append(f"{nombre}: falta")
    except json.JSONDecodeError as e:
        problemas.append(f"{nombre}: JSON no válido ({e})")


def _faltan(obj, claves, donde, problemas):
    if not isinstance(obj, dict):
        problemas.append(f"{donde}: se esperaba un objeto")
        return True
    falta = [c for c in claves if c not in obj]
    if falta:
        problemas.append(f"{donde}: faltan {', '.join(falta)}")
    return bool(falta)


def _anclados(lista, donde, problemas, claves=("texto", "pdf")):
    if not isinstance(lista, list):
        problemas.append(f"{donde}: se esperaba una lista")
        return
    for i, e in enumerate(lista):
        if not _faltan(e, claves, f"{donde}[{i}]", problemas) and not isinstance(e["pdf"], int):
            problemas.append(f"{donde}[{i}].pdf: debe ser un entero (página del PDF)")


def validar(d):
    """Lista de problemas en los JSON de un PFG; vacía si todo está bien. Solo valida lo que existe."""
    problemas = []
    sd = d / "secciones"
    indice = _cargar(sd / "indice.json", problemas) if (sd / "indice.json").exists() else []
    for s in indice or []:
        nombre = f"secciones/{s['n']:02d}.json"
        sec = _cargar(sd / f"{s['n']:02d}.json", problemas, nombre)
        if sec is None or _faltan(sec, ["resumen", "puntos_clave", "decisiones", "resultados",
                                       "tensiones", "no_legible"], nombre, problemas):
            continue
        for campo in ("puntos_clave", "decisiones", "resultados", "tensiones"):
            _anclados(sec[campo], f"{nombre}.{campo}", problemas)
        _anclados(sec["no_legible"], f"{nombre}.no_legible", problemas, ("pdf", "motivo"))
        for i, t in enumerate(sec["tensiones"] if isinstance(sec["tensiones"], list) else []):
            if isinstance(t, dict) and t.get("tipo") not in TENSIONES:
                problemas.append(f"{nombre}.tensiones[{i}].tipo: debe ser uno de {sorted(TENSIONES)}")

    if (d / "analisis.json").exists():
        a = _cargar(d / "analisis.json", problemas)
        if a is not None and not _faltan(a, ANALISIS, "analisis.json", problemas):
            for campo in ("decisiones", "resultados", "fortalezas", "debilidades"):
                _anclados(a[campo], f"analisis.json.{campo}", problemas)

    ids = set()
    if (d / "preguntas.json").exists():
        preguntas = _cargar(d / "preguntas.json", problemas)
        if preguntas is not None and not isinstance(preguntas, list):
            problemas.append("preguntas.json: se esperaba una lista")
        for i, p in enumerate(preguntas if isinstance(preguntas, list) else []):
            donde = f"preguntas.json[{i}]"
            if _faltan(p, PREGUNTA, donde, problemas):
                continue
            if p["id"] in ids:
                problemas.append(f"{donde}: id repetido {p['id']}")
            ids.add(p["id"])
            if "categoria" in p:  # la generación es ciega a las categorías
                problemas.append(f"{donde}: no debe llevar categoría (eso va en clasificacion.json)")
            if not _faltan(p["anclaje"], ["pdf", "pag", "seccion", "cita"], f"{donde}.anclaje", problemas) \
                    and not isinstance(p["anclaje"]["pdf"], int):
                problemas.append(f"{donde}.anclaje.pdf: debe ser un entero (página del PDF)")

    if (d / "clasificacion.json").exists():
        c = _cargar(d / "clasificacion.json", problemas)
        validas = {cat["id"] for cat in json.loads(CATEGORIAS.read_text(encoding="utf-8"))} | {"otra"}
        if isinstance(c, dict):
            if set(c) != ids:
                problemas.append(f"clasificacion.json: ids distintos a preguntas.json "
                                 f"(sobran {sorted(set(c) - ids)}, faltan {sorted(ids - set(c))})")
            for pid, v in c.items():
                if not _faltan(v, ["categoria", "motivo"], f"clasificacion.json.{pid}", problemas) \
                        and v["categoria"] not in validas:
                    problemas.append(f"clasificacion.json.{pid}: categoría desconocida {v['categoria']!r}")
        elif c is not None:
            problemas.append("clasificacion.json: se esperaba un objeto {id: {categoria, motivo}}")

    # No se cruza con anotaciones.json: el docente puede borrar una nota mientras el agente responde.
    if (d / "respuestas.json").exists():
        r = _cargar(d / "respuestas.json", problemas)
        if isinstance(r, dict):
            for aid, v in r.items():
                donde = f"respuestas.json.{aid}"
                if _faltan(v, ["nota", "respuesta"], donde, problemas):
                    continue
                if not isinstance(v["nota"], str):
                    problemas.append(f"{donde}.nota: debe ser el texto de la nota respondida")
                _anclados(v["respuesta"], f"{donde}.respuesta", problemas)
        elif r is not None:
            problemas.append("respuestas.json: se esperaba un objeto {id: {nota, respuesta}}")
    return problemas


def escribir(ruta, datos):
    """El dashboard puede pedir la misma página dos veces a la vez: nunca debe leer un archivo a medias."""
    ruta.parent.mkdir(exist_ok=True)
    tmp = ruta.with_name(f".{ruta.name}.{os.getpid()}")
    tmp.write_bytes(datos)
    os.replace(tmp, ruta)


def paginas(pfg_id):
    import pymupdf
    d = dir_pfg(pfg_id)
    doc = pymupdf.open(d / "memoria.pdf")
    indice = [{"w": round(p.rect.width, 2), "h": round(p.rect.height, 2), "pag": p.get_label() or None} for p in doc]
    escribir(d / "paginas" / "indice.json", json.dumps(indice, ensure_ascii=False).encode())
    print(d / "paginas" / "indice.json")


def imagen(pfg_id, pdf):
    import pymupdf
    d = dir_pfg(pfg_id)
    doc = pymupdf.open(d / "memoria.pdf")
    if not 1 <= pdf <= doc.page_count:
        sys.exit(f"la página {pdf} no existe (el PDF tiene {doc.page_count})")
    page = doc[pdf - 1]
    w, h = page.rect.width, page.rect.height
    # Mismo orden que get_text() y NN.txt, pero con las ligaduras («ﬁ») separadas. NFKC también las separa,
    # pero cambiaría «n.º» por «n.o» y «m²» por «m2».
    flags = pymupdf.TEXTFLAGS_WORDS & ~pymupdf.TEXT_PRESERVE_LIGATURES
    palabras = [[round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4), t]
                for x0, y0, x1, y1, t, *_ in page.get_text("words", flags=flags)]
    out = d / "paginas" / f"p{pdf:03d}.png"
    escribir(out.with_suffix(".json"), json.dumps({"palabras": palabras}, ensure_ascii=False).encode())
    escribir(out, page.get_pixmap(dpi=DPI).tobytes("png"))
    print(out)


def main(args):
    if len(args) >= 2 and args[0] == "trocear":
        trocear(args[1])
    elif len(args) >= 2 and args[0] == "validar":
        problemas = validar(dir_pfg(args[1]))
        print("\n".join(problemas) or "ok")
        sys.exit(1 if problemas else 0)
    elif len(args) >= 3 and args[0] == "imagen" and args[2].isdigit():
        imagen(args[1], int(args[2]))
    elif len(args) >= 2 and args[0] == "paginas":
        paginas(args[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
