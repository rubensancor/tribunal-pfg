# Lentes por tipo de proyecto

Dónde suelen estar las tensiones interesantes en cada tipo de PFG de ingeniería. Aplica las que encajen; muchos proyectos mezclan varias.

## Desarrollo de software / aplicaciones
- Arquitectura: por qué ese estilo (monolito, microservicios, serverless) para ese tamaño de problema.
- Elección de stack justificada por requisitos o por costumbre.
- Requisitos no funcionales: rendimiento, seguridad, accesibilidad; ¿se midieron o solo se enuncian?
- Pruebas: cobertura real, pruebas con usuarios (¿cuántos, quiénes, sesgo de conocidos?).
- Persistencia: modelo de datos, migraciones, qué pasa con datos concurrentes.
- Despliegue y mantenimiento: quién lo mantiene mañana, coste de operación.

## Datos, IA y aprendizaje automático
- Datos: origen, tamaño, desbalanceo, licencia, datos personales.
- Fuga de datos entre entrenamiento y test; validación cruzada; semilla y repetibilidad.
- Línea base: ¿se compara con algo simple (regresión, reglas, modelo previo)?
- Métrica alineada con el objetivo de negocio o del problema (accuracy con clases desbalanceadas).
- Interpretabilidad, sesgos, coste de cómputo y huella energética.
- Si usa LLM o modelos preentrenados: qué parte es aportación propia.

## Electrónica, sistemas embebidos y telecomunicaciones
- Selección de componentes: alternativas, coste, disponibilidad, consumo.
- Márgenes de diseño, tolerancias, peor caso; ¿simulado o medido?
- Diferencias simulación ↔ prototipo y su explicación.
- Restricciones de tiempo real, latencia, ancho de banda, presupuesto de enlace.
- Normativa (CE, EMC, espectro radioeléctrico), seguridad eléctrica.
- Fabricación: ¿escala de 1 a 1000 unidades?

## Industrial, mecánica, energía y organización
- Hipótesis de cálculo y coeficientes de seguridad; origen de los datos de entrada.
- Sensibilidad: cuánto cambia el resultado si el dato más incierto varía un ±20 %.
- Validación de simulaciones (FEM, CFD) con malla, convergencia o ensayo.
- Viabilidad económica: VAN/TIR/payback, hipótesis de precios, escenarios.
- Normativa aplicable, seguridad, ciclo de vida, impacto ambiental.

## Gestión del proyecto (todas)
- Planificación frente a lo realizado: desviaciones y su causa.
- Presupuesto: horas del estudiante, licencias, hardware; ¿es realista?
- Riesgos identificados al inicio y si alguno se materializó.
- Sostenibilidad / ODS: ¿análisis concreto o párrafo de relleno?

## Proyectos en empresa
- Qué hizo el estudiante y qué ya estaba hecho o lo hizo el equipo.
- Confidencialidad: qué no puede contar y si eso deja sin evidencia algún resultado.
- Decisiones impuestas por la empresa frente a decisiones propias.
