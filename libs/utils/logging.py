import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from datetime import datetime

from libs import RUTA_RAIZ_PROYECTO
from libs.utils import LOG_MAX_ARCHIVOS, LOG_MAX_PESO_MB


class Logger:
    _ruta_log_dir = "logs"
    _codificacion = 'utf-8'

    _manejador_archivo = None
    _manejador_consola = None
    _timestamp = None
    _nombre_base = None

    @staticmethod
    def obtener_registrador(nombre_modulo: str) -> logging.Logger:
        registrador = logging.getLogger(nombre_modulo)

        if not registrador.handlers:
            registrador.setLevel(logging.INFO)
            Logger._inicializar_manejadores_si_necesario()
            registrador.addHandler(Logger._manejador_archivo)
            registrador.addHandler(Logger._manejador_consola)
            registrador.propagate = False

        return registrador

    @staticmethod
    def _inicializar_manejadores_si_necesario():
        if Logger._manejador_archivo is None:
            Logger._timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            Logger._nombre_base = f"log_{Logger._timestamp}.txt"

            ruta_directorio = Logger._obtener_ruta_directorio()
            ruta_directorio.mkdir(parents=True, exist_ok=True)
            ruta_archivo = ruta_directorio / Logger._nombre_base

            limite_bytes = int(LOG_MAX_PESO_MB * 1024 * 1024)

            Logger._manejador_archivo = RotatingFileHandler(
                filename=ruta_archivo,
                maxBytes=limite_bytes,
                backupCount=100,
                encoding=Logger._codificacion
            )
            Logger._manejador_archivo.setLevel(logging.INFO)

            Logger._manejador_consola = logging.StreamHandler(sys.stdout)
            Logger._manejador_consola.setLevel(logging.INFO)

            formato = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
            Logger._manejador_archivo.setFormatter(formato)
            Logger._manejador_consola.setFormatter(formato)

            Logger._limpiar_logs_viejos(ruta_directorio)

    @staticmethod
    def _limpiar_logs_viejos(directorio: Path):
        archivos = sorted(
            directorio.glob("log_*.txt*"),
            key=lambda p: p.stat().st_mtime 
        )

        if not archivos: return

        archivo_actual = directorio / Logger._nombre_base

        while len(archivos) > LOG_MAX_ARCHIVOS:
            viejo = archivos.pop(0)
            if viejo == archivo_actual:
                continue
            viejo.unlink()

        archivos_restantes = list(directorio.glob("log_*.txt*"))
        archivos_restantes.sort(key=lambda p: p.stat().st_mtime)

        tamaño_total = sum(p.stat().st_size for p in archivos_restantes)
        limite_bytes = int(LOG_MAX_PESO_MB * 1024 * 1024)

        while tamaño_total > limite_bytes and archivos_restantes:
            viejo = archivos_restantes.pop(0)
            if viejo == archivo_actual:
                continue
            tamaño_total -= viejo.stat().st_size
            viejo.unlink()

    @staticmethod
    def _obtener_ruta_directorio() -> Path:
        return RUTA_RAIZ_PROYECTO / Logger._ruta_log_dir