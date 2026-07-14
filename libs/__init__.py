import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

# VARIABLES RUTAS

RUTA_ENV = find_dotenv()
load_dotenv(RUTA_ENV)
RUTA_RAIZ_PROYECTO = Path(RUTA_ENV).parent if RUTA_ENV else Path(__file__).resolve().parent.parent

def _resolver_ruta(valor: str, base: Path) -> Path:
    if os.path.isabs(valor): return Path(valor).resolve()
    return (base / valor).resolve()

_ruta_env = os.getenv("DATASET_PATH", "")
RUTA_DATASET = _resolver_ruta(_ruta_env, RUTA_RAIZ_PROYECTO) if _ruta_env else Path("")

DB_IMAGES_PATH = _resolver_ruta(
    os.getenv("DB_IMAGES_PATH", "imagenes.db"),
    RUTA_RAIZ_PROYECTO
)

DB_VIDEOS_PATH = _resolver_ruta(
    os.getenv("DB_VIDEOS_PATH", "videos.db"),
    RUTA_RAIZ_PROYECTO
)

# VARIABLES METRICAS

FRAME_SKIP = int(os.getenv("FRAME_SKIP", "0"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "250"))
PARALLEL_WORKERS = int(os.getenv("PARALLEL_WORKERS", "1"))