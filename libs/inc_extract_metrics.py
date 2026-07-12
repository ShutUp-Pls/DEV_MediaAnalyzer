from libs.utils.logging import Logger

registrador = Logger.obtener_registrador(__name__)

class ErrorExtraccionBase(Exception):
    mensaje_defecto = "Error desconocido en el proceso de extracción de métricas."
    
    def __init__(self, mensaje=None, error_original=None):
        self.mensaje = mensaje or self.mensaje_defecto
        if error_original:
            self.mensaje += f" | Detalle: {str(error_original)}"
        super().__init__(self.mensaje)

class ErrorRutaDataset(ErrorExtraccionBase):
    mensaje_defecto = "La ruta del dataset no está configurada correctamente en las variables de entorno."

class ErrorProcesarImagen(ErrorExtraccionBase):
    mensaje_defecto = "Fallo crítico al calcular phash o registrar la imagen en la base de datos."

class ErrorProcesarVideo(ErrorExtraccionBase):
    mensaje_defecto = "Fallo crítico al extraer y registrar los fotogramas del video en la base de datos."

class LogExtractor:
    @staticmethod
    def error_entorno():
        registrador.critical("Ruta de dataset invalida o faltante en las variables de entorno.")

    @staticmethod
    def inicio_flujo(ruta):
        registrador.info(f"Iniciando flujo de extracción de métricas para el directorio: {ruta}")

    @staticmethod
    def fin_flujo():
        registrador.info("Flujo de extracción de métricas completado exitosamente.")

    @staticmethod
    def exito_imagen(nombre):
        registrador.info(f"Imagen procesada exitosamente: {nombre}")

    @staticmethod
    def error_imagen(nombre, error):
        registrador.error(f"Fallo al procesar la imagen {nombre}: {str(error)}")

    @staticmethod
    def exito_video(nombre, fotogramas):
        registrador.info(f"Video procesado exitosamente: {nombre} | Fotogramas extraidos: {fotogramas}")

    @staticmethod
    def error_video(nombre, error):
        registrador.error(f"Fallo al procesar el video {nombre}: {str(error)}")

    @staticmethod
    def advertencia_video_corrupto(nombre):
        registrador.warning(f"Omitiendo video corrupto o con 0 FPS: {nombre}")

class ConsultasSQLExtractor:
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