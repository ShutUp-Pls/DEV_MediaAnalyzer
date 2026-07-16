import sqlite3
import cv2
from pathlib import Path
from typing import List, Tuple

from libs.inc_extract_orb import ErrorExtraccionORB, Eventos, Consultas
from libs.utils.gsqlite import gSQLite

MAX_FEATURES_ORB = 500
TAMANO_LOTE = 500

def _extraer_registros(ruta_db: Path) -> List[Tuple]:
    if not ruta_db.exists():
        Eventos.db_no_encontrada(str(ruta_db))
        return []
        
    try:
        with sqlite3.connect(str(ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(Consultas.OBTENER_REGISTROS_CLUSTER)
            return cursor.fetchall()
    except Exception as error:
        raise ErrorExtraccionORB(error_original=error)

def _extraer_matriz_orb(ruta_imagen: str, extractor_orb: cv2.ORB) -> bytes:
    imagen_grises = cv2.imread(ruta_imagen, cv2.IMREAD_GRAYSCALE)
    if imagen_grises is None:
        Eventos.archivo_corrupto(ruta_imagen)
        return None

    _, descriptores = extractor_orb.detectAndCompute(imagen_grises, None)
    
    if descriptores is None:
        Eventos.sin_descriptores(ruta_imagen)
        return None
        
    return descriptores.tobytes()

def _preparar_base_datos_orb(ruta_db_destino: Path) -> gSQLite:
    db_destino = gSQLite(ruta_db_destino)
    db_destino.ejecutar_escritura(Consultas.CREAR_TABLA_ORB)
    db_destino.ejecutar_escritura(Consultas.VACIAR_TABLA_ORB)
    return db_destino

class ExtractorORBCluster:
    def __init__(self, ruta_db_origen: Path, ruta_db_destino: Path):
        self.ruta_db_origen = ruta_db_origen
        self.ruta_db_destino = ruta_db_destino
        self.extractor = cv2.ORB_create(nfeatures=MAX_FEATURES_ORB)

    def ejecutar_flujo(self) -> None:
        Eventos.inicio_proceso()
        
        registros_origen = _extraer_registros(self.ruta_db_origen)
        if not registros_origen:
            return
            
        Eventos.extraccion_clusters_exitosa(len(registros_origen))
        db_destino = _preparar_base_datos_orb(self.ruta_db_destino)
        
        lote_actual = []
        contador_lotes = 1
        total_lotes = (len(registros_origen) // TAMANO_LOTE) + 1
        calculados_orb = 0

        for id_reg, nombre, ruta, phash, c_id, representativa in registros_origen:
            orb_bytes = None
            
            # Solo calculamos ORB para el ruido o los campeones del clúster
            if c_id == -1 or representativa == 1:
                orb_bytes = _extraer_matriz_orb(ruta, self.extractor)
                if orb_bytes is not None:
                    calculados_orb += 1
            
            lote_actual.append((id_reg, nombre, ruta, phash, c_id, representativa, orb_bytes))
            
            if len(lote_actual) >= TAMANO_LOTE:
                Eventos.avance_lote(contador_lotes, total_lotes)
                db_destino.ejecutar_escritura_many(Consultas.INSERTAR_REGISTRO_ORB, lote_actual)
                lote_actual = []
                contador_lotes += 1
                
        # Insertar remanente
        if lote_actual:
            Eventos.avance_lote(contador_lotes, total_lotes)
            db_destino.ejecutar_escritura_many(Consultas.INSERTAR_REGISTRO_ORB, lote_actual)

        Eventos.escritura_completada(self.ruta_db_destino, calculados_orb)


if __name__ == '__main__':
    from libs import DB_IMAGES_PATH
    
    ruta_origen = DB_IMAGES_PATH.parent / "imagenes_cluster.db"
    ruta_destino = DB_IMAGES_PATH.parent / "imagenes_cluster_orb.db"
    
    extractor_orb = ExtractorORBCluster(ruta_origen, ruta_destino)
    extractor_orb.ejecutar_flujo()