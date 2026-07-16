from pathlib import Path
from libs.utils.logging import Logger
from libs.utils.errores import ErrorBase

registrador = Logger.obtener_registrador(__name__)

class ErrorClusterizacion(ErrorBase):
    mensaje_defecto = "Fallo critico durante el proceso de clusterizacion de imagenes."

class Eventos:
    @staticmethod
    def inicio_proceso() -> None:
        registrador.info("Iniciando proceso de clusterizacion continua de imagenes.")

    @staticmethod
    def extraccion_exitosa(cantidad: int) -> None:
        registrador.info(f"Se han extraido {cantidad} registros de la base de datos origen.")

    @staticmethod
    def inicio_busqueda_eps() -> None:
        registrador.info("Iniciando busqueda recursiva de EPS optimo basada en matriz de distancia continua.")

    @staticmethod
    def busqueda_eps_fase(fase: int, eps: float, clusters: int, caida: int) -> None:
        registrador.info(f"Fase {fase} completada | EPS evaluado: {eps:.4f} | Clusters: {clusters} | Caida pre-avalancha: {caida}")

    @staticmethod
    def eps_optimo_encontrado(eps: float) -> None:
        registrador.info(f"EPS optimo encontrado satisfactoriamente: {eps:.5f}")

    @staticmethod
    def clusterizacion_completada(cantidad_clusters: int, ruido: int) -> None:
        registrador.info(f"Agrupacion finalizada. Clusters formados: {cantidad_clusters} | Imagenes no agrupadas (Ruido): {ruido}")

    @staticmethod
    def escritura_completada(ruta: Path) -> None:
        registrador.info(f"Base de datos de clusters generada y poblada exitosamente en: {ruta}")

    @staticmethod
    def fin_proceso() -> None:
        registrador.info("Proceso de clusterizacion de imagenes finalizado.")

class Consultas:
    OBTENER_IMAGENES = """
        SELECT id, nombre_archivo, ruta_completa, phash
        FROM imagenes
        WHERE phash IS NOT NULL
    """

    CREAR_TABLA_CLUSTERS = """
        CREATE TABLE IF NOT EXISTS imagenes_cluster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT UNIQUE,
            ruta_completa TEXT,
            phash BLOB,
            cluster_id INTEGER,
            es_representativa INTEGER
        )
    """

    VACIAR_TABLA_CLUSTERS = """
        DELETE FROM imagenes_cluster
    """

    INSERTAR_IMAGEN_CLUSTER = """
        INSERT INTO imagenes_cluster (nombre_archivo, ruta_completa, phash, cluster_id, es_representativa)
        VALUES (?, ?, ?, ?, ?)
    """