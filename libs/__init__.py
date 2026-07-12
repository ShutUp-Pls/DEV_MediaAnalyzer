import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path


RUTA_ENV = find_dotenv()
load_dotenv(RUTA_ENV)
RUTA_RAIZ_PROYECTO = Path(RUTA_ENV).parent if RUTA_ENV else Path(__file__).resolve().parent.parent

_ruta_env = os.getenv("DATASET_PATH", "")
RUTA_DATASET = RUTA_RAIZ_PROYECTO / _ruta_env if _ruta_env else Path("")

DB_IMAGENES_NOMBRE  = os.getenv("DB_IMAGES_NAME", "imagenes.db")
DB_VIDEOS_NOMBRE    = os.getenv("DB_VIDEOS_NAME", "videos.db")