from pathlib import Path
from libs.utils.logging import Logger
from libs.utils.errores import ErrorBase

registrador = Logger.obtener_registrador(__name__)

class ErrorReclusterizacionORB(ErrorBase):
    mensaje_defecto = "Fallo critico durante el proceso de re-clusterizacion por ORB."

class Eventos:
    @staticmethod
    def inicio_proceso() -> None:
        registrador.info("Iniciando re-clusterizacion dinamica basada en ORB (Z-Score).")

    @staticmethod
    def db_no_encontrada(ruta: str) -> None:
        registrador.error(f"La base de datos de origen ORB no existe: {ruta}")

    @staticmethod
    def datos_cargados(cantidad_ruido: int, cantidad_clusters: int) -> None:
        registrador.info(f"Datos en memoria: {cantidad_ruido} imagenes de ruido a evaluar contra {cantidad_clusters} clusteres.")

    @staticmethod
    def avance_evaluacion(procesados: int, total: int) -> None:
        registrador.info(f"Evaluando ruido... {procesados}/{total} procesados.")

    @staticmethod
    def ruido_rescatado(nombre: str, nuevo_cluster: int, matches: int, z_score: float) -> None:
        registrador.info(f"[RESCATE] '{nombre}' asignado al cluster {nuevo_cluster} | Matches: {matches} | Z-Score: {z_score:.2f}")

    @staticmethod
    def escritura_completada(ruta: Path) -> None:
        registrador.info(f"Base de datos re-clusterizada guardada exitosamente en: {ruta}")

    @staticmethod
    def resumen_final(total: int, rescatados: int) -> None:
        registrador.info(f"Proceso finalizado. Se rescataron {rescatados} imagenes de un total de {total} ruidos iniciales.")

class Consultas:
    OBTENER_REGISTROS = """
        SELECT id, nombre_archivo, ruta_completa, phash, cluster_id, es_representativa, orb_descriptores
        FROM imagenes_cluster_orb
    """

    CREAR_TABLA_RECLUSTER = """
        CREATE TABLE IF NOT EXISTS imagenes_cluster_orb_re (
            id INTEGER PRIMARY KEY,
            nombre_archivo TEXT UNIQUE,
            ruta_completa TEXT,
            phash BLOB,
            cluster_id INTEGER,
            es_representativa INTEGER,
            orb_descriptores BLOB,
            metodo_agrupacion TEXT
        )
    """

    VACIAR_TABLA_RECLUSTER = """
        DELETE FROM imagenes_cluster_orb_re
    """

    INSERTAR_REGISTRO = """
        INSERT INTO imagenes_cluster_orb_re (id, nombre_archivo, ruta_completa, phash, cluster_id, es_representativa, orb_descriptores, metodo_agrupacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """