"""Extracción: nos traemos las colecciones de MongoDB a DataFrames de pandas."""

import logging
from itertools import islice

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError

URI_MONGO = "mongodb://localhost:27017/"
BASE_DATOS = "airbnb_bogota"
COLECCIONES = ["listings", "calendar", "reviews"]

logger = logging.getLogger("extraccion")


class Extraccion:
    """Se conecta a la base airbnb_bogota de MongoDB y lee las colecciones listings, calendar y reviews."""

    def __init__(self, uri=URI_MONGO, base_datos=BASE_DATOS):
        self.uri = uri
        self.base_datos = base_datos
        self.cliente = None
        self.bd = None

    def conectar(self):
        """Abre la conexión y confirma con un ping que el servidor responde."""
        try:
            self.cliente = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.cliente.admin.command("ping")
        except PyMongoError as error:
            logger.error("No se pudo conectar a MongoDB en %s: %s", self.uri, error)
            raise
        self.bd = self.cliente[self.base_datos]
        logger.info("Conexión exitosa a MongoDB (%s), base de datos '%s'", self.uri, self.base_datos)

    def leer_coleccion(self, nombre):
        """Lee una colección completa y la devuelve como DataFrame."""
        # Se lee por bloques de 500 mil documentos para no llenar la memoria,
        # calendar tiene más de 7 millones
        cursor = self.bd[nombre].find({}, {"_id": 0})
        partes = []
        while True:
            bloque = list(islice(cursor, 500_000))
            if not bloque:
                break
            partes.append(pd.DataFrame(bloque))

        if not partes:
            logger.error("La colección '%s' está vacía, primero hay que correr cargar_mongodb.py", nombre)
            raise ValueError(f"Colección vacía: {nombre}")

        df = pd.concat(partes, ignore_index=True)
        logger.info("Se leyeron %d registros y %d columnas de '%s'", len(df), df.shape[1], nombre)
        return df

    def cerrar(self):
        """Cierra la conexión."""
        if self.cliente is not None:
            self.cliente.close()
            logger.info("Conexión a MongoDB cerrada")

    def extraer(self):
        """Lee las tres colecciones y devuelve un diccionario {colección: DataFrame}."""
        logger.info("Inicio de la extracción")
        self.conectar()
        try:
            return {nombre: self.leer_coleccion(nombre) for nombre in COLECCIONES}
        finally:
            self.cerrar()
