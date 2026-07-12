import sqlite3
from pathlib import Path

class gSQLite:
    def __init__(self, ruta_db: Path):
        self.ruta_db = ruta_db

    def ejecutar_escritura(self, consulta: str, parametros: tuple = ()):
        with sqlite3.connect(str(self.ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(consulta, parametros)