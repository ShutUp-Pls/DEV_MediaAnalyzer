import sqlite3
import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from libs.inc_cluster_orb import ErrorReclusterizacionORB, Eventos, Consultas
from libs.utils.gsqlite import gSQLite

# Parametros Dinámicos Mejorados
UMBRAL_Z_SCORE = 3.5
PROPORCION_LOWE = 0.75
PORCENTAJE_MINIMO_OVERLAP = 0.12  
MIN_MATCHES_DURO = 5             
DESVIACION_MINIMA_SUAVIZADA = 5.0 

def _extraer_registros(ruta_db: Path) -> List[Tuple]:
    if not ruta_db.exists():
        Eventos.db_no_encontrada(str(ruta_db))
        return []
    try:
        with sqlite3.connect(str(ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(Consultas.OBTENER_REGISTROS)
            return cursor.fetchall()
    except Exception as error:
        raise ErrorReclusterizacionORB(error_original=error)

def _decodificar_descriptores(blob: Optional[bytes]) -> Optional[np.ndarray]:
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.uint8).reshape(-1, 32)

def _calcular_buenos_matches(desc1: np.ndarray, desc2: np.ndarray, matcher: cv2.BFMatcher) -> int:
    if desc1 is None or desc2 is None or len(desc1) < 2 or len(desc2) < 2:
        return 0
    try:
        matches = matcher.knnMatch(desc1, desc2, k=2)
        buenos = 0
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < PROPORCION_LOWE * n.distance:
                    buenos += 1
        return buenos
    except Exception:
        return 0

def _evaluar_ruido_zscore(matches_por_cluster: Dict[int, int], total_features_ruido: int) -> Tuple[Optional[int], int, float]:
    if not matches_por_cluster:
        return None, 0, 0.0

    scores = list(matches_por_cluster.values())
    max_score = np.max(scores)
    
    min_requerido = max(MIN_MATCHES_DURO, int(total_features_ruido * PORCENTAJE_MINIMO_OVERLAP))
    
    if max_score < min_requerido:
        return None, int(max_score), 0.0

    media = np.mean(scores)
    desviacion = np.std(scores)
    desviacion_suavizada = max(desviacion, DESVIACION_MINIMA_SUAVIZADA)
    
    z_score = (max_score - media) / desviacion_suavizada

    scores_ordenados = sorted(scores, reverse=True)
    top1 = scores_ordenados[0]
    top2 = scores_ordenados[1] if len(scores_ordenados) > 1 else 0

    if z_score >= UMBRAL_Z_SCORE and top1 >= (top2 * 1.3):
        mejor_cluster = max(matches_por_cluster, key=matches_por_cluster.get)
        return mejor_cluster, int(max_score), float(z_score)
        
    return None, int(max_score), float(z_score)

def _preparar_base_datos(ruta_db_destino: Path) -> gSQLite:
    db_destino = gSQLite(ruta_db_destino)
    db_destino.ejecutar_escritura(Consultas.CREAR_TABLA_RECLUSTER)
    db_destino.ejecutar_escritura(Consultas.VACIAR_TABLA_RECLUSTER)
    return db_destino

class ReclusterizadorORB:
    def __init__(self, ruta_db_origen: Path, ruta_db_destino: Path):
        self.ruta_db_origen = ruta_db_origen
        self.ruta_db_destino = ruta_db_destino
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def ejecutar_flujo(self) -> None:
        Eventos.inicio_proceso()
        registros = _extraer_registros(self.ruta_db_origen)
        if not registros: return

        representativas_por_cluster: Dict[int, List[np.ndarray]] = {}
        lista_ruido: List[Tuple] = []

        for reg in registros:
            c_id = reg[4]
            es_rep = reg[5]
            
            if c_id == -1:
                lista_ruido.append(reg)
            elif es_rep == 1:
                desc = _decodificar_descriptores(reg[6])
                if desc is not None:
                    if c_id not in representativas_por_cluster:
                        representativas_por_cluster[c_id] = []
                    representativas_por_cluster[c_id].append(desc)

        Eventos.datos_cargados(len(lista_ruido), len(representativas_por_cluster))
        
        registros_actualizados = []
        ruido_rescatado = 0
        total_ruido = len(lista_ruido)

        for idx, reg_ruido in enumerate(lista_ruido):
            desc_ruido = _decodificar_descriptores(reg_ruido[6])
            nombre_archivo = reg_ruido[1]
            
            if (idx + 1) % 50 == 0 or (idx + 1) == total_ruido:
                Eventos.avance_evaluacion(idx + 1, total_ruido)

            if desc_ruido is None:
                reg_modificado = list(reg_ruido)
                reg_modificado.append('Ruido')
                registros_actualizados.append(tuple(reg_modificado))
                continue

            cantidad_features_ruido = len(desc_ruido)
            scores_por_cluster = {}
            
            for c_id, descriptores_campeones in representativas_por_cluster.items():
                max_match_interno = 0
                for desc_camp in descriptores_campeones:
                    matches = _calcular_buenos_matches(desc_ruido, desc_camp, self.matcher)
                    if matches > max_match_interno:
                        max_match_interno = matches
                scores_por_cluster[c_id] = max_match_interno

            nuevo_cluster, max_matches, z_score = _evaluar_ruido_zscore(scores_por_cluster, cantidad_features_ruido)

            if nuevo_cluster is not None:
                Eventos.ruido_rescatado(nombre_archivo, nuevo_cluster, max_matches, z_score)
                reg_modificado = list(reg_ruido)
                reg_modificado[4] = nuevo_cluster
                reg_modificado.append('ORB') # Etiquetar como rescatado por ORB
                registros_actualizados.append(tuple(reg_modificado))
                ruido_rescatado += 1
            else:
                reg_modificado = list(reg_ruido)
                reg_modificado.append('Ruido') # Etiquetar como Ruido absoluto
                registros_actualizados.append(tuple(reg_modificado))

        registros_finales = []
        for reg in registros:
            if reg[4] != -1:
                reg_modificado = list(reg)
                reg_modificado.append('pHash') # Etiquetar original de pHash
                registros_finales.append(tuple(reg_modificado))
                
        registros_finales.extend(registros_actualizados)

        db_destino = _preparar_base_datos(self.ruta_db_destino)
        db_destino.ejecutar_escritura_many(Consultas.INSERTAR_REGISTRO, registros_finales)
        
        Eventos.escritura_completada(self.ruta_db_destino)
        Eventos.resumen_final(total_ruido, ruido_rescatado)

if __name__ == '__main__':
    from libs import DB_IMAGES_PATH
    
    ruta_origen = DB_IMAGES_PATH.parent / "imagenes_cluster_orb.db"
    ruta_destino = DB_IMAGES_PATH.parent / "imagenes_cluster_orb_re.db"
    
    reclusterizador = ReclusterizadorORB(ruta_origen, ruta_destino)
    reclusterizador.ejecutar_flujo()