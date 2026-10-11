"""Configuración de los logs: un archivo por ejecución en logs/log_YYYYMMDD_HHMM.txt."""

import logging
from datetime import datetime
from pathlib import Path

CARPETA_LOGS = Path(__file__).resolve().parent.parent / "logs"


def configurar_logs():
    """Escribe los mensajes en el archivo de la ejecución y en consola, con fecha, hora y nivel."""
    CARPETA_LOGS.mkdir(exist_ok=True)
    archivo = CARPETA_LOGS / f"log_{datetime.now():%Y%m%d_%H%M}.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(archivo, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )
    return archivo
