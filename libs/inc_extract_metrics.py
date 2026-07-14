from pathlib import Path

from libs.utils.logging import Logger
from libs.utils.errores import ErrorBase

registrador = Logger.obtener_registrador(__name__)

class ErrorRutaDataset(ErrorBase):
    mensaje_defecto = "La ruta del dataset no está configurada correctamente en las variables de entorno."

class ErrorProcesarImagen(ErrorBase):
    mensaje_defecto = "Fallo crítico al calcular phash o registrar la imagen en la base de datos."

class ErrorProcesarVideo(ErrorBase):
    mensaje_defecto = "Fallo crítico al extraer y registrar los fotogramas del video en la base de datos."

class Eventos:
    @staticmethod
    def inicio_flujo(ruta: str):
        registrador.info(f"Iniciando flujo de extracción de métricas para el directorio: {ruta}")

    @staticmethod
    def fin_flujo():
        registrador.info("Flujo de extracción de métricas completado exitosamente.")

    @staticmethod
    def exito_imagen(nombre: str):
        registrador.info(f"Imagen procesada exitosamente: {nombre}")

    @staticmethod
    def exito_video(nombre: str, fotogramas: int):
        registrador.info(f"Video procesado exitosamente: {nombre} | Fotogramas extraidos: {fotogramas}")

    @staticmethod
    def advertencia_video_corrupto(nombre: str):
        registrador.warning(f"Omitiendo video corrupto o con 0 FPS: {nombre}")

    @staticmethod
    def advertencia_workers_excedido(solicitado: int, maximo: int):
        registrador.warning(
            f"Se solicitaron {solicitado} workers, pero el sistema solo soporta {maximo}. "
            f"Se limitará a {maximo}."
        )

    @staticmethod
    def inicio_paralelo(total: int, workers: int):
        registrador.info(f"Iniciando procesamiento paralelo de {total} archivos con {workers} workers.")

    @staticmethod
    def progreso_lote(procesados: int, total: int):
        registrador.info(f"Progreso: {procesados}/{total} archivos procesados.")

    @staticmethod
    def error_worker(mensaje: str):
        registrador.error(f"Error en worker: {mensaje}")

    @staticmethod
    def info_imagenes_insertadas(cantidad: int):
        registrador.info(f"Se insertaron {cantidad} registros de imágenes.")

    @staticmethod
    def info_videos_insertados(cantidad: int):
        registrador.info(f"Se insertaron {cantidad} registros de vídeos.")

    @staticmethod
    def sin_archivos():
        registrador.warning("No se encontraron archivos con extensiones válidas en el dataset.")

    @staticmethod
    def creacion_directorio_bd(directorio: Path):
        registrador.info(f"Directorio para base de datos creado: {directorio}")

    @staticmethod
    def inicio_procesamiento_archivo(nombre: str, pid: int):
        registrador.info(f"Worker PID {pid} procesando archivo: {nombre}")

    @staticmethod
    def archivo_no_reconocido(nombre: str):
        registrador.warning(f"Archivo ignorado (no es imagen ni video reconocible): {nombre}")
    
    @staticmethod
    def advertencia_batch_size_invalido(valor: int):
        registrador.warning(f"BATCH_SIZE inválido ({valor}), se usará 1000.")

class Consultas:
    CREAR_TABLA_IMAGENES = '''
        CREATE TABLE IF NOT EXISTS imagenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT UNIQUE,
            ruta_completa TEXT,
            phash TEXT
        )
    '''
    
    CREAR_TABLA_VIDEOS = '''
        CREATE TABLE IF NOT EXISTS videos_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT,
            ruta_completa TEXT,
            segundo_video INTEGER,
            phash TEXT
        )
    '''
    
    INSERTAR_IMAGEN = '''
        INSERT OR IGNORE INTO imagenes (nombre_archivo, ruta_completa, phash)
        VALUES (?, ?, ?)
    '''
    
    INSERTAR_VIDEO = '''
        INSERT INTO videos_frames (nombre_archivo, ruta_completa, segundo_video, phash)
        VALUES (?, ?, ?, ?)
    '''