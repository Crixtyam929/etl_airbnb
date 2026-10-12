"""Corre el proceso completo: extracción, transformación y carga.

Antes hay que haber corrido cargar_mongodb.py al menos una vez.
"""

import logging

from carga import Carga
from extraccion import Extraccion
from logs import configurar_logs
from transformacion import Transformacion

logger = logging.getLogger("ejecutar_etl")


def ejecutar():
    archivo_log = configurar_logs()
    logger.info("Inicio del proceso ETL")
    datos = Extraccion().extraer()
    tablas = Transformacion(datos).transformar()
    Carga().cargar(tablas)
    logger.info("Proceso ETL terminado sin errores. Log en %s", archivo_log.name)


if __name__ == "__main__":
    try:
        ejecutar()
    except Exception:
        logger.exception("El proceso ETL se detuvo por un error")
        raise SystemExit(1)
