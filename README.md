# ETL Airbnb Bogotá

Taller ETL Airbnb de Inteligencia de Negocios.

Proceso ETL en Python con los datos de Airbnb de Bogotá publicados por Inside Airbnb. El objetivo es aplicar
extracción, transformación y carga sobre los datos guardados en una base MongoDB local: se extraen con pandas, se
limpian y transforman, y el resultado queda en una base de datos SQLite y en archivos XLSX. Todo el proceso deja
registro en logs.

El informe con el análisis, las transformaciones y su justificación está en [doc/informe_etl_airbnb.pdf](doc/informe_etl_airbnb.pdf).

Este README lo creamos con ayuda de la IA.


## Integrantes y responsabilidades

| Integrante | Responsabilidades |
|---|---|
| Cristian Andres Agudelo Henao | Base de datos en MongoDB y carga inicial (`cargar_mongodb.py`), extracción (`extraccion.py`), logs (`logs.py`) y carga a SQLite y XLSX (`carga.py`). |
| Jeronimo Patiño Betancur | Análisis exploratorio (`exploracion_airbnb.ipynb`), transformación (`transformacion.py`), README e informe. |


## Carpetas

- `datos`: archivos originales (.csv.gz). Al correr el ETL aquí quedan la base `airbnb_bogota.db` y la carpeta `xlsx`.
- `src`: scripts del proceso.
- `notebooks`: análisis exploratorio.
- `doc`: informe en PDF y en Word.
- `logs`: un archivo por cada ejecución (`log_YYYYMMDD_HHMM.txt`).

| Script | Qué hace |
|---|---|
| `cargar_mongodb.py` | Crea la base `airbnb_bogota` en MongoDB, sube las colecciones listings, calendar y reviews y valida los conteos. |
| `extraccion.py` | Clase `Extraccion`: se conecta a MongoDB y lleva cada colección a un DataFrame. |
| `transformacion.py` | Clase `Transformacion`: limpieza, precios, fechas, rangos de precio y aplanado de amenities. |
| `carga.py` | Clase `Carga`: inserta en SQLite, exporta a XLSX y verifica los conteos. |
| `logs.py` | Configura el archivo de log de cada ejecución. |
| `ejecutar_etl.py` | Corre extracción, transformación y carga en orden. |


## Requisitos

- Python 3.11 o superior.
- MongoDB corriendo en `localhost:27017`.


## Instalación y ejecución

Crear y activar el entorno virtual (en Windows):

```
python -m venv .venv
.venv\Scripts\activate
```

En Linux o Mac la activación es `source .venv/bin/activate`.

Instalar las dependencias:

```
pip install -r requirements.txt
```

Crear la base en MongoDB y subir los archivos (solo la primera vez, tarda un par de minutos):

```
python src/cargar_mongodb.py
```

Correr el proceso ETL (unos dos minutos):

```
python src/ejecutar_etl.py
```

Abrir el análisis exploratorio:

```
jupyter notebook notebooks/exploracion_airbnb.ipynb
```


## Ejemplo de ejecución

Salida de `python src/ejecutar_etl.py` (resumida):

```
2026-10-11 19:26:23 | INFO | ejecutar_etl | Inicio del proceso ETL
2026-10-11 19:26:23 | INFO | extraccion | Inicio de la extracción
2026-10-11 19:26:23 | INFO | extraccion | Conexión exitosa a MongoDB (mongodb://localhost:27017/), base de datos 'airbnb_bogota'
2026-10-11 19:26:24 | INFO | extraccion | Se leyeron 19187 registros y 90 columnas de 'listings'
2026-10-11 19:26:49 | INFO | extraccion | Se leyeron 7003255 registros y 5 columnas de 'calendar'
2026-10-11 19:26:54 | INFO | extraccion | Se leyeron 527731 registros y 6 columnas de 'reviews'
...
2026-10-11 19:26:57 | WARNING | transformacion | Anuncios | 38 precios mayores a 5000000 por noche se dejan nulos
2026-10-11 19:26:57 | WARNING | transformacion | Anuncios | 233 anuncios quedan sin precio
2026-10-11 19:27:04 | INFO | transformacion | Calendario mensual | 7003255 filas diarias -> 249431 filas por anuncio y mes
2026-10-11 19:27:08 | WARNING | transformacion | Reseñas | sin comentario: 527731 -> 527540 filas (191 descartadas)
...
2026-10-11 19:27:19 | INFO | carga | Tabla 'calendario' insertada en SQLite: 7003255 filas
2026-10-11 19:27:36 | WARNING | carga | La tabla 'calendario' tiene 7003255 filas y no cabe en Excel: queda solo en SQLite
2026-10-11 19:27:50 | INFO | carga | Tabla 'calendario_mensual' exportada a calendario_mensual.xlsx: 249431 filas
2026-10-11 19:28:36 | INFO | carga | Tabla 'resenas' exportada a resenas.xlsx: 527540 filas
...
2026-10-11 19:28:41 | INFO | carga | Carga terminada y verificada
2026-10-11 19:28:41 | INFO | ejecutar_etl | Proceso ETL terminado sin errores. Log en log_20261011_1926.txt
```

Al terminar quedan:

- `datos/airbnb_bogota.db` con las tablas `anuncios`, `anuncio_comodidades`, `calendario`, `calendario_mensual` y `resenas`.
- `datos/xlsx/` con un archivo por tabla, menos el calendario diario, que tiene 7 millones de filas y no cabe en Excel.
- El log de la ejecución en `logs/`.
