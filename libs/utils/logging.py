import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

from libs import RUTA_RAIZ_PROYECTO
from libs.utils import LOG_MAX_ARCHIVOS, LOG_MAX_PESO_MB

class Logger:
    _ruta_log = "logs"
    _nombre_log = "log.txt"
    _codificacion = 'utf-8'

    _manejador_archivo = None
    _manejador_consola = None

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
            ruta_directorio = Logger._obtener_ruta_directorio()
            ruta_directorio.mkdir(parents=True, exist_ok=True)
            ruta_archivo = ruta_directorio / Logger._nombre_log
            
            limite_bytes = int(LOG_MAX_PESO_MB * 1024 * 1024)
            respaldos_permitidos = max(0, LOG_MAX_ARCHIVOS - 1)
            
            Logger._manejador_archivo = RotatingFileHandler(
                filename=ruta_archivo,
                maxBytes=limite_bytes, 
                backupCount=respaldos_permitidos,
                encoding=Logger._codificacion
            )
            Logger._manejador_archivo.setLevel(logging.INFO)
            
            Logger._manejador_consola = logging.StreamHandler(sys.stdout)
            Logger._manejador_consola.setLevel(logging.INFO)
            
            formato = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
            Logger._manejador_archivo.setFormatter(formato)
            Logger._manejador_consola.setFormatter(formato)

    @staticmethod
    def _obtener_ruta_directorio() -> Path:
        return RUTA_RAIZ_PROYECTO / Logger._ruta_log