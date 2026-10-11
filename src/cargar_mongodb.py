"""Paso previo al ETL: se crea la base airbnb_bogota en MongoDB y se suben los archivos de Inside Airbnb.

Solo hay que correrlo una vez o cuando cambie algún dato
"""

import logging
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

from extraccion import BASE_DATOS, URI_MONGO
from logs import configurar_logs

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"
ARCHIVOS = {
    "listings": CARPETA_DATOS / "listings.csv.gz",
    "calendar": CARPETA_DATOS / "calendar.csv.gz",
    "reviews": CARPETA_DATOS / "reviews.csv.gz",
}

logger = logging.getLogger("cargar_mongodb")


def subir_archivo(bd, nombre, archivo):
    # Se borra la colección para no duplicar documentos si se corre otra vez
    bd.drop_collection(nombre)

    filas = 0
    # Se lee por bloques porque calendar tiene más de 7 millones de filas
    for bloque in pd.read_csv(archivo, chunksize=100_000):
        # Los valores vacíos se guardan como null y no como NaN
        documentos = bloque.astype(object).where(bloque.notna(), None).to_dict("records")
        bd[nombre].insert_many(documentos)
        filas += len(bloque)

    # Se valida que la colección quedó con las mismas filas del archivo
    en_mongo = bd[nombre].count_documents({})
    if en_mongo != filas:
        logger.error("'%s': el archivo tiene %d filas y en MongoDB quedaron %d", nombre, filas, en_mongo)
        raise ValueError(f"La colección '{nombre}' no quedó completa")
    logger.info("Colección '%s' cargada y validada: %d documentos", nombre, en_mongo)


def subir_todo():
    logger.info("Inicio de la carga de archivos a MongoDB")
    cliente = MongoClient(URI_MONGO, serverSelectionTimeoutMS=5000)
    try:
        cliente.admin.command("ping")
        bd = cliente[BASE_DATOS]
        for nombre, archivo in ARCHIVOS.items():
            subir_archivo(bd, nombre, archivo)
    finally:
        cliente.close()
    logger.info("Base de datos '%s' lista para el ETL", BASE_DATOS)


if __name__ == "__main__":
    configurar_logs()
    try:
        subir_todo()
    except Exception:
        logger.exception("La carga a MongoDB se detuvo por un error")
        raise SystemExit(1)
