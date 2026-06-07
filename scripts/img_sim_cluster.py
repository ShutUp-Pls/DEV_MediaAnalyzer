import shutil
from pathlib import Path
from PIL import Image
import imagehash

def agrupar_similares(ruta_carpeta, umbral_diferencia=5):
    """
    Acción: Usa hashes perceptuales para agrupar imágenes visualmente similares.
    El 'umbral_diferencia' define qué tan estrictos somos. 
    0 = idénticas, 5-10 = soporta cambios de contraste, recortes, marcas de agua.
    """
    directorio = Path(ruta_carpeta)
    
    if not directorio.exists() or not directorio.is_dir():
        print(f"Error: La ruta '{ruta_carpeta}' no existe.")
        return

    extensiones_validas = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
    diccionario_hashes = {}
    
    print("Analizando imágenes... esto puede tomar un momento dependiendo de la cantidad.")
    
    # Calcular el hash de todas las imágenes
    for archivo in directorio.iterdir():
        if archivo.is_file() and archivo.suffix.lower() in extensiones_validas:
            try:
                # Abrimos la imagen y calculamos su pHash
                img = Image.open(archivo)
                hash_img = imagehash.phash(img)
                diccionario_hashes[archivo] = hash_img
            except Exception as e:
                print(f"No se pudo procesar {archivo.name}: {e}")

    # Agrupar mediante comparación de hashes
    grupos = [] # Lista de listas, donde cada sublista tiene rutas de imágenes similares
    
    for archivo, h_actual in diccionario_hashes.items():
        agregado = False
        for grupo in grupos:
            archivo_referencia = grupo[0]
            hash_referencia = diccionario_hashes[archivo_referencia]
            
            # Restar hashes de imagehash nos da la "distancia" o diferencia entre ellos
            if abs(h_actual - hash_referencia) <= umbral_diferencia:
                grupo.append(archivo)
                agregado = True
                break
                
        if not agregado:
            grupos.append([archivo])

    # Mover a carpetas (solo creamos carpetas para grupos de 2 o más imágenes)
    cont_grupos = 0
    cont_movidas = 0

    for i, grupo in enumerate(grupos):
        if len(grupo) > 1:
            cont_grupos += 1
            nombre_carpeta = f"Grupo_Similar_{cont_grupos:03d}"
            carpeta_destino = directorio / nombre_carpeta
            carpeta_destino.mkdir(exist_ok=True)
            
            for archivo in grupo:
                try:
                    shutil.move(str(archivo), str(carpeta_destino / archivo.name))
                    cont_movidas += 1
                except Exception as e:
                    print(f"Error al mover {archivo.name}: {e}")

    print("--- AGRUPACIÓN COMPLETADA ---")
    print(f"Se crearon {cont_grupos} carpetas agrupando un total de {cont_movidas} imágenes similares.\n")


def desagrupar_similares(ruta_carpeta):
    """
    Reversión: Saca todas las imágenes de las carpetas 'Grupo_Similar_XXX' 
    y las devuelve a la raíz, eliminando luego las carpetas.
    """
    directorio = Path(ruta_carpeta)
    
    if not directorio.exists() or not directorio.is_dir():
        print(f"Error: La ruta '{ruta_carpeta}' no existe.")
        return

    cont_restaurados = 0

    # Buscamos todas las subcarpetas que empiecen con el prefijo de nuestro agrupador
    for subcarpeta in directorio.iterdir():
        if subcarpeta.is_dir() and subcarpeta.name.startswith("Grupo_Similar_"):
            
            # Devolvemos los archivos a la raíz
            for archivo in subcarpeta.iterdir():
                if archivo.is_file():
                    try:
                        shutil.move(str(archivo), str(directorio / archivo.name))
                        cont_restaurados += 1

                    except Exception as e: print(f"Error al restaurar {archivo.name}: {e}")
            
            # Eliminamos la carpeta vacía
            try: subcarpeta.rmdir()
            except OSError: print(f"Nota: '{subcarpeta.name}' no se pudo eliminar (probablemente no esté vacía).")

    print("--- REVERSIÓN COMPLETADA ---")
    print(f"Imágenes devueltas a la carpeta principal: {cont_restaurados}\n")