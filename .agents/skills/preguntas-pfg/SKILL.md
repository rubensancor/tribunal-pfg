---
name: preguntas-pfg
description: Genera las preguntas para la defensa de un PFG/TFG/TFM ya leído en el dashboard del tribunal (pfgs/<id>/analisis.json). Primero escribe las preguntas sin conocer las categorías y después las clasifica con un subagente aparte. Úsala cuando pidan preguntas para una defensa o un tribunal, o cuando peguen «usa la skill preguntas-pfg con el PFG <id>».
---

# Preguntas para la defensa

Entrada: un id de `pfgs/`. Necesita `pfgs/<id>/analisis.json`; si no existe, ejecuta antes la skill `leer-pfg`.

- Si ya existe `preguntas.json` pero no `clasificacion.json`, salta al paso 2.
- Si existen los dos, pregunta antes de regenerar, porque se perderían.

El orden importa: **primero se escriben las preguntas y luego se clasifican**. Así las preguntas salen de dónde flojea el trabajo, no de una lista de temas por cubrir.

## Paso 1: generar (tú, modelo principal)

**En este paso no abras `config/categorias.json` ni ningún `clasificacion.json`, y no preguntes por categorías.** Otro agente las clasifica después.

Lee `analisis.json` y los `secciones/NN.json`. Abre tramos de `secciones/NN.txt` cuando necesites la cita exacta o comprobar algo.

Las buenas preguntas salen de las **tensiones** del trabajo: las que han marcado los lectores, las debilidades y la tabla de coherencia del análisis, y lo que veas con las lentes de `.agents/skills/leer-pfg/lentes.md`. Las lentes dicen dónde mirar, no qué cubrir: no hace falta una pregunta por lente.

**Dudas del tribunal.** Si existe `anotaciones.json`, lee las notas con `"tipo": "preguntas"`: son dudas que el docente ha anotado al leer la memoria, con su `cita`, su `pdf` y su `pag`. Compruébalas en el texto. Las que sigan en pie son candidatas a pregunta, ancladas a su página: no las copies, reescríbelas para que pasen los filtros. Ignora las notas de otros tipos y no abras `notas-personales.json`, que es privado.

**Contraste con el grado.** Si existe `contraste.json`, lo que va en `extiende` es buen anclaje para preguntas de Dominio y Mecanismo: el estudiante ha ido más allá de lo que imparte el grado, y la defensa es el momento de que lo explique. No lo conviertas en sospecha.

**Cuántas**: las que el trabajo merezca, normalmente entre 8 y 15. No hay cupo por tema. Si el trabajo flojea sobre todo en un punto, que la mayoría de las preguntas vayan ahí.

**Cada pregunta tiene que pasar estos filtros.** Si no los pasa, reescríbela o descártala.

1. **Test de transplante**: si la misma pregunta sirve para otro PFG, es genérica. Descártala.
2. **Anclada**: cita la página, la sección y la afirmación concreta («En la pág. 34 dices que…»).
3. **Exige razonar, no recordar**: la respuesta no está copiada en la memoria. Pide justificar, comparar, predecir, estimar o explicar un mecanismo.
4. **Se responde en 2–3 minutos**, de pie y sin ordenador.
5. **Sin trampa ni humillación**: busca que el estudiante luzca lo que sabe y que se vea lo que no.

**Prohibidas**, salvo que estén ancladas y concretadas: «¿Qué has aprendido?», «¿Qué mejorarías?», «¿Por qué elegiste este tema?», «¿Cuáles son las líneas futuras?», «¿Qué dificultades encontraste?».

**Formas que suelen funcionar:**

- **Contrafactual**: «Si en lugar de X hubieras usado Y, ¿qué habría cambiado en [resultado concreto]?»
- **Predicción**: «Si la carga se multiplica por 10, ¿qué parte de tu sistema falla primero y por qué?»
- **Mecanismo**: «Explícanos con la figura 4.2 qué ocurre paso a paso cuando…»
- **Evidencia**: «Afirmas en la pág. 51 que es un 30 % más rápido. ¿Frente a qué, medido cómo y cuántas veces?»
- **Coherencia**: «El objetivo O3 (pág. 4) no aparece en la evaluación del cap. 6. ¿Se cumplió? ¿Cómo lo sabemos?»
- **Abogado del diablo**: «Una solución como Z ya hace esto. ¿Qué aporta tu trabajo?»
- **Dominio**: «En la ecuación (3.4), ¿qué pasa si α tiende a cero? ¿Tiene sentido físico?» Úsala cuando algo parezca ajeno al estudiante: no acuses, pide que lo explique.

Escribe `pfgs/<id>/preguntas.json`, ordenado por `prioridad`: la 1 es la que mejor distingue a quien domina el trabajo de quien no. No pongas campo de categoría.

```json
[
  {
    "id": "P1", "prioridad": 1,
    "pregunta": "",
    "anclaje": {"pdf": 0, "pag": "", "seccion": "", "cita": "cita o paráfrasis breve"},
    "por_que_importa": "qué evidencia aporta sobre el dominio del trabajo",
    "buena_respuesta": "qué ideas mencionaría alguien que lo domina",
    "senal_alarma": "qué respuesta indicaría que no lo domina",
    "repregunta": "si la respuesta es vaga o evasiva"
  }
]
```

Valida con `uv run scripts/pfg.py validar <id>`.

## Paso 2: clasificar (subagente barato, con contexto limpio)

Lanza el agente `clasificador-preguntas` por la misma vía que los lectores de `leer-pfg`: subagente si lo hay y, si no, CLI no interactivo. Encárgale:

> Clasifica `pfgs/<id>/preguntas.json` con `config/categorias.json` y escribe `pfgs/<id>/clasificacion.json`.

Después valida.

**Si no tienes subagentes**: clasifica tú siguiendo `.agents/agents/clasificador-preguntas.md`, como último paso. Desde ese momento **no generes más preguntas en esta sesión**, porque ya conoces las categorías. Para pedir más, abre una sesión nueva.

Termina con el número de preguntas y la de prioridad 1. No señales como carencia las categorías que se hayan quedado sin preguntas.

## Reglas

- La IA prepara y el tribunal juzga. No propongas nota y no afirmes que el estudiante ha usado IA.
- Escribe en el idioma de la memoria. No inventes datos externos: si comparas con una alternativa, que sea conocida y estándar en el área.
