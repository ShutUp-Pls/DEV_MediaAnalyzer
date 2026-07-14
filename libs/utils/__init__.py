import os

LOG_MAX_ARCHIVOS = int(os.getenv("LOG_MAX_FILES", "5"))
LOG_MAX_PESO_MB = float(os.getenv("LOG_MAX_SIZE_MB", "10.0"))

MAX_ARCHIVOS_ERROR = int(os.getenv("ERRORS_MAX_FILES", "50"))
MAX_PESO_DIR_ERROR_MB = float(os.getenv("ERRORS_MAX_DIR_SIZE_MB", "50.0"))