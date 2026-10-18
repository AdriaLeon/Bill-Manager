# README

## Arrancar la aplicación

### 1. Primera ejecución

Crea un archivo `.env` en el directorio raíz del proyecto. Puedes utilizar `.env.example` como plantilla.

Para construir las imágenes de Docker e iniciar la aplicación ejecuta:

```bash
docker compose up --build
```

Este comando inicializa y arranca los siguientes componentes:

- Migraciones de la base de datos.
- Worker.
- Base de datos.
- Frontend.
- Backend.
- Tests.

### 2. Acceso a la aplicación

Frontend: http://localhost:5173

Backend (API): http://localhost:8000

Swagger UI: http://localhost:8000/docs

### 3. Ejecuciones posteriores

A partir de la segunda ejecución, puedes agilizar el arranque iniciando directamente los servicios necesarios:

```bash
docker compose up db backend worker frontend
```

## Tecnologías

El proyecto se ha desarrollado utilizando las siguientes tecnologías, teniendo en cuenta los requisitos establecidos y mi familiaridad con ellas:

- **Python:** FastAPI.
- **TypeScript:** React.
- **PostgreSQL:** base de datos relacional.
- **Docker:** contenedorización y ejecución de los servicios.
- **Alembic:** gestión y versionado de las migraciones de la base de datos.
- **Pytest:** ejecución de pruebas automatizadas.

## Arquitectura

El proyecto se ha dividido en cinco servicios principales: base de datos, migraciones, tests, frontend y backend.

Esta separación busca mantener los distintos componentes independientes, facilitando su desarrollo, ejecución y mantenimiento. Entre sus principales ventajas destacan:

- **Aislamiento:** permite ejecutar y probar componentes específicos sin necesidad de iniciar toda la aplicación.
- **Desarrollo independiente:** facilita modificar o reconstruir una parte del proyecto sin tener que reconstruir las demás. Por ejemplo, es posible reconstruir el frontend sin necesidad de reconstruir la API.
- **Facilidad de pruebas:** permite comprobar el comportamiento de componentes concretos de forma aislada.

### 1. Modelo de datos

Para modelar el ciclo de vida de los documentos, definí cinco estados posibles:

- **`PENDING`:** el documento está pendiente de ser reclamado por un worker.
- **`PROCESSING`:** un worker está procesando el documento.
- **`COMPLETED`:** la extracción de datos del documento ha finalizado correctamente.
- **`ERROR`:** el documento ha alcanzado un estado de error definitivo. Puede deberse a un error permanente, como un archivo vacío o la ausencia del atributo `total`, o a la acumulación de tres errores transitorios. Estos últimos pueden estar causados por fallos aleatorios (con una probabilidad del 20 %), por la ausencia de otros atributos o por valores escritos en un formato incorrecto o inesperado.
- **`REVIEWED`:** un usuario ha revisado y modificado los valores extraídos del documento.

Cuando falta alguno de los atributos esperados (menos el total) o alguno de sus valores presenta un formato incorrecto, el error se considera transitorio. En estos casos, se conservan los datos que se hayan podido extraer correctamente y se reintenta.

Añadí `REVIEWED` como estado para evitar incorporar un atributo adicional al modelo de datos y, al mismo tiempo, distinguir claramente los documentos cuyos valores han sido modificados por un usuario de aquellos procesados automáticamente.

Por último, cada entrada dispone de dos atributos adicionales relacionados con la gestión de las tareas:

- **`lease_token`:** identifica la reclamación de un documento por parte de un worker.
- **`lease_expires_at`:** indica cuándo expira la reclamación del documento.

Estos atributos permiten identificar los documentos que ya han sido reclamados y devolverlos a la cola de trabajos cuando una tarea queda bloqueada debido a un error del trabajador o del sistema.

Se utiliza **Alembic** para gestionar el versionado de las migraciones y mantener un registro de los cambios realizados en el esquema de la base de datos.

### 2. Extractor

El extractor está definido en `backend/app/services/extractor` como una clase que se proporciona a los trabajadores para procesar los documentos.

Por defecto, se utiliza un extractor basado en expresiones regulares (*regex*), encargado de extraer los valores esperados a partir del contenido de archivos `.txt`.

Alternativamente, es posible utilizar un extractor basado en un modelo de lenguaje (LLM). Para ello, es necesario configurar una clave de la API de Gemini en el archivo `.env` y establecer `USE_AI_EXTRACTOR` en `true`.

En este modo, los workers utilizan un extractor basado en Gemini, al que se le proporcionan instrucciones sobre la estructura de los datos esperados y cómo extraerlos del archivo `.txt`. Una vez obtenida la respuesta, se valida el formato de los valores extraídos antes de determinar si el documento puede marcarse como completado.

Ambos extractores utilizan el mismo sistema de excepciones:

- **`TransientExtractionError`:** representa errores recuperables, como fallos aleatorios, respuestas no válidas de Gemini o la ausencia de atributos distintos de `total`.
- **`PermanentExtractionError`:** representa errores definitivos, como un documento vacío o la ausencia del atributo `total`.

Por limitaciones de tiempo, no se han podido desarrollar las pruebas necesarias para comparar el rendimiento del extractor basado en IA con el basado en expresiones regulares.

En futuras iteraciones, si se decide utilizar el extractor basado en LLM de forma habitual, sería conveniente evaluar su precisión y consistencia mediante pruebas específicas. También sería interesante optimizar el número de llamadas a la API e implementar un mecanismo alternativo que permita continuar procesando documentos en caso de que el servicio de Google no esté disponible.

### 3. Worker

El Worker se inicializa en `backend/app/worker.py` y sigue la lógica definida en `backend/app/services/document_worker.py`.

Periódicamente, el trabajador comprueba si existen tareas cuya lease haya expirado. Para ello, revisa los documentos que se encuentran en estado `PROCESSING` y devuelve a `PENDING` aquellos cuya lease ha caducado.

A continuación, si hay documentos disponibles, reclama uno y comienza a procesarlo. Durante el procesamiento, renueva periódicamente la lease mediante un mecanismo de heartbeat, evitando que la tarea se considere abandonada mientras sigue activa.

La implementación actual utiliza un único trabajador simultáneamente. No obstante, el mecanismo de leases se ha diseñado teniendo en cuenta una posible ampliación futura que permita ejecutar varios trabajadores en paralelo y reclamar los trabajos de forma atómica, evitando que dos trabajadores procesen simultáneamente el mismo documento.

### 4. Backend (API)

Los endpoints de la API están definidos en `backend/app/api/documents.py`.

Entre las operaciones disponibles se encuentran:

- Buscar documentos, con filtros por estado y proveedor, y paginación.
- Subir archivos.
- Modificar los datos de un documento.
- Consultar los detalles de un documento específico.

Los principales códigos de error utilizados por los endpoints son:

- `400`: Formato de archivo no válido. Por ejemplo, cuando se intenta subir un archivo que no es `.txt`.
- `404`: Documento no encontrado.
- `409`:  Conflicto al intentar editar un documento que está pendiente de procesamiento o siendo procesado.
- `413`:  Archivo demasiado grande.

Como posibles ampliaciones, sería interesante añadir nuevos endpoints, como la eliminación de documentos, e implementar mecanismos de autenticación y autorización que permitan gestionar usuarios y roles.

### 5. Frontend (React)

La aplicación se ha diseñado en torno a dos páginas principales:

- **Página principal:** contiene los componentes de listado de documentos, subida de archivos y filtros.
- **Página de detalle:** permite consultar la información de un documento concreto y editar sus datos.

Aunque las instrucciones planteaban el uso de una aplicación de una sola página, opté por separar el listado y el detalle en dos vistas. Esta decisión permite presentar la información de cada documento con mayor claridad, aprovechar mejor el espacio disponible y facilitar la navegación y el acceso a los detalles.

La división de cada página en componentes independientes facilita su reutilización en futuras implementaciones y permite combinarlos de distintas formas sin duplicar lógica.

La actualización de los documentos se realiza mediante polling mientras haya documentos en estado `PENDING` o `PROCESSING`. La aplicación consulta periódicamente la API cada tres segundos para actualizar la información mostrada.

Aunque esta solución es sencilla de implementar, en una futura iteración podría sustituirse por un mecanismo basado en eventos, como WebSockets o SSE. Esto permitiría actualizar la interfaz cuando ocurran cambios relevantes, reduciendo las peticiones innecesarias a la API.

## Tests (Pytest)

Los tests se encuentran en el directorio `backend/tests` y pueden ejecutarse mediante Docker Compose:

```bash
docker compose up test
```

Estas pruebas tienen como objetivo evaluar el comportamiento del sistema ante distintos formatos de datos, comprobar la respuesta de los trabajadores en diferentes situaciones y verificar el ciclo de vida de los documentos.

Muchos de los tests utilizan archivos `.txt` de ejemplo diseñados para comprobar el comportamiento de la aplicación ante distintos escenarios, incluidos datos incompletos, formatos incorrectos y documentos que generan errores durante la extracción.

El desarrollo se ha centrado principalmente en las pruebas unitarias. En futuras iteraciones, sería conveniente incorporar pruebas de integración que permitan evaluar el comportamiento de la aplicación en su conjunto.

## Uso de la IA

Durante el desarrollo se han utilizado modelos de lenguaje (LLM) como herramientas de apoyo para agilizar la implementación del código y facilitar la depuración de errores.

Su uso ha tenido como objetivo mejorar la productividad durante el desarrollo y reducir el tiempo dedicado a tareas repetitivas.

## Tiempo dedicado

El desarrollo del proyecto ha requerido aproximadamente cinco horas de trabajo.

## Mejoras a futuro

Aunque la implementación actual cubre los principales requisitos del proyecto, existen varías mejoras que han quedado fuera del proyecto, que sin embargo, podrían aumentar su robustez, escalabilidad y funcionalidad:

- **Permitir la ejecución de varios workers en paralelo**: Si garantizamos la reclamación atómica de los documentos, podría mejor el rendimiento cuando haya varios archivos que procesar a la ves.

- **Mejorar la extracción de datos**: Decidí implementar el extractor basado en LLM's porque las posibilidades de detectar patrones de texto (como sinónimos o faltas de ortografía) me parece que amplian mucho las posibilidades del proceso de extracción. Sin embargo, verificar y controlar los resultados obtenidos del LLM requiere de muchos tests y verificaciones que salían del alcance de este proyecto, por lo que la implementación que he hecho no es necesariamente mejor que la basada en regex. En futuras iteraciones sería muy interesante explorar las posibilidades de un LLM en todo lo relacionado con el procesamiento de escritos (tanto en el extractor o nuevas funciones como un buscador de documentos).

- **Actualización en tiempo real**: Para el desarrollo de esta aplicación he utilizado un sistema de polling para refrescar la información. Sin embargo, un sistema basado en SSE o WebSockets reduciría las peticiones innecesarias (de cara a expandir el proyecto) y mejoraría la experiencia de usuario.

- **Ampliación de las pruebas**: Ampliar la cobertura de los tests mediante pruebas de integración y de concurrencia permitiría validar el comportamiento del sistema en escenarios más complejos y garantizar su fiabilidad a medida que aumente el número de usuarios.

- **Añadir verificación de usuarios**: Actualmente, cualquier usuario puede subir documentos y consultar los detalles de todos los documentos existentes. Incorporar un sistema de autenticación y autorización basado en usuarios y roles permitiría restringir el acceso a la información según los permisos de cada usuario, así como identificar quién realiza cada acción. Esto sería especialmente importante para garantizar la privacidad y la trazabilidad de las operaciones a medida que se incorpore información potencialmente sensible a la aplicación.