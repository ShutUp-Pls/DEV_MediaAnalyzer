import uuid
import traceback
from pathlib import Path
from libs.utils.logging import Logger
from libs.utils import MAX_ARCHIVOS_ERROR, MAX_PESO_DIR_ERROR_MB
from libs import RUTA_RAIZ_PROYECTO

registrador = Logger.obtener_registrador(__name__)

class ErrorBase(Exception):
    mensaje_defecto = "Error desconocido en el proceso."
    
    def __init__(self, mensaje: str = None, error_original: Exception = None):
        self.mensaje = mensaje or self.mensaje_defecto
        self.error_original = error_original
        
        if error_original:
            self.mensaje += f" | Detalle: {str(error_original)}"
            
        super().__init__(self.mensaje)
        self._registrar_y_respaldar_error()

    def _registrar_y_respaldar_error(self):
        id_error = uuid.uuid4().hex[:8]
        ruta_errores = RUTA_RAIZ_PROYECTO / "logs" / "errores"
        ruta_errores.mkdir(parents=True, exist_ok=True)
        
        archivo_error = ruta_errores / f"{id_error}.txt"
        traza = self._extraer_traza()
        
        contenido = f"ID: {id_error}\nExcepcion: {self.__class__.__name__}\nMensaje: {self.mensaje}\n\nTraza:\n{traza}"
        archivo_error.write_text(contenido, encoding="utf-8")
        
        registrador.error(f"Excepcion capturada [{id_error}]: {self.__class__.__name__} | {self.mensaje}")
        
        self._aplicar_politicas_reemplazo(ruta_errores)

    def _extraer_traza(self) -> str:
        if self.error_original and hasattr(self.error_original, "__traceback__") and self.error_original.__traceback__:
            return "".join(traceback.format_exception(
                type(self.error_original), 
                self.error_original, 
                self.error_original.__traceback__
            ))
        return "Traza de ejecucion no disponible."

    def _aplicar_politicas_reemplazo(self, ruta_directorio: Path):
        archivos = sorted(ruta_directorio.glob("*.txt"), key=lambda x: x.stat().st_mtime)
        
        while len(archivos) > MAX_ARCHIVOS_ERROR and archivos:
            archivo_viejo = archivos.pop(0)
            archivo_viejo.unlink()

        while self._obtener_tamano_directorio(ruta_directorio) > (MAX_PESO_DIR_ERROR_MB * 1024 * 1024) and archivos:
            archivo_viejo = archivos.pop(0)
            archivo_viejo.unlink()

    def _obtener_tamano_directorio(self, ruta_directorio: Path) -> float:
        return sum(f.stat().st_size for f in ruta_directorio.glob("*.txt") if f.is_file())