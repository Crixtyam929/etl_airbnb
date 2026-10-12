"""limpieza de los datos, aplanado de las comodidades y variables de fecha.
"""

import json
import logging

import pandas as pd

logger = logging.getLogger("transformacion")

# Por encima de este precio por noche (en pesos) se toma como error de captura
PRECIO_MAXIMO = 5_000_000

TIPOS_ALOJAMIENTO = {
    "Entire home/apt": "Alojamiento entero",
    "Private room": "Habitación privada",
    "Shared room": "Habitación compartida",
    "Hotel room": "Habitación de hotel",
}

# Las localidades vienen sin tilde (menos Antonio Nariño), se dejan con su nombre oficial
LOCALIDADES = {
    "Candelaria": "La Candelaria",
    "Ciudad Bolivar": "Ciudad Bolívar",
    "Engativa": "Engativá",
    "Fontibon": "Fontibón",
    "Los Martires": "Los Mártires",
    "San Cristobal": "San Cristóbal",
    "Usaquen": "Usaquén",
}

# Comodidades que se pasan a columnas de sí o no en la tabla de anuncios
COMODIDADES_CLAVE = {
    "tiene_wifi": r"wifi",
    "tiene_cocina": r"kitchen",
    "tiene_parqueadero": r"parking",
    "tiene_lavadora": r"\bwasher",
    "tiene_espacio_trabajo": r"workspace",
}

# Columnas de listings que se usan y su nombre en español
COLUMNAS_ANUNCIOS = {
    "id": "id",
    "host_id": "id_anfitrion",
    "name": "nombre",
    "neighbourhood_cleansed": "localidad",
    "room_type": "tipo_alojamiento",
    "accommodates": "capacidad",
    "bedrooms": "habitaciones",
    "beds": "camas",
    "bathrooms": "banos",
    "precio": "precio",
    "categoria_precio": "categoria_precio",
    "minimum_nights": "noches_minimas",
    "availability_365": "dias_disponibles",
    "number_of_reviews": "num_resenas",
    "review_scores_rating": "calificacion",
}


class Transformacion:
    """Recibe los DataFrames de la extracción y genera las tablas limpias para la carga."""

    def __init__(self, datos):
        self.listings = datos["listings"]
        self.calendar = datos["calendar"]
        self.reviews = datos["reviews"]

    @staticmethod
    def registrar(tabla, paso, antes, despues):
        """Deja en el log las filas antes y después de un paso; si se descartaron filas es advertencia."""
        if antes == despues:
            logger.info("%s | %s: %d filas, no se descartó ninguna", tabla, paso, antes)
        else:
            logger.warning("%s | %s: %d -> %d filas (%d descartadas)", tabla, paso, antes, despues, antes - despues)

    @staticmethod
    def limpiar_texto(serie):
        """Quita etiquetas HTML como <br/> y espacios de más; el texto vacío queda nulo."""
        texto = serie.str.replace(r"<[^>]+>", " ", regex=True)
        texto = texto.str.replace(r"\s+", " ", regex=True).str.strip()
        return texto.mask(texto == "")

    @staticmethod
    def normalizar_texto(serie):
        """Minúsculas, sin tildes ni caracteres especiales y sin espacios de más."""
        texto = serie.str.lower().str.normalize("NFKD")
        texto = texto.str.encode("ascii", errors="ignore").str.decode("ascii")
        return texto.str.replace(r"\s+", " ", regex=True).str.strip()

    @staticmethod
    def convertir_fechas(df, tabla):
        """Pasa date a fecha AAAA-MM-DD y deriva año, mes, día y trimestre; las fechas inválidas se descartan."""
        fechas = pd.to_datetime(df["date"], errors="coerce")
        Transformacion.registrar(tabla, "fechas inválidas", len(df), int(fechas.notna().sum()))
        df = df[fechas.notna()]
        fechas = fechas[fechas.notna()]
        return df.assign(
            fecha=fechas.dt.strftime("%Y-%m-%d"),
            anio=fechas.dt.year,
            mes=fechas.dt.month,
            dia=fechas.dt.day,
            trimestre=fechas.dt.quarter,
        )

    def aplanar_comodidades(self):
        """Pasa la lista de amenities de cada anuncio a una tabla con una fila por anuncio y comodidad."""
        listas = self.listings.drop_duplicates(subset="id").set_index("id")["amenities"].map(json.loads)
        tabla = listas.explode().dropna().reset_index()
        tabla.columns = ["id_anuncio", "comodidad"]
        logger.info("Comodidades | lista aplanada: %d anuncios -> %d filas", len(listas), len(tabla))

        # Se normaliza el texto y se quita la velocidad del internet
        # ("Fast wifi - 228 Mbps" queda como "fast wifi") para juntar variantes
        distintas_antes = tabla["comodidad"].nunique()
        comodidad = self.normalizar_texto(tabla["comodidad"].astype(str))
        tabla["comodidad"] = comodidad.str.replace(r"\s*\d+ mbps$", "", regex=True)
        logger.info(
            "Comodidades | normalización de texto: %d -> %d comodidades distintas",
            distintas_antes, tabla["comodidad"].nunique(),
        )

        antes = len(tabla)
        tabla = tabla.drop_duplicates().reset_index(drop=True)
        self.registrar("Comodidades", "repetidas después de normalizar", antes, len(tabla))
        return tabla

    def limpiar_anuncios(self, comodidades):
        """Limpia listings: duplicados, precio, nulos, textos y columnas en español."""
        antes = len(self.listings)
        df = self.listings.drop_duplicates(subset="id")
        self.registrar("Anuncios", "duplicados por id", antes, len(df))

        # Precio: de texto ("$284,294.01") a número; los precios imposibles quedan nulos
        df["precio"] = pd.to_numeric(df["price"].str.replace(r"[$,]", "", regex=True), errors="coerce")
        errores = df["precio"] > PRECIO_MAXIMO
        df["precio"] = df["precio"].mask(errores)
        logger.info("Anuncios | precio convertido de texto a número")
        logger.warning("Anuncios | %d precios mayores a %d por noche se dejan nulos", errores.sum(), PRECIO_MAXIMO)
        logger.warning("Anuncios | %d anuncios quedan sin precio", df["precio"].isna().sum())

        df["categoria_precio"] = pd.cut(
            df["precio"],
            bins=[0, 100_000, 250_000, 500_000, float("inf")],
            labels=["Económico", "Medio", "Alto", "Lujo"],
            right=False,
        ).astype("string").fillna("Sin precio")
        logger.info("Anuncios | categorías de precio: %s", df["categoria_precio"].value_counts().to_dict())

        # Habitaciones: en un cuarto (privado, compartido o de hotel) se asume 1;
        # en los demás se usa la mediana de los anuncios con la misma capacidad
        nulos_habitaciones = df["bedrooms"].isna().sum()
        es_cuarto = df["room_type"] != "Entire home/apt"
        df.loc[es_cuarto & df["bedrooms"].isna(), "bedrooms"] = 1
        mediana = df.groupby("accommodates")["bedrooms"].transform("median").round()
        df["bedrooms"] = df["bedrooms"].fillna(mediana)

        # Camas: mediana de los anuncios con la misma capacidad
        nulos_camas = df["beds"].isna().sum()
        mediana = df.groupby("accommodates")["beds"].transform("median").round()
        df["beds"] = df["beds"].fillna(mediana)

        # Baños: se sacan del texto ("1.5 shared baths"); "half-bath" es medio baño
        nulos_banos = df["bathrooms"].isna().sum()
        texto_banos = df["bathrooms_text"].str.lower().str.replace("half-bath", "0.5")
        df["bathrooms"] = df["bathrooms"].fillna(pd.to_numeric(texto_banos.str.extract(r"([\d.]+)")[0]))
        df["bathrooms"] = df["bathrooms"].fillna(df["bathrooms"].median())

        # Noches mínimas: son pocos nulos, se completan con la mediana
        nulos_noches = df["minimum_nights"].isna().sum()
        df["minimum_nights"] = df["minimum_nights"].fillna(df["minimum_nights"].median())
        logger.info(
            "Anuncios | nulos completados: %d habitaciones, %d camas, %d baños, %d noches mínimas",
            nulos_habitaciones, nulos_camas, nulos_banos, nulos_noches,
        )

        # Textos y categorías en español
        df["room_type"] = df["room_type"].map(TIPOS_ALOJAMIENTO)
        df["neighbourhood_cleansed"] = df["neighbourhood_cleansed"].replace(LOCALIDADES)
        df["name"] = self.limpiar_texto(df["name"])
        logger.info("Anuncios | tipo de alojamiento traducido y localidades con nombre oficial")

        # Se filtran las columnas que se usan y se renombran
        df = df[list(COLUMNAS_ANUNCIOS)].rename(columns=COLUMNAS_ANUNCIOS)
        for columna in ["habitaciones", "camas", "noches_minimas"]:
            df[columna] = df[columna].astype(int)

        # Resumen de comodidades por anuncio
        df["num_comodidades"] = df["id"].map(comodidades.groupby("id_anuncio").size()).fillna(0).astype(int)
        for columna, patron in COMODIDADES_CLAVE.items():
            ids = comodidades.loc[comodidades["comodidad"].str.contains(patron), "id_anuncio"]
            df[columna] = df["id"].isin(ids)

        logger.info("Anuncios | quedan %d columnas de %d", df.shape[1], self.listings.shape[1])
        return df.reset_index(drop=True)

    def limpiar_calendario(self, ids_anuncios):
        """Limpia calendar: duplicados, anuncios inexistentes, fechas y disponibilidad t/f."""
        antes = len(self.calendar)
        df = self.calendar.drop_duplicates(subset=["listing_id", "date"])
        self.registrar("Calendario", "duplicados por anuncio y fecha", antes, len(df))

        antes = len(df)
        df = df[df["listing_id"].isin(ids_anuncios)]
        self.registrar("Calendario", "anuncios que no existen", antes, len(df))

        antes = len(df)
        df = df[df["available"].isin(["t", "f"])]
        self.registrar("Calendario", "disponibilidad distinta de t/f", antes, len(df))

        df = self.convertir_fechas(df, "Calendario")
        calendario = pd.DataFrame({
            "id_anuncio": df["listing_id"],
            "fecha": df["fecha"],
            "anio": df["anio"],
            "mes": df["mes"],
            "dia": df["dia"],
            "trimestre": df["trimestre"],
            "disponible": df["available"] == "t",
        }).reset_index(drop=True)
        logger.info("Calendario | fechas en AAAA-MM-DD con año, mes, día y trimestre")
        return calendario

    @staticmethod
    def resumir_calendario_por_mes(calendario):
        """Resume el calendario diario por anuncio y mes (el diario no cabe en Excel)."""
        mensual = calendario.groupby(["id_anuncio", "anio", "mes"], as_index=False).agg(
            dias=("disponible", "size"),
            dias_disponibles=("disponible", "sum"),
        )
        mensual["porcentaje_disponible"] = (mensual["dias_disponibles"] / mensual["dias"] * 100).round(1)
        logger.info("Calendario mensual | %d filas diarias -> %d filas por anuncio y mes", len(calendario), len(mensual))
        return mensual

    def limpiar_resenas(self, ids_anuncios):
        """Limpia reviews: duplicados, anuncios inexistentes, comentarios vacíos, HTML y fechas."""
        antes = len(self.reviews)
        df = self.reviews.drop_duplicates(subset="id")
        self.registrar("Reseñas", "duplicados por id", antes, len(df))

        antes = len(df)
        df = df[df["listing_id"].isin(ids_anuncios)]
        self.registrar("Reseñas", "anuncios que no existen", antes, len(df))

        # Se limpia el comentario y se descartan las reseñas sin texto
        antes = len(df)
        df = df.assign(comentario=self.limpiar_texto(df["comments"])).dropna(subset=["comentario"])
        self.registrar("Reseñas", "sin comentario", antes, len(df))

        df = self.convertir_fechas(df, "Reseñas")

        # No se guardan el nombre ni el id de quien escribe: son datos personales que no se usan
        df = df[["id", "listing_id", "fecha", "anio", "mes", "dia", "trimestre", "comentario"]]
        return df.rename(columns={"listing_id": "id_anuncio"}).reset_index(drop=True)

    def transformar(self):
        """Ejecuta todas las transformaciones y devuelve las tablas listas para la carga."""
        logger.info("Inicio de la transformación")
        comodidades = self.aplanar_comodidades()
        anuncios = self.limpiar_anuncios(comodidades)
        calendario = self.limpiar_calendario(anuncios["id"])

        tablas = {
            "anuncios": anuncios,
            "anuncio_comodidades": comodidades,
            "calendario": calendario,
            "calendario_mensual": self.resumir_calendario_por_mes(calendario),
            "resenas": self.limpiar_resenas(anuncios["id"]),
        }
        for nombre, df in tablas.items():
            logger.info("Tabla '%s' lista: %d filas y %d columnas", nombre, len(df), df.shape[1])
        return tablas
