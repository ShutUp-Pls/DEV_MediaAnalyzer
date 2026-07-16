from pathlib import Path
from libs.utils.logging import Logger
from libs.utils.errores import ErrorBase

registrador = Logger.obtener_registrador(__name__)

class ErrorExtraccionORB(ErrorBase):
    mensaje_defecto = "Fallo critico al extraer ORB y construir la nueva base de datos."

class Eventos:
    @staticmethod
    def inicio_proceso() -> None:
        registrador.info("Iniciando extraccion de caracteristicas ORB para ruido y representativas.")

    @staticmethod
    def extraccion_clusters_exitosa(cantidad: int) -> None:
        registrador.info(f"Se obtuvieron {cantidad} registros desde la base de datos de clusters.")

    @staticmethod
    def db_no_encontrada(ruta: str) -> None:
        registrador.error(f"La base de datos de origen no existe: {ruta}")

    @staticmethod
    def archivo_corrupto(ruta: str) -> None:
        registrador.warning(f"No se pudo leer la imagen, omitiendo calculo ORB: {ruta}")

    @staticmethod
    def sin_descriptores(ruta: str) -> None:
        registrador.warning(f"La imagen no tiene suficientes texturas para extraer descriptores ORB: {ruta}")

    @staticmethod
    def avance_lote(lote_actual: int, total_lotes: int) -> None:
        registrador.info(f"Procesando extraccion ORB... lote {lote_actual} de {total_lotes}.")

    @staticmethod
    def escritura_completada(ruta: Path, calculados: int) -> None:
        registrador.info(f"Proceso finalizado. ORB calculado para {calculados} imagenes. DB guardada en: {ruta}")

class Consultas:
    OBTENER_REGISTROS_CLUSTER = """
        SELECT id, nombre_archivo, ruta_completa, phash, cluster_id, es_representativa
        FROM imagenes_cluster
    """

    CREAR_TABLA_ORB = """
        CREATE TABLE IF NOT EXISTS imagenes_cluster_orb (
            id INTEGER PRIMARY KEY,
            nombre_archivo TEXT UNIQUE,
            ruta_completa TEXT,
            phash BLOB,
            cluster_id INTEGER,
            es_representativa INTEGER,
            orb_descriptores BLOB
        )
    """

    VACIAR_TABLA_ORB = """
        DELETE FROM imagenes_cluster_orb
    """

    INSERTAR_REGISTRO_ORB = """
        INSERT INTO imagenes_cluster_orb (id, nombre_archivo, ruta_completa, phash, cluster_id, es_representativa, orb_descriptores)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """