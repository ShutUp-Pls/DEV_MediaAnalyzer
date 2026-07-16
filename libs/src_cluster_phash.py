import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Tuple, Set
from sklearn.cluster import DBSCAN

from libs.inc_cluster_phash import ErrorClusterizacion, Eventos, Consultas
from libs.utils.gsqlite import gSQLite

SIGMA_SIMILITUD = 10.0
MUESTRAS_MINIMAS_CLUSTER = 2
RANGO_MIN_EPS = 0.01
RANGO_MAX_EPS = 0.99
PASO_INICIAL_EPS = 0.1
TOLERANCIA_DECIMALES = 0.001

def _extraer_registros(ruta_db: Path) -> List[Tuple[int, str, str, bytes]]:
    try:
        with sqlite3.connect(str(ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(Consultas.OBTENER_IMAGENES)
            return cursor.fetchall()
    except Exception as error:
        raise ErrorClusterizacion(error_original=error)

def _calcular_distancia_hamming(hash_a: int, hash_b: int) -> int:
    return (hash_a ^ hash_b).bit_count()

def _decodificar_hash(hash_bytes: bytes) -> int:
    return int.from_bytes(hash_bytes, 'big')

def _calcular_matriz_distancia_continua(hashes_bytes: List[bytes]) -> np.ndarray:
    cantidad = len(hashes_bytes)
    matriz = np.zeros((cantidad, cantidad))
    hashes_enteros = [_decodificar_hash(hb) for hb in hashes_bytes]
    
    for i in range(cantidad):
        for j in range(i + 1, cantidad):
            distancia_discreta = _calcular_distancia_hamming(hashes_enteros[i], hashes_enteros[j])
            similitud = np.exp(-distancia_discreta / SIGMA_SIMILITUD)
            distancia_continua = 1.0 - similitud
            
            matriz[i, j] = distancia_continua
            matriz[j, i] = distancia_continua
            
    return matriz

def _buscar_eps_optimo_recursivo(
    matriz_distancia: np.ndarray,
    rango_min: float,
    rango_max: float,
    paso: float,
    tolerancia: float,
    fase: int = 1
) -> float:
    eps_valores = list(np.arange(rango_min, rango_max + paso, paso))
    lista_clusters = []

    for eps in eps_valores:
        modelo = DBSCAN(metric='precomputed', eps=eps, min_samples=MUESTRAS_MINIMAS_CLUSTER)
        etiquetas = modelo.fit_predict(matriz_distancia)
        cantidad_clusters = len(set(etiquetas)) - (1 if -1 in etiquetas else 0)
        lista_clusters.append(cantidad_clusters)

    indice_pico = int(np.argmax(lista_clusters))
    clusters_pico = lista_clusters[indice_pico]

    if clusters_pico == 0:
        Eventos.busqueda_eps_fase(fase, eps_valores[indice_pico], 0, 0)
        if paso <= tolerancia:
            return eps_valores[indice_pico]
        nuevo_paso = paso / 5.0
        return _buscar_eps_optimo_recursivo(matriz_distancia, rango_min, rango_max, nuevo_paso, tolerancia, fase + 1)

    caidas = []
    for i in range(indice_pico, len(lista_clusters) - 1):
        caidas.append(lista_clusters[i] - lista_clusters[i + 1])

    indice_ideal = indice_pico
    caida_detectada = 0

    if caidas:
        caida_maxima = max(caidas)
        umbral_relativo = max(2.0, float(clusters_pico) * 0.10)
        umbral_avalancha = max(3.0, float(caida_maxima) * 0.35)

        for i, caida in enumerate(caidas):
            if caida < 3:
                continue
            if float(caida) >= umbral_relativo or float(caida) >= umbral_avalancha:
                indice_ideal = indice_pico + i
                caida_detectada = caida
                break
        else:
            indice_ideal = indice_pico + int(np.argmax(caidas))
            caida_detectada = caida_maxima

    eps_ideal = eps_valores[indice_ideal]
    Eventos.busqueda_eps_fase(fase, eps_ideal, clusters_pico, caida_detectada)

    if paso <= tolerancia:
        Eventos.eps_optimo_encontrado(eps_ideal)
        return eps_ideal

    nuevo_paso = paso / 5.0
    nuevo_min = max(0.0001, eps_ideal - paso)
    nuevo_max = eps_ideal + paso

    return _buscar_eps_optimo_recursivo(
        matriz_distancia, nuevo_min, nuevo_max, nuevo_paso, tolerancia, fase + 1
    )

def _identificar_indices_representativos(hashes: List[int]) -> Set[int]:
    cantidad = len(hashes)
    if cantidad <= 3:
        return set(range(cantidad))

    max_distancia = -1
    idx_a = idx_b = 0

    for i in range(cantidad):
        for j in range(i + 1, cantidad):
            distancia = _calcular_distancia_hamming(hashes[i], hashes[j])
            if distancia > max_distancia:
                max_distancia = distancia
                idx_a, idx_b = i, j

    mejor_centroide = -1
    mejor_diferencia = float('inf')

    for i in range(cantidad):
        if i == idx_a or i == idx_b:
            continue
        dist_a = _calcular_distancia_hamming(hashes[i], hashes[idx_a])
        dist_b = _calcular_distancia_hamming(hashes[i], hashes[idx_b])
        diferencia = abs(dist_a - dist_b)
        
        if diferencia < mejor_diferencia:
            mejor_diferencia = diferencia
            mejor_centroide = i

    return {idx_a, idx_b, mejor_centroide}

def _generar_lotes_insercion(
    registros_originales: List[Tuple[int, str, str, bytes]], 
    etiquetas: np.ndarray
) -> List[Tuple[str, str, bytes, int, int]]:
    
    agrupaciones_por_cluster = {}
    for i, etiqueta in enumerate(etiquetas):
        c_id = int(etiqueta)
        if c_id not in agrupaciones_por_cluster:
            agrupaciones_por_cluster[c_id] = []
        agrupaciones_por_cluster[c_id].append(i)

    indices_representativos_globales = set()
    for c_id, indices in agrupaciones_por_cluster.items():
        if c_id == -1:
            continue
            
        hashes_cluster = [_decodificar_hash(registros_originales[i][3]) for i in indices]
        indices_relativos_representativos = _identificar_indices_representativos(hashes_cluster)
        
        for idx_rel in indices_relativos_representativos:
            indices_representativos_globales.add(indices[idx_rel])

    lotes = []
    for i, registro in enumerate(registros_originales):
        _, nombre_archivo, ruta_completa, phash = registro
        cluster_id = int(etiquetas[i])
        es_representativa = 1 if i in indices_representativos_globales else 0
        lotes.append((nombre_archivo, ruta_completa, phash, cluster_id, es_representativa))
        
    return lotes

def _preparar_base_datos_clusters(ruta_db_destino: Path) -> gSQLite:
    db_destino = gSQLite(ruta_db_destino)
    db_destino.ejecutar_escritura(Consultas.CREAR_TABLA_CLUSTERS)
    db_destino.ejecutar_escritura(Consultas.VACIAR_TABLA_CLUSTERS)
    return db_destino

class ClusterizadorImagenes:
    def __init__(self, ruta_db_origen: Path, ruta_db_destino: Path):
        self.ruta_db_origen = ruta_db_origen
        self.ruta_db_destino = ruta_db_destino

    def ejecutar_flujo(self) -> None:
        Eventos.inicio_proceso()
        
        registros = _extraer_registros(self.ruta_db_origen)
        Eventos.extraccion_exitosa(len(registros))
        
        if len(registros) < MUESTRAS_MINIMAS_CLUSTER:
            Eventos.fin_proceso()
            return

        hashes_bytes = [registro[3] for registro in registros]
        matriz_distancia = _calcular_matriz_distancia_continua(hashes_bytes)
        
        Eventos.inicio_busqueda_eps()
        eps_optimo = _buscar_eps_optimo_recursivo(
            matriz_distancia, 
            RANGO_MIN_EPS, 
            RANGO_MAX_EPS, 
            PASO_INICIAL_EPS, 
            TOLERANCIA_DECIMALES
        )
        
        modelo_final = DBSCAN(metric='precomputed', eps=eps_optimo, min_samples=MUESTRAS_MINIMAS_CLUSTER)
        etiquetas_finales = modelo_final.fit_predict(matriz_distancia)
        
        cantidad_clusters = len(set(etiquetas_finales)) - (1 if -1 in etiquetas_finales else 0)
        ruido = list(etiquetas_finales).count(-1)
        Eventos.clusterizacion_completada(cantidad_clusters, ruido)
        
        lotes_insercion = _generar_lotes_insercion(registros, etiquetas_finales)
        
        db_destino = _preparar_base_datos_clusters(self.ruta_db_destino)
        db_destino.ejecutar_escritura_many(Consultas.INSERTAR_IMAGEN_CLUSTER, lotes_insercion)
        
        Eventos.escritura_completada(self.ruta_db_destino)
        Eventos.fin_proceso()

if __name__ == '__main__':
    from libs import DB_IMAGES_PATH
    
    ruta_origen = DB_IMAGES_PATH
    ruta_destino = DB_IMAGES_PATH.parent / "imagenes_cluster.db"
    
    clusterizador = ClusterizadorImagenes(ruta_origen, ruta_destino)
    clusterizador.ejecutar_flujo()