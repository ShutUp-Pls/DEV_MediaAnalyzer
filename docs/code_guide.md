# Guía de Estilo y Patrones de Código

Este documento define los estándares de escritura de código, arquitectura y buenas prácticas del proyecto. Debe ser utilizado como referencia obligatoria al momento de leer, refactorizar o generar nuevo código para este repositorio.

## 1. Idioma
*   **Español**
*   *Flexibilidades:* El español se puede omitir en.
    * *Nombre de Librerías*
    * *Palabras Reservadas Python*
    * *Nombres de Archivos*

## 2. Convenciones de Nomenclatura
*   **Clases y Excepciones:**
    <br> `PascalCase`
*   **Variables, argumentos y funciones/métodos:**
    <br> `snake_case`
*   **Constantes globales:**
    <br> `UPPER_SNAKE_CASE`
*   **Ámbito Privado/Protegido:**
    <br> `Python Name Mangling`

## 3. Tipado Estático
*   Uso obligatorio de *Type Hints* en la definición de argumentos y en sus retornos.

## 4. Diseño y Estructura
*   **CleanCode:** Respetaremos 3 principios de CleanCode:

    1. **Atomicidad**: Las funciones y métodos han de ser pequeños. Hacer solo una cosa y hacerla bien.
    2. **Autodescriptivas**: El nombre de la función revela su intención por completo. Si se requiere nombre muy largo o comentarios, puede ser indicio de que está haciendo mucho y debe dividirse.
    3. **Sin comentarios**: A tráves de 1. y 2. la documentación del codigo debiese ser despresiable.

## 5. Manejo de Rutas y Archivos
*   **Uso de Pathlib:** Es obligatorio utilizar `pathlib.Path` para cualquier construcción, manipulación o comprobación de rutas de directorios o archivos.

## 6. Manejo de Errores y Excepciones
*   **Excepciones Personalizadas:** Cada módulo principal debe definir una clase de Excepción base de la cual heredarán las excepciones específicas.

## 7. Abstracción de Logs (Registros)
*   **Cero `print()`:** Queda terminantemente prohibido usar la función `print` en el código. Todo mensaje de estado, error o información debe ir a través del `Logger` del sistema.
*   **Clases de Abstracción de Eventos:** La llamada a las funciones de logging no debe hacerse directamente dentro del bloque lógico interrumpiendo su lectura. En su lugar, todos los posibles eventos de log deben agruparse en una clase estática dedicada.

## 8. Persistencia de Datos y Consultas SQL
*   **Consultas centralizadas:** Toda consulta o sentencia SQL debe almacenarse como un string multilínea constante dentro de una clase agrupador dedicadas. Las clases lógicas solo llaman a esas constantes.
*   **Consultas parametrizadas:** Todo ingreso de datos se debe ejecutar pasando parámetros y empleando placeholders (`?`), nunca mediante literales ni "f-strings" directos al SQL.
*   **Context Managers:** Toda apertura de base de datos o archivo debe envolverse obligatoriamente dentro de un bloque `with` para asegurar el cierre automático y liberación de recursos.

## 9. Estructura del Proyecto y Arquitectura Modular

Los archivos deben organizarse respetando la siguiente estructura de separación de responsabilidades:

### Directorio `libs/`
Todo el código de negocio reside aquí. Para cada modulo, el código se divide en un par de archivos complementarios utilizando los prefijos `src_` e `inc_`:

*   **El patrón `inc_` (Include):**
    * **Clase de Excepciones del modulo**: (Punto 6.)
    * **Clase de Logs del modulo**: (Punto 7.)
    * **Clase de Consultas SQL**: (Punto 8.)

*   **El patrón `src_` (Source):** Es el orquestador principal. Contiene las clases y métodos puramente lógicos que dictan el flujo del negocio. Al aislar la lógica e importar las configuraciones desde su respectivo `inc_`, se garantiza la legibilidad continua de los algoritmos sin interrupciones visuales por literales de texto o queries SQL.

### Directorio `libs/utils/`
Contiene módulos transversales. Clases genéricas que no pertenecen a ninguna lógica de negocio en particular, pero que son utilizadas por múltiples componentes.

### Directorios Generales de Soporte
*   **`docs/`:** Almacena manuales, guías de estilo y descripciones arquitectónicas orientadas tanto a desarrolladores como a integraciones IA.
*   **`logs/`:** Directorio reservado estrictamente como destino para los archivos de salida generados en tiempo de ejecución por el sistema de registro (Logger). No debe contener código.

## 10. Gestión de Variables de Entorno y Configuración (`__init__.py`)

Los archivos `__init__.py` debe regirse por los siguientes principios:

*   **Delegación de Carga (`.env`):**
    <br> La instanciación y lectura física del archivo de entorno debe ocurrir exclusivamente en el `__init__.py` de mayor jerarquía o punto de entrada del árbol de ejecución.

*   **Consumo Descendente:**
    <br> Cualquier `__init__.py` anidado o de nivel inferior debe asumir que el contexto del sistema ya fue alimentado en la capa superior, usando `os.getenv()` para extraer sus variables específicas, sin intentar recargar el archivo de configuración base.

*   **Principio de Alcance Estricto (Scope):** 
    <br> Cada `__init__.py` es responsable de **únicamente** las variables de entorno que son pertinentes para el funcionamiento de los archivos internos de su directorio al mismo nivel jerarquico del `__init__.py` correspondiente.

*   **Abstracción de Entorno en la Lógica:**
    <br> Queda prohibido el uso de `os.getenv()` dentro del código fuente. Los archivos internos siempre deben importar sus configuraciones y credenciales desde el `__init__.py` de su nivel.