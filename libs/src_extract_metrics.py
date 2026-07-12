import os
import cv2
import imagehash
from PIL import Image
from pathlib import Path

from libs import (
    RUTA_DATASET,
    DB_IMAGENES_NOMBRE,
    DB_VIDEOS_NOMBRE,
    RUTA_RAIZ_PROYECTO
)

from libs.utils.gsqlite import gSQLite
from libs.inc_extract_metrics import (
    LogExtractor, 
    ConsultasSQLExtractor, 
    ErrorRutaDataset, 
    ErrorProcesarImagen, 
    ErrorProcesarVideo
)

class ExtractorMetricasMultimedia:
    EXTENSIONES_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    EXTENSIONES_VIDEO = {'.mp4', '.avi', '.mkv', '.mov'}

    def __init__(self):
        self.ruta_dataset = RUTA_DATASET
        self._db_imagenes = DB_IMAGENES_NOMBRE
        self._db_videos = DB_VIDEOS_NOMBRE
        self._validar_entorno()
        
        self.db_imagenes:gSQLite = gSQLite(RUTA_RAIZ_PROYECTO / self._db_imagenes)
        self.db_videos:gSQLite = gSQLite(RUTA_RAIZ_PROYECTO / self._db_videos)
        
        self._inicializar_tablas()

    def _inicializar_tablas(self):
        self.db_imagenes.ejecutar_escritura(ConsultasSQLExtractor.CREAR_TABLA_IMAGENES)
        self.db_videos.ejecutar_escritura(ConsultasSQLExtractor.CREAR_TABLA_VIDEOS)

    def _validar_entorno(self):
        if not self.ruta_dataset.name or not self.ruta_dataset.exists():
            LogExtractor.error_entorno()
            raise ErrorRutaDataset()

    def ejecutar_flujo(self):
        LogExtractor.inicio_flujo(self.ruta_dataset)
        self._recorrer_y_procesar_dataset()
        LogExtractor.fin_flujo()

    def _recorrer_y_procesar_dataset(self):
        for directorio_raiz, _, archivos in os.walk(self.ruta_dataset):
            directorio_actual = Path(directorio_raiz)
            self._procesar_archivos_directorio(directorio_actual, archivos)

    def _procesar_archivos_directorio(self, directorio: Path, archivos: list):
        for nombre_archivo in archivos:
            ruta_archivo = directorio / nombre_archivo
            self._enrutar_archivo_por_extension(ruta_archivo, nombre_archivo)

    def _enrutar_archivo_por_extension(self, ruta_archivo: Path, nombre_archivo: str):
        extension = ruta_archivo.suffix.lower()
        if extension in self.EXTENSIONES_IMAGEN:
            self._procesar_imagen(ruta_archivo, nombre_archivo)
        elif extension in self.EXTENSIONES_VIDEO:
            self._procesar_video(ruta_archivo, nombre_archivo)

    def _procesar_imagen(self, ruta_archivo: Path, nombre_archivo: str):
        try:
            valor_hash = self._calcular_phash_imagen(ruta_archivo)
            self.db_imagenes.ejecutar_escritura(
                ConsultasSQLExtractor.INSERTAR_IMAGEN, 
                (nombre_archivo, str(ruta_archivo), valor_hash)
            )
            LogExtractor.exito_imagen(nombre_archivo)
        except Exception as error:
            LogExtractor.error_imagen(nombre_archivo, error)
            raise ErrorProcesarImagen(error_original=error)

    def _calcular_phash_imagen(self, ruta_archivo: Path) -> str:
        imagen = Image.open(ruta_archivo)
        return str(imagehash.phash(imagen))

    def _procesar_video(self, ruta_archivo: Path, nombre_archivo: str):
        try:
            fotogramas_extraidos = self._extraer_y_hashear_fotogramas_video(ruta_archivo, nombre_archivo)
            LogExtractor.exito_video(nombre_archivo, fotogramas_extraidos)
        except Exception as error:
            LogExtractor.error_video(nombre_archivo, error)
            raise ErrorProcesarVideo(error_original=error)

    def _extraer_y_hashear_fotogramas_video(self, ruta_archivo: Path, nombre_archivo: str) -> int:
        captura_video = cv2.VideoCapture(str(ruta_archivo))
        fotogramas_por_segundo = round(captura_video.get(cv2.CAP_PROP_FPS))
        
        if fotogramas_por_segundo <= 0:
            LogExtractor.advertencia_video_corrupto(nombre_archivo)
            return 0

        total_fotogramas_guardados = self._iterar_y_guardar_fotogramas(
            captura_video, fotogramas_por_segundo, ruta_archivo, nombre_archivo
        )
        captura_video.release()
        
        return total_fotogramas_guardados

    def _iterar_y_guardar_fotogramas(
        self, captura_video: cv2.VideoCapture, fotogramas_por_segundo: int, 
        ruta_archivo: Path, nombre_archivo: str
    ) -> int:
        indice_fotograma = 0
        segundo_actual = 0
        
        while captura_video.isOpened():
            exito, fotograma = captura_video.read()
            if not exito:
                break
                
            if indice_fotograma % fotogramas_por_segundo == 0:
                valor_hash = self._calcular_phash_fotograma(fotograma)
                self.db_videos.ejecutar_escritura(
                    ConsultasSQLExtractor.INSERTAR_VIDEO, 
                    (nombre_archivo, str(ruta_archivo), segundo_actual, valor_hash)
                )
                segundo_actual += 1

            indice_fotograma += 1
                
        return segundo_actual

    def _calcular_phash_fotograma(self, fotograma) -> str:
        fotograma_rgb = cv2.cvtColor(fotograma, cv2.COLOR_BGR2RGB)
        imagen_pil = Image.fromarray(fotograma_rgb)
        return str(imagehash.phash(imagen_pil))

if __name__ == "__main__":
    extractor = ExtractorMetricasMultimedia()
    extractor.ejecutar_flujo()