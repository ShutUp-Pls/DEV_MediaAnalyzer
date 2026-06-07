import shutil
from pathlib import Path

def separar_multimedia(ruta_carpeta):
    """Acción: Separa fotos y videos en subcarpetas."""
    directorio = Path(ruta_carpeta)
    
    if not directorio.exists() or not directorio.is_dir():
        print(f"Error: La ruta '{ruta_carpeta}' no existe o no es un directorio válido.")
        return

    carpeta_fotos = directorio / "Fotos"
    carpeta_videos = directorio / "Videos"

    carpeta_fotos.mkdir(exist_ok=True)
    carpeta_videos.mkdir(exist_ok=True)

    extensiones_fotos = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.raw'}
    extensiones_videos = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}

    cont_fotos, cont_videos = 0, 0

    for archivo in directorio.iterdir():
        if archivo.is_file():
            extension = archivo.suffix.lower()
            try:
                if extension in extensiones_fotos:
                    shutil.move(str(archivo), str(carpeta_fotos / archivo.name))
                    cont_fotos += 1
                elif extension in extensiones_videos:
                    shutil.move(str(archivo), str(carpeta_videos / archivo.name))
                    cont_videos += 1
            except Exception as e:
                print(f"Error al mover {archivo.name}: {e}")

    print("--- SEPARACIÓN COMPLETADA ---")
    print(f"Fotos movidas: {cont_fotos} | Videos movidos: {cont_videos}\n")


def unir_multimedia(ruta_carpeta):
    """Reversión: Devuelve los archivos a la raíz y elimina las subcarpetas."""
    directorio = Path(ruta_carpeta)
    
    if not directorio.exists() or not directorio.is_dir():
        print(f"Error: La ruta '{ruta_carpeta}' no existe o no es un directorio válido.")
        return

    carpetas_a_vaciar = [directorio / "Fotos", directorio / "Videos"]
    cont_restaurados = 0

    for subcarpeta in carpetas_a_vaciar:
        # Verificamos que la subcarpeta exista antes de intentar vaciarla
        if subcarpeta.exists() and subcarpeta.is_dir():
            # Devolvemos cada archivo a la carpeta principal
            for archivo in subcarpeta.iterdir():
                if archivo.is_file():
                    try:
                        shutil.move(str(archivo), str(directorio / archivo.name))
                        cont_restaurados += 1
                    except Exception as e:
                        print(f"Error al restaurar {archivo.name}: {e}")
            
            # Intentamos eliminar la subcarpeta ya vacía
            try:
                subcarpeta.rmdir()
            except OSError:
                print(f"Nota: No se pudo eliminar '{subcarpeta.name}' porque contiene archivos no reconocidos.")

    print("--- REVERSIÓN COMPLETADA ---")
    print(f"Archivos devueltos a la carpeta principal: {cont_restaurados}\n")


# --- EJEMPLO DE USO ---
ruta_objetivo = r"C:\RUTA\A\TU\CARPETA" 

# Para ejecutar la acción, descomenta la línea de abajo:
# separar_multimedia(ruta_objetivo)

# Para revertir la acción, descomenta la línea de abajo:
# unir_multimedia(ruta_objetivo)