import concurrent.futures
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import cv2
import imagehash
from PIL import Image

from libs import (
    RUTA_DATASET,
    DB_IMAGES_PATH,
    DB_VIDEOS_PATH,
    FRAME_SKIP,
    BATCH_SIZE,
    PARALLEL_WORKERS,
)

from libs.utils.gsqlite import gSQLite
from libs.inc_extract_metrics import (
    Eventos,
    Consultas,
    ErrorRutaDataset
)

def _calcular_phash_imagen(ruta_archivo: Path) -> str:
    """Calcula el phash de una imagen usando PIL."""
    with Image.open(ruta_archivo) as imagen:
        return str(imagehash.phash(imagen))

def _calcular_phash_fotograma(fotograma) -> str:
    """Convierte un fotograma de OpenCV (BGR) a PIL y calcula su phash."""
    fotograma_rgb = cv2.cvtColor(fotograma, cv2.COLOR_BGR2RGB)
    imagen_pil = Image.fromarray(fotograma_rgb)
    return str(imagehash.phash(imagen_pil))

def _extraer_frames_video(ruta_archivo: Path, frame_skip: int) -> List[Tuple[int, str]]:
    """Extrae fotogramas de un video, aplicando el salto frame_skip."""
    captura = cv2.VideoCapture(str(ruta_archivo))
    fps = round(captura.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        captura.release()
        return []

    paso = frame_skip + 1
    frames_data = []
    idx = 0
    while captura.isOpened():
        ok, frame = captura.read()
        if not ok: break
        if idx % paso == 0:
            segundo = idx // fps
            hash_val = _calcular_phash_fotograma(frame)
            frames_data.append((segundo, hash_val))
        idx += 1
    captura.release()
    return frames_data

def procesar_archivo(ruta_archivo: Path, frame_skip: int) -> Optional[Dict]:
    nombre = ruta_archivo.name
    Eventos.inicio_procesamiento_archivo(nombre, os.getpid())

    try:
        hash_val = _calcular_phash_imagen(ruta_archivo)
        return {
            "tipo": "imagen",
            "nombre": nombre,
            "ruta": str(ruta_archivo),
            "datos": hash_val,
        }
    except Exception: pass

    try:
        frames = _extraer_frames_video(ruta_archivo, frame_skip)
        if frames:
            return {
                "tipo": "video",
                "nombre": nombre,
                "ruta": str(ruta_archivo),
                "datos": frames,
            }
        else:
            Eventos.advertencia_video_corrupto(nombre)
            return None
        
    except Exception:
        Eventos.archivo_no_reconocido(nombre)
        return None

class ExtractorMetricasMultimedia:
    def __init__(self) -> None:
        self.ruta_dataset = RUTA_DATASET
        self.frame_skip = FRAME_SKIP
        self.parallel_workers = PARALLEL_WORKERS
        self._validar_entorno()

        self._crear_directorios_bd()

        self.db_imagenes = gSQLite(DB_IMAGES_PATH)
        self.db_videos = gSQLite(DB_VIDEOS_PATH)
        self._inicializar_tablas()

        self._ajustar_workers()

    def _ajustar_workers(self) -> None:
        max_cpu = os.cpu_count() or 1
        if self.parallel_workers > max_cpu:
            Eventos.advertencia_workers_excedido(self.parallel_workers, max_cpu)
            self.parallel_workers = max_cpu
        elif self.parallel_workers < 1:
            self.parallel_workers = 1

    def _crear_directorios_bd(self) -> None:
        for ruta in (DB_IMAGES_PATH, DB_VIDEOS_PATH):
            directorio = ruta.parent
            if not directorio.exists():
                directorio.mkdir(parents=True, exist_ok=True)
                Eventos.creacion_directorio_bd(directorio)

    def _inicializar_tablas(self) -> None:
        self.db_imagenes.ejecutar_escritura(Consultas.CREAR_TABLA_IMAGENES)
        self.db_videos.ejecutar_escritura(Consultas.CREAR_TABLA_VIDEOS)

    def _validar_entorno(self) -> None:
        if not self.ruta_dataset.name or not self.ruta_dataset.exists():
            raise ErrorRutaDataset()

    def _recoger_archivos(self) -> List[Path]:
        """Recoge todos los archivos (no directorios) del dataset sin filtrar por extensión."""
        archivos = []
        for raiz, _, nombres in os.walk(self.ruta_dataset):
            for nombre in nombres:
                ruta = Path(raiz) / nombre
                if ruta.is_file():
                    archivos.append(ruta)
        return archivos

    def _insertar_resultados(self, resultados: List[Dict]) -> None:
        lotes_imagenes = []
        lotes_videos = []
        for res in resultados:
            if res["tipo"] == "imagen":
                lotes_imagenes.append((res["nombre"], res["ruta"], res["datos"]))
            elif res["tipo"] == "video":
                for segundo, hash_val in res["datos"]:
                    lotes_videos.append((res["nombre"], res["ruta"], segundo, hash_val))

        if lotes_imagenes:
            self.db_imagenes.ejecutar_escritura_many(
                Consultas.INSERTAR_IMAGEN, lotes_imagenes
            )
            Eventos.info_imagenes_insertadas(len(lotes_imagenes))

        if lotes_videos:
            self.db_videos.ejecutar_escritura_many(
                Consultas.INSERTAR_VIDEO, lotes_videos
            )
            Eventos.info_videos_insertados(len(lotes_videos))

    def _procesar_archivos_en_paralelo(self) -> None:
        archivos = self._recoger_archivos()
        total = len(archivos)
        if total == 0:
            Eventos.sin_archivos()
            return

        Eventos.inicio_paralelo(total, self.parallel_workers)

        for i in range(0, total, BATCH_SIZE):
            lote_archivos = archivos[i:i + BATCH_SIZE]
            resultados_lote = []

            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.parallel_workers
            ) as executor:
                futuros = [
                    executor.submit(procesar_archivo, archivo, self.frame_skip)
                    for archivo in lote_archivos
                ]

                for fut in concurrent.futures.as_completed(futuros):
                    try:
                        res = fut.result()
                        if res is not None:
                            resultados_lote.append(res)
                    except Exception as e:
                        Eventos.error_worker(str(e))

            if resultados_lote:
                self._insertar_resultados(resultados_lote)

            Eventos.progreso_lote(i + len(lote_archivos), total)

    def ejecutar_flujo(self) -> None:
        Eventos.inicio_flujo(str(self.ruta_dataset))
        if self.parallel_workers == 1:
            self._procesar_secuencial()
        else:
            self._procesar_archivos_en_paralelo()
        Eventos.fin_flujo()

    def _procesar_secuencial(self) -> None:
        """Procesa todos los archivos de forma secuencial (sin usar procesos)."""
        archivos = self._recoger_archivos()
        total = len(archivos)
        if total == 0:
            Eventos.sin_archivos()
            return

        Eventos.inicio_paralelo(total, 1)
        resultados = []
        for i, archivo in enumerate(archivos):
            res = procesar_archivo(archivo, self.frame_skip)
            if res is not None:
                resultados.append(res)
            if (i + 1) % 100 == 0 or (i + 1) == total:
                Eventos.progreso_lote(i + 1, total)

        if resultados:
            self._insertar_resultados(resultados)


if __name__ == "__main__":
    extractor = ExtractorMetricasMultimedia()
    extractor.ejecutar_flujo()