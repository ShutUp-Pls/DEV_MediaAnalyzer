import sqlite3
import base64
import logging
import random
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import plotly.graph_objects as go
from sklearn.manifold import TSNE
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
import dash
from dash import dcc, html, Input, Output, State, Patch

DIRECTORIO_SCRIPT = Path(__file__).resolve().parent
RUTA_BASE_DATOS = DIRECTORIO_SCRIPT / ".." / ".media" / "data" / "imagenes.db"
LIMITE_MUESTRA = 5000
CLUSTER_EPS_MAXIMO = 40
PERPLEJIDAD_MINIMA = 2
PERPLEJIDAD_MAXIMA = 50
CLUSTER_MUESTRAS_MINIMAS = 2
PUERTO_SERVIDOR = 8050

class EstilosUI:
    COLOR_FONDO = "#f4f6f9"
    COLOR_TEXTO_PRIMARIO = "#2c3e50"
    COLOR_TEXTO_SECUNDARIO = "#7f8c8d"
    COLOR_TEXTO_ERROR = "#e74c3c"
    COLOR_FONDO_TARJETA = "white"
    
    TARJETA_BASE = {
        'backgroundColor': COLOR_FONDO_TARJETA, 
        'borderRadius': '12px', 
        'boxShadow': '0 4px 12px rgba(0,0,0,0.05)', 
        'padding': '20px'
    }
    CONTENEDOR_APP = {
        'backgroundColor': COLOR_FONDO, 
        'fontFamily': 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif', 
        'height': '100vh', 
        'padding': '20px', 
        'boxSizing': 'border-box',
        'display': 'flex',
        'flexDirection': 'column',
        'overflow': 'hidden'
    }
    CABECERA = {**TARJETA_BASE, 'marginBottom': '20px', 'flexShrink': '0', 'padding': '15px 20px'}
    PANEL_SLIDER = {**TARJETA_BASE, 'marginBottom': '20px', 'flexShrink': '0'}
    FLEX_CONTENEDOR = {
        'display': 'flex', 'gap': '20px', 'flex': '1', 'minHeight': '0'
    }
    PANEL_IZQUIERDO = {**TARJETA_BASE, 'flex': '2', 'display': 'flex', 'flexDirection': 'column', 'minHeight': '0'}
    PANEL_DERECHO = {**TARJETA_BASE, 'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'minHeight': '0'}
    CONTENEDOR_IMAGEN_ACTIVA = {
        'flex': '1', 'display': 'flex', 'flexDirection': 'column', 
        'alignItems': 'center', 'justifyContent': 'center', 'textAlign': 'center',
        'overflow': 'hidden'
    }
    IMAGEN_MOSTRADA = {
        'maxWidth': '100%', 'maxHeight': '100%', 'objectFit': 'contain',
        'border': '1px solid #ecf0f1', 'borderRadius': '8px',
        'boxShadow': '0 8px 16px rgba(0,0,0,0.1)'
    }
    ETIQUETA_ARCHIVO = {
        'backgroundColor': '#f8f9fa', 'padding': '12px', 'borderRadius': '8px', 
        'marginBottom': '20px', 'width': '100%', 'textAlign': 'left', 'flexShrink': '0'
    }

class ErrorBaseVisualizador(Exception):
    mensaje_defecto = "Ocurrió un error inesperado en el visualizador 3D."

    def __init__(self, mensaje: str = None, error_original: Exception = None):
        self.mensaje = mensaje or self.mensaje_defecto
        if error_original:
            self.mensaje += f" | Detalle: {str(error_original)}"
        super().__init__(self.mensaje)

class ErrorCargaDatos(ErrorBaseVisualizador):
    mensaje_defecto = "Fallo crítico al cargar o procesar los datos desde la base de datos."

class Logger:
    _codificacion = 'utf-8'
    _formato = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    @staticmethod
    def obtener_registrador(nombre_modulo: str) -> logging.Logger:
        registrador = logging.getLogger(nombre_modulo)
        if not registrador.handlers:
            registrador.setLevel(logging.INFO)
            manejador_consola = logging.StreamHandler()
            manejador_consola.setLevel(logging.INFO)
            manejador_consola.setFormatter(Logger._formato)
            registrador.addHandler(manejador_consola)
            registrador.propagate = False
        return registrador

registrador = Logger.obtener_registrador(__name__)

class Eventos:
    @staticmethod
    def inicio_servidor(puerto: int) -> None:
        registrador.info(f"Servidor Dash iniciado exitosamente en http://127.0.0.1:{puerto}")

    @staticmethod
    def sin_datos_suficientes() -> None:
        registrador.warning("No se obtuvieron registros suficientes para construir la visualización 3D.")

    @staticmethod
    def analisis_codo_robusto(pico_grupos: int, eps_pico: int, eps_final: int, caida_evitada: int) -> None:
        registrador.info("Análisis de Método del Codo Robusto completado.")
        registrador.info(f"Pico de grupos detectado: {pico_grupos} grupos (EPS={eps_pico}).")
        registrador.info(f"Freno de avalancha activado antes de perder {caida_evitada} grupos.")
        registrador.info(f"EPS final asignado: {eps_final}.")

    @staticmethod
    def busqueda_perplejidad(fase: str, perplejidad: int, score: float) -> None:
        registrador.info(f"Búsqueda Perplejidad [{fase}]: Perp={perplejidad} | Silueta={score:.4f}")

    @staticmethod
    def perplejidad_optima_encontrada(perplejidad: int) -> None:
        registrador.info(f"Perplejidad óptima final asignada: {perplejidad}")

    @staticmethod
    def imagen_no_encontrada(ruta: str) -> None:
        registrador.warning(f"La imagen solicitada no existe en el sistema de archivos: {ruta}")

    @staticmethod
    def error_carga_imagen(ruta: str, detalle: str) -> None:
        registrador.error(f"Error al decodificar la imagen solicitada ({ruta}): {detalle}")

    @staticmethod
    def error_general(detalle: str) -> None:
        registrador.error(f"Error general en el sistema: {detalle}")

class Consultas:
    OBTENER_IMAGENES = """
        SELECT id, nombre_archivo, phash, ruta_completa 
        FROM imagenes
    """

class GestorBaseDatos:
    @staticmethod
    def extraer_registros(ruta_db: Path) -> List[Tuple]:
        with sqlite3.connect(str(ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(Consultas.OBTENER_IMAGENES)
            return cursor.fetchall()

def _obtener_muestra_aleatoria(filas: List[Tuple], limite: int) -> List[Tuple]:
    if len(filas) > limite:
        return random.sample(filas, limite)
    return filas

def _formatear_registros_db(filas: List[Tuple]) -> Tuple[List[int], List[str], List[int], List[str]]:
    ids = [fila[0] for fila in filas]
    nombres = [fila[1] for fila in filas]
    hashes = [int.from_bytes(fila[2], 'big') if fila[2] is not None else 0 for fila in filas]
    rutas = [fila[3] for fila in filas]
    return ids, nombres, hashes, rutas

def _cargar_datos(ruta_db: Path, limite: int) -> Tuple[List[int], List[str], List[int], List[str]]:
    try:
        filas = GestorBaseDatos.extraer_registros(ruta_db)
        filas_muestra = _obtener_muestra_aleatoria(filas, limite)
        return _formatear_registros_db(filas_muestra)
    except Exception as error:
        raise ErrorCargaDatos(error_original=error)

def _calcular_distancia_hamming(hash_a: int, hash_b: int) -> int:
    return (hash_a ^ hash_b).bit_count()

def _calcular_matriz_similitud(hashes: List[int], sigma: int = 10) -> np.ndarray:
    cantidad = len(hashes)
    matriz_similitud = np.zeros((cantidad, cantidad))
    for i in range(cantidad):
        for j in range(i + 1, cantidad):
            distancia = _calcular_distancia_hamming(hashes[i], hashes[j])
            similitud = np.exp(-distancia / sigma)
            matriz_similitud[i, j] = similitud
            matriz_similitud[j, i] = similitud
    return matriz_similitud

def _calcular_matriz_distancia(hashes: List[int]) -> np.ndarray:
    cantidad = len(hashes)
    matriz_distancia = np.zeros((cantidad, cantidad))
    for i in range(cantidad):
        for j in range(i + 1, cantidad):
            distancia = _calcular_distancia_hamming(hashes[i], hashes[j])
            matriz_distancia[i, j] = distancia
            matriz_distancia[j, i] = distancia
    return matriz_distancia

def _determinar_eps_optimo(lista_clusters: List[int], lista_eps: List[int]) -> int:
    indice_pico = int(np.argmax(lista_clusters))
    clusters_pico = lista_clusters[indice_pico]
    
    if clusters_pico == 0:
        return 8 
        
    caidas = []
    for i in range(indice_pico, len(lista_clusters) - 1):
        caida = lista_clusters[i] - lista_clusters[i + 1]
        caidas.append(caida)
        
    if not caidas:
        return lista_eps[indice_pico]
        
    caida_maxima = max(caidas)
    umbral_relativo = max(2, clusters_pico * 0.10)
    umbral_avalancha = max(3, caida_maxima * 0.35)
    
    indice_ideal = indice_pico
    caida_detectada = 0
    
    for i, caida in enumerate(caidas):
        if caida < 3:
            continue
            
        if caida >= umbral_relativo or caida >= umbral_avalancha:
            indice_ideal = indice_pico + i
            caida_detectada = caida
            break
    else:
        indice_ideal = indice_pico + int(np.argmax(caidas))
        caida_detectada = caida_maxima

    eps_final = lista_eps[indice_ideal]
    Eventos.analisis_codo_robusto(clusters_pico, lista_eps[indice_pico], eps_final, caida_detectada)
    return eps_final

def _proyectar_tsne(matriz_distancia_tsne: np.ndarray, perplejidad: int) -> np.ndarray:
    modelo_tsne = TSNE(
        n_components=3,
        metric='precomputed',
        random_state=42,
        perplexity=perplejidad,
        early_exaggeration=12,
        init='random'
    )
    return modelo_tsne.fit_transform(matriz_distancia_tsne)

def _optimizar_perplejidad(matriz_distancia_tsne: np.ndarray, etiquetas_optimas: np.ndarray) -> Tuple[int, np.ndarray]:
    """
    Realiza una búsqueda adaptativa y agnóstica en múltiples fases para encontrar la perplejidad 
    que maximiza el coeficiente de silueta de los clústeres definidos por el EPS óptimo.
    """
    mascara_validos = etiquetas_optimas != -1
    etiquetas_validas = etiquetas_optimas[mascara_validos]
    
    if len(set(etiquetas_validas)) < 2:
        registrador.info("No hay suficientes clústeres válidos para evaluar la silueta. Usando perplejidad heurística.")
        perplejidad_defecto = min(30, PERPLEJIDAD_MAXIMA)
        return perplejidad_defecto, _proyectar_tsne(matriz_distancia_tsne, perplejidad_defecto)

    registrador.info("--- Iniciando optimización adaptativa de Perplejidad t-SNE ---")

    cache_resultados = {}
    
    mejor_score_global = -1.0
    mejor_perp_global = PERPLEJIDAD_MINIMA

    rango_min = PERPLEJIDAD_MINIMA
    rango_max = PERPLEJIDAD_MAXIMA

    paso = max(1, (rango_max - rango_min) // 5)
    fase = 1
    
    while True:
        perplejidades_fase = list(range(rango_min, rango_max + 1, paso))
        if perplejidades_fase[-1] != rango_max:
            perplejidades_fase.append(rango_max)

        perplejidades_a_evaluar = [p for p in perplejidades_fase if p not in cache_resultados]
        
        for perp in perplejidades_a_evaluar:
            coords = _proyectar_tsne(matriz_distancia_tsne, perp)
            coords_validas = coords[mascara_validos]
            score = silhouette_score(coords_validas, etiquetas_validas)
            
            cache_resultados[perp] = (score, coords)
            Eventos.busqueda_perplejidad(f"Fase {fase}|Paso {paso}", perp, score)
            
            if score > mejor_score_global:
                mejor_score_global = score
                mejor_perp_global = perp

        if paso == 1:
            break

        rango_min = max(PERPLEJIDAD_MINIMA, mejor_perp_global - paso)
        rango_max = min(PERPLEJIDAD_MAXIMA, mejor_perp_global + paso)

        paso = max(1, paso // 2)
        fase += 1

    mejor_coords = cache_resultados[mejor_perp_global][1]
    Eventos.perplejidad_optima_encontrada(mejor_perp_global)
    
    return mejor_perp_global, mejor_coords

def _ejecutar_pipeline_analisis(hashes: List[int], muestras_minimas: int) -> Tuple[Optional[np.ndarray], Dict[int, np.ndarray], int, int, Optional[np.ndarray], int]:
    if len(hashes) < 3:
        return None, {}, 0, 0, None, 0

    matriz_similitud = _calcular_matriz_similitud(hashes)
    matriz_distancia_tsne = 1 - matriz_similitud
    matriz_distancia_original = _calcular_matriz_distancia(hashes)
    
    historial_etiquetas = {}
    lista_clusters = []
    lista_eps = []
    
    # 1. Ejecutar DBSCAN y encontrar el EPS Óptimo
    for eps in range(1, CLUSTER_EPS_MAXIMO + 1):
        modelo = DBSCAN(metric='precomputed', eps=eps, min_samples=muestras_minimas)
        etiquetas = modelo.fit_predict(matriz_distancia_original)
        cantidad_clusters = len(set(etiquetas)) - (1 if -1 in etiquetas else 0)
        
        historial_etiquetas[eps] = etiquetas
        lista_clusters.append(cantidad_clusters)
        lista_eps.append(eps)
        
        if cantidad_clusters <= 1 and eps > 15:
            break
            
    eps_optimo = _determinar_eps_optimo(lista_clusters, lista_eps)
    eps_maximo = lista_eps[-1]
    
    # 2. Encontrar la Perplejidad Óptima alineada a los clústeres del EPS Óptimo
    etiquetas_optimas = historial_etiquetas[eps_optimo]
    perplejidad_optima, coordenadas = _optimizar_perplejidad(matriz_distancia_tsne, etiquetas_optimas)
    
    return coordenadas, historial_etiquetas, eps_optimo, eps_maximo, matriz_distancia_tsne, perplejidad_optima

def _asignar_colores_clusters(etiquetas: np.ndarray) -> List[str]:
    colores = []
    for etiqueta in etiquetas:
        if etiqueta == -1:
            colores.append('gray')
        else:
            rojo = (etiqueta * 37) % 256
            verde = (etiqueta * 73) % 256
            azul = (etiqueta * 127) % 256
            colores.append(f'rgb({rojo}, {verde}, {azul})')
    return colores

def _construir_grafico_dispersion(coordenadas: np.ndarray, colores: List[str], etiquetas: np.ndarray, nombres: List[str], perplejidad: int, eps: int) -> go.Figure:
    textos_informacion = [f"ID: {i}<br>{nombres[i]}<br>Cluster: {etiquetas[i]}" for i in range(len(nombres))]
    indices_identificadores = list(range(len(nombres)))

    traza_puntos = go.Scatter3d(
        x=coordenadas[:, 0],
        y=coordenadas[:, 1],
        z=coordenadas[:, 2],
        mode='markers',
        marker=dict(size=6, color=colores, opacity=0.8),
        text=textos_informacion,
        hoverinfo='text',
        customdata=indices_identificadores
    )

    traza_resaltada = go.Scatter3d(
        x=[coordenadas[0, 0]], 
        y=[coordenadas[0, 1]], 
        z=[coordenadas[0, 2]],
        mode='markers',
        marker=dict(
            size=12, 
            color='rgba(0,0,0,0)',
            symbol='circle-open', 
            line=dict(color='rgba(0,0,0,0)', width=4)
        ),
        hoverinfo='skip',
        showlegend=False
    )

    figura = go.Figure(data=[traza_puntos, traza_resaltada])

    figura.update_layout(
        title=f"t-SNE 3D (perplejidad={perplejidad}) - {len(nombres)} imágenes | EPS: {eps}",
        scene=dict(
            xaxis_title='D1', 
            yaxis_title='D2', 
            zaxis_title='D3'
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        uirevision='mantener_camara_estatica'
    )
    
    return figura

def _construir_layout_principal(figura_3d: go.Figure, eps_optimo: int, eps_maximo: int, perplejidad_actual: int) -> html.Div:
    cabecera = html.Div(style=EstilosUI.CABECERA, children=[
        html.H1("🧠 Visualizador de Similitud Perceptual", 
                style={'margin': '0', 'color': EstilosUI.COLOR_TEXTO_PRIMARIO, 'fontSize': '24px'}),
        html.P("Explora el espacio latente de imágenes agrupadas por su distancia de Hamming.", 
                style={'margin': '5px 0 0 0', 'color': EstilosUI.COLOR_TEXTO_SECUNDARIO, 'fontSize': '14px'})
    ])

    marcas_slider_eps = {
        i: {'label': str(i), 'style': {'fontWeight': 'bold', 'color': EstilosUI.COLOR_TEXTO_ERROR}} if i == eps_optimo else str(i)
        for i in range(1, eps_maximo + 1) 
        if i % 5 == 0 or i == 1 or i == eps_maximo or i == eps_optimo
    }

    marcas_slider_perp = {
        i: {'label': str(i), 'style': {'fontWeight': 'bold', 'color': EstilosUI.COLOR_TEXTO_ERROR}} if i == perplejidad_actual else str(i)
        for i in range(PERPLEJIDAD_MINIMA, PERPLEJIDAD_MAXIMA + 1) 
        if i % 10 == 0 or i == PERPLEJIDAD_MINIMA or i == PERPLEJIDAD_MAXIMA or i == perplejidad_actual
    }

    panel_controles = html.Div(style=EstilosUI.PANEL_SLIDER, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '10px'}, children=[
            dcc.RadioItems(
                id='modo-seleccion',
                options=[
                    {'label': '🖱️ Seleccionar al hacer Clic', 'value': 'click'},
                    {'label': '👀 Seleccionar al pasar Cursor', 'value': 'hover'}
                ],
                value='click',
                inline=True,
                style={'display': 'flex', 'gap': '15px', 'fontWeight': '500', 'color': EstilosUI.COLOR_TEXTO_PRIMARIO, 'cursor': 'pointer'}
            )
        ]),
        html.Div(style={'display': 'flex', 'gap': '40px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                html.H3("🎚️ Tolerancia de Similitud (EPS)", style={'margin': '0 0 10px 0', 'fontSize': '16px', 'color': EstilosUI.COLOR_TEXTO_PRIMARIO}),
                dcc.Slider(
                    id='slider-eps', min=1, max=eps_maximo, step=1, value=eps_optimo,
                    marks=marcas_slider_eps, tooltip={"placement": "bottom", "always_visible": True},
                    updatemode='drag'
                )
            ]),
            html.Div(style={'flex': '1'}, children=[
                html.H3("🎚️ Perplejidad (t-SNE)", style={'margin': '0 0 10px 0', 'fontSize': '16px', 'color': EstilosUI.COLOR_TEXTO_PRIMARIO}),
                dcc.Slider(
                    id='slider-perplejidad', min=PERPLEJIDAD_MINIMA, max=PERPLEJIDAD_MAXIMA, step=1, value=perplejidad_actual,
                    marks=marcas_slider_perp, tooltip={"placement": "bottom", "always_visible": True},
                    updatemode='mouseup'
                )
            ])
        ])
    ])

    grafico_panel = html.Div(style=EstilosUI.PANEL_IZQUIERDO, children=[
        dcc.Graph(id='grafico-dispersion', figure=figura_3d, style={'flex': '1'}),
        dcc.Store(id='estado-camara')
    ])

    detalles_panel = html.Div(style=EstilosUI.PANEL_DERECHO, children=[
        html.H3("🖼️ Detalles de la Imagen", 
                style={'marginTop': '0', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px', 'color': EstilosUI.COLOR_TEXTO_PRIMARIO}),
        html.Div(id='visor-imagen', style=EstilosUI.CONTENEDOR_IMAGEN_ACTIVA)
    ])

    contenedor_flexible = html.Div(style=EstilosUI.FLEX_CONTENEDOR, children=[grafico_panel, detalles_panel])
    return html.Div(style=EstilosUI.CONTENEDOR_APP, children=[cabecera, panel_controles, contenedor_flexible])

def _generar_componente_error(ruta: str) -> html.Div:
    return html.Div([
        html.P("❌ Imagen no encontrada", style={'fontWeight': 'bold', 'color': EstilosUI.COLOR_TEXTO_ERROR, 'fontSize': '18px'}),
        html.Code(ruta, style={'color': EstilosUI.COLOR_TEXTO_SECUNDARIO, 'fontSize': '12px', 'wordBreak': 'break-all'})
    ])

def _codificar_imagen_base64(ruta: Path) -> str:
    with open(ruta, 'rb') as archivo_imagen:
        datos_codificados = base64.b64encode(archivo_imagen.read()).decode('utf-8')
    
    extension = ruta.suffix.lower()
    tipo_mime = 'image/jpeg' if extension in ['.jpg', '.jpeg'] else 'image/png' if extension == '.png' else 'image/webp'
    return f"data:{tipo_mime};base64,{datos_codificados}"

def _generar_componente_imagen(nombre: str, ruta: str) -> html.Div:
    try:
        ruta_absoluta = Path(ruta)
        fuente_imagen = _codificar_imagen_base64(ruta_absoluta)

        bloque_texto = html.Div([
            html.Span("Archivo:", style={'fontWeight': 'bold', 'color': EstilosUI.COLOR_TEXTO_SECUNDARIO, 'marginRight': '8px'}),
            html.Span(f"{nombre}", style={'color': EstilosUI.COLOR_TEXTO_PRIMARIO, 'wordBreak': 'break-all', 'fontWeight': '500'})
        ], style=EstilosUI.ETIQUETA_ARCHIVO)

        bloque_imagen = html.Img(src=fuente_imagen, style=EstilosUI.IMAGEN_MOSTRADA)

        return html.Div(
            children=[bloque_texto, bloque_imagen], 
            style={'width': '100%', 'height': '100%', 'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center', 'justifyContent': 'flex-start'}
        )
        
    except Exception as error:
        Eventos.error_carga_imagen(ruta, str(error))
        return html.P(f"⚠️ Error al cargar: {str(error)}", style={'color': EstilosUI.COLOR_TEXTO_ERROR})

class VisualizadorApp:
    def __init__(self, ruta_db: Path, limite: int):
        self.ruta_db = ruta_db
        self.limite = limite
        self.perplejidad = 0 # Se asignará dinámicamente
        self.nombres_archivos: List[str] = []
        self.rutas_archivos: List[str] = []
        self.historial_etiquetas: Dict[int, np.ndarray] = {}
        self.coordenadas: Optional[np.ndarray] = None
        self.matriz_distancia_tsne: Optional[np.ndarray] = None
        self.aplicacion_dash = dash.Dash(__name__)
        self._inicializar_aplicacion()

    def _inicializar_aplicacion(self) -> None:
        ids, self.nombres_archivos, hashes, self.rutas_archivos = _cargar_datos(self.ruta_db, self.limite)

        self.coordenadas, self.historial_etiquetas, eps_optimo, eps_maximo, self.matriz_distancia_tsne, self.perplejidad = _ejecutar_pipeline_analisis(
            hashes, CLUSTER_MUESTRAS_MINIMAS
        )

        if self.coordenadas is None:
            Eventos.sin_datos_suficientes()
            return

        etiquetas_optimas = self.historial_etiquetas[eps_optimo]
        colores_optimos = _asignar_colores_clusters(etiquetas_optimas)
        
        figura_3d = _construir_grafico_dispersion(
            self.coordenadas, colores_optimos, etiquetas_optimas, self.nombres_archivos, self.perplejidad, eps_optimo
        )

        self.aplicacion_dash.layout = _construir_layout_principal(figura_3d, eps_optimo, eps_maximo, self.perplejidad)

        self.aplicacion_dash.clientside_callback(
            """
            function(relayoutData) {
                if (relayoutData && relayoutData['scene.camera']) {
                    return relayoutData['scene.camera'];
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output('estado-camara', 'data'),
            Input('grafico-dispersion', 'relayoutData'),
        )

        self.aplicacion_dash.callback(
            Output('grafico-dispersion', 'figure'),
            Input('slider-eps', 'value'),
            Input('slider-perplejidad', 'value'),
            State('estado-camara', 'data'),
            prevent_initial_call=True
        )(self._procesar_cambio_parametros)

        self.aplicacion_dash.callback(
            Output('visor-imagen', 'children'),
            Output('grafico-dispersion', 'figure', allow_duplicate=True),
            Input('grafico-dispersion', 'clickData'),
            Input('grafico-dispersion', 'hoverData'),
            Input('modo-seleccion', 'value'),
            State('estado-camara', 'data'),
            prevent_initial_call=True
        )(self._procesar_interaccion_grafico)

    def _procesar_cambio_parametros(self, eps_seleccionado: int, perplejidad_seleccionada: int, camara_guardada: Optional[Dict]) -> dash.Patch:
        contexto = dash.callback_context
        propiedad_disparadora = contexto.triggered[0]['prop_id']

        grafico_parcheado = dash.Patch()

        if 'slider-perplejidad' in propiedad_disparadora:
            self.perplejidad = perplejidad_seleccionada
            self.coordenadas = _proyectar_tsne(self.matriz_distancia_tsne, self.perplejidad)

            grafico_parcheado['data'][0]['x'] = self.coordenadas[:, 0]
            grafico_parcheado['data'][0]['y'] = self.coordenadas[:, 1]
            grafico_parcheado['data'][0]['z'] = self.coordenadas[:, 2]

            grafico_parcheado['data'][1]['x'] = [self.coordenadas[0, 0]]
            grafico_parcheado['data'][1]['y'] = [self.coordenadas[0, 1]]
            grafico_parcheado['data'][1]['z'] = [self.coordenadas[0, 2]]

        etiquetas = self.historial_etiquetas[eps_seleccionado]
        colores = _asignar_colores_clusters(etiquetas)
        textos_informacion = [f"ID: {i}<br>{self.nombres_archivos[i]}<br>Cluster: {etiquetas[i]}" for i in range(len(self.nombres_archivos))]

        grafico_parcheado['data'][0]['marker']['color'] = colores
        grafico_parcheado['data'][0]['text'] = textos_informacion
        grafico_parcheado['layout']['title']['text'] = f"t-SNE 3D (perplejidad={self.perplejidad}) - {len(self.nombres_archivos)} imágenes | EPS: {eps_seleccionado}"
        grafico_parcheado['layout']['uirevision'] = 'mantener_camara_estatica'

        if camara_guardada:
            grafico_parcheado['layout']['scene']['camera'] = camara_guardada

        return grafico_parcheado

    def _procesar_interaccion_grafico(self, datos_click: Optional[Dict], datos_hover: Optional[Dict], modo: str, camara_guardada: Optional[Dict]) -> Tuple[Any, Any]:
        contexto = dash.callback_context
        if not contexto.triggered:
            return dash.no_update, dash.no_update

        propiedad_disparadora = contexto.triggered[0]['prop_id']

        if 'modo-seleccion' in propiedad_disparadora:
            return dash.no_update, dash.no_update

        datos_activos = None
        if modo == 'click' and 'clickData' in propiedad_disparadora:
            datos_activos = datos_click
        elif modo == 'hover' and 'hoverData' in propiedad_disparadora:
            datos_activos = datos_hover

        if not datos_activos or not datos_activos.get('points'):
            return dash.no_update, dash.no_update

        punto_seleccionado = datos_activos['points'][0]
        
        if 'customdata' not in punto_seleccionado:
            return dash.no_update, dash.no_update

        indice_seleccionado = punto_seleccionado['customdata']
        nombre_objetivo = self.nombres_archivos[indice_seleccionado]
        ruta_objetivo = self.rutas_archivos[indice_seleccionado]

        if not Path(ruta_objetivo).exists():
            Eventos.imagen_no_encontrada(ruta_objetivo)
            componente_imagen = _generar_componente_error(ruta_objetivo)
        else:
            componente_imagen = _generar_componente_imagen(nombre_objetivo, ruta_objetivo)

        grafico_parcheado = dash.Patch()
        grafico_parcheado['data'][1]['x'] = [self.coordenadas[indice_seleccionado, 0]]
        grafico_parcheado['data'][1]['y'] = [self.coordenadas[indice_seleccionado, 1]]
        grafico_parcheado['data'][1]['z'] = [self.coordenadas[indice_seleccionado, 2]]
        grafico_parcheado['data'][1]['marker']['color'] = 'black'
        grafico_parcheado['data'][1]['marker']['line']['color'] = 'black'
        grafico_parcheado['layout']['uirevision'] = 'mantener_camara_estatica'

        if camara_guardada:
            grafico_parcheado['layout']['scene']['camera'] = camara_guardada

        return componente_imagen, grafico_parcheado

    def ejecutar_servidor(self, puerto: int) -> None:
        Eventos.inicio_servidor(puerto)
        self.aplicacion_dash.run(debug=True, port=puerto)


if __name__ == '__main__':
    try:
        app_visualizador = VisualizadorApp(RUTA_BASE_DATOS, LIMITE_MUESTRA)
        app_visualizador.ejecutar_servidor(PUERTO_SERVIDOR)
    except Exception as e:
        Eventos.error_general(str(e))