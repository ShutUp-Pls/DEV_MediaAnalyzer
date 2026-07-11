# Limpiar DataSets multimedía

Al extraer datasets desde RRSS a tráves de scraping, el resultado suelen ser miles de imagenes y videos con contenido repetido. Por **sanidad del dataset**, es conveniente seleccionar solo aquellas piezas de contenido que más valor aporten a tráves de caracteristicas como:

- **Calidad**: Define el detalle de lo visualizado.
    <br>*(Resolución, Nitidez, Ruido, etc...)*
- **Peso de archivo**: Define la eficiencia del formato.
    <br>*(Tamaño en MB vs Calidad)*
- **Artefactos gráficos**: Extras que no son parte del contenido original.
    <br> *(Marcas de agua, bandas negras, texto, etc...)*

Además, en el caso de videos:

- **Duración o Completitud**:
    <br> Hasta que punto un video es un clip, subvideo, la continuación o precuela de otro video.

Estas caracteristicas pueden ser facilmente identificables por un humano, sin embargo, no para sistemas computacionales.

## Limitación de herramientas actuales

Actualmente hay muchas piezas de software que buscan contenido multimedia repetido en datasets. Aún así, estás son insuficientes para la problematica anterior, ya que se limitan a hacer una comparación binaria incapaz de extraer conceptos semanticos para clasificar este contenido como un humano y tomar decisiones de limpieza y calidad.

## Propuesta de proyecto

Para solucionar lo anterior, se propone la construcción de un sistema que mezcle:

1. Inteligencia Artifical
2. Visión por computadora
3. Análisis metrico
4. Análisis semantico

Con el fin de obtener las siguientes capacidades:

- **Agrupación semántica de contenido (Clustering):** 
    <br>Identificar y agrupar medios que representan la misma escena o contenido subyacente, ignorando variaciones superficiales como recortes, filtros de color, espejado o cambios de formato.
- **Evaluación algorítmica de fidelidad visual:** 
    <br>Medir objetivamente atributos como la nitidez, exposición y compresión para detectar la calidad real de un archivo, diferenciando un archivo nativo en alta definición de uno reescalado artificialmente.
- **Detección y penalización de artefactos:** 
    <br>Reconocer elementos no deseados superpuestos a la imagen original (marcas de agua, logotipos, texto estático, bandas negras horizontales/verticales) para priorizar las versiones "limpias".
- **Análisis topológico temporal en video:** 
    <br>Comparar fotogramas clave (keyframes) y marcas de tiempo para mapear si un clip corto es un fragmento exacto extraído de un video más largo, priorizando conservar la versión completa o concatenando partes si es necesario.
- **Puntuación y selección automatizada (Scoring):** 
    <br>Asignar una calificación global a cada archivo dentro de un grupo semántico, cruzando el peso del archivo con su calidad, pureza y completitud, para conservar automáticamente el "mejor representante" y eliminar la redundancia.
- **Preservación de información diferencial (Salvaguarda):** 
    <br>Garantizar que al perfilar el "mejor representante", el sistema ejecute un análisis comparativo para no destruir datos únicos presentes en archivos secundarios. Si una versión de menor puntuación contiene un encuadre más amplio (uncropped) o una escena extra, el sistema retiene, recorta o fusiona esa información exclusiva antes de la purga final.