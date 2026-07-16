import sqlite3
import logging
import io
import urllib.parse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import flask
import cv2
import numpy as np
from PIL import Image

DIRECTORIO_SCRIPT = Path(__file__).resolve().parent
RUTA_BASE_DATOS_CLUSTERS = DIRECTORIO_SCRIPT / ".." / ".media" / "data" / "imagenes_cluster_orb_re.db"
PUERTO_SERVIDOR = 8051

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
        registrador.info(f"Visualizador interactivo de Clusters iniciado en http://127.0.0.1:{puerto}")

    @staticmethod
    def db_no_encontrada(ruta: str) -> None:
        registrador.error(f"La base de datos de clusters no existe en la ruta: {ruta}")

    @staticmethod
    def error_miniatura(ruta: str, detalle: str) -> None:
        registrador.warning(f"No se pudo generar miniatura para ({ruta}): {detalle}")

class Consultas:
    OBTENER_TODOS_LOS_REGISTROS = """
        SELECT nombre_archivo, ruta_completa, cluster_id, phash, es_representativa, metodo_agrupacion 
        FROM imagenes_cluster_orb_re
    """

class GestorBaseDatos:
    @staticmethod
    def extraer_registros(ruta_db: Path) -> List[Tuple[str, str, int, int, int, str]]:
        if not ruta_db.exists():
            Eventos.db_no_encontrada(str(ruta_db))
            return []
        
        with sqlite3.connect(str(ruta_db)) as conexion:
            cursor = conexion.cursor()
            cursor.execute(Consultas.OBTENER_TODOS_LOS_REGISTROS)
            resultados = []
            for nombre, ruta, cluster_id, phash_bytes, es_rep, metodo in cursor.fetchall():
                phash_int = int.from_bytes(phash_bytes, 'big') if phash_bytes else 0
                resultados.append((nombre, ruta, cluster_id, phash_int, es_rep, metodo))
            return resultados

def _agrupar_por_cluster(registros: List[Tuple[str, str, int, int, int, str]]) -> Tuple[Dict[int, List[Tuple[str, str, int, str, int]]], List[Tuple[str, str, int, str]]]:
    clusters_validos = {}
    ruido = []
    for nombre, ruta, cluster_id, phash_int, es_rep, metodo in registros:
        if cluster_id == -1:
            ruido.append((nombre, ruta, phash_int, metodo))
        else:
            if cluster_id not in clusters_validos:
                clusters_validos[cluster_id] = []
            clusters_validos[cluster_id].append((nombre, ruta, phash_int, metodo, es_rep))
    return clusters_validos, ruido

def _calcular_phash_promedio(hashes: List[int]) -> int:
    if not hashes:
        return 0
    conteo_bits = [0] * 64
    for h in hashes:
        for i in range(64):
            if (h >> i) & 1:
                conteo_bits[i] += 1
                
    umbral = len(hashes) / 2.0
    promedio = 0
    for i in range(64):
        if conteo_bits[i] >= umbral:
            promedio |= (1 << i)
    return promedio

def _calcular_buenos_matches(desc1_blob: bytes, desc2_blob: bytes, matcher: cv2.BFMatcher) -> int:
    if not desc1_blob or not desc2_blob:
        return 0
    desc1 = np.frombuffer(desc1_blob, dtype=np.uint8).reshape(-1, 32)
    desc2 = np.frombuffer(desc2_blob, dtype=np.uint8).reshape(-1, 32)
    if len(desc1) < 2 or len(desc2) < 2:
        return 0
    try:
        matches = matcher.knnMatch(desc1, desc2, k=2)
        buenos = 0
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < 0.75 * n.distance:
                    buenos += 1
        return buenos
    except Exception:
        return 0

def _generar_script_js() -> str:
    return """
        // Lógica mejorada de Tooltip Flotante (Permite copiar contenido)
        const tooltip = document.getElementById('tooltip');
        let tooltipTimeout;

        document.querySelectorAll('.icono-info').forEach(icon => {
            icon.addEventListener('mouseenter', (e) => {
                clearTimeout(tooltipTimeout);
                tooltip.innerHTML = icon.dataset.info;
                const rect = icon.getBoundingClientRect();
                tooltip.style.left = (e.pageX + 15) + 'px';
                tooltip.style.top = (e.pageY + 15) + 'px';
                tooltip.style.opacity = '1';
                tooltip.style.visibility = 'visible';
            });
            
            icon.addEventListener('mousemove', (e) => {
                // Solo se mueve si no estamos tratando de copiar texto
                if(tooltip.style.opacity === '1') return;
                tooltip.style.left = (e.pageX + 15) + 'px';
                tooltip.style.top = (e.pageY + 15) + 'px';
            });

            icon.addEventListener('mouseleave', () => {
                tooltipTimeout = setTimeout(() => {
                    tooltip.style.opacity = '0';
                    tooltip.style.visibility = 'hidden';
                }, 300); // 300ms de ventana para mover el mouse al tooltip
            });
        });

        // Mantener tooltip abierto si el mouse está encima
        tooltip.addEventListener('mouseenter', () => {
            clearTimeout(tooltipTimeout);
        });

        tooltip.addEventListener('mouseleave', () => {
            tooltipTimeout = setTimeout(() => {
                tooltip.style.opacity = '0';
                tooltip.style.visibility = 'hidden';
            }, 300);
        });

        // Lógica de Modal (Lightbox Detallado)
        const modal = document.getElementById('modal-overlay');
        const modalImg = document.getElementById('modal-img');
        const modalDetalles = document.getElementById('modal-lista-detalles');
        const modalCerrar = document.getElementById('modal-cerrar');

        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('miniatura')) {
                const contenedor = e.target.closest('.contenedor-miniatura');
                if (!contenedor) return;
                
                const data = contenedor.dataset;
                
                // Cargar imagen en alta resolución
                modalImg.src = '/api/imagen?ruta=' + encodeURIComponent(data.ruta);
                
                // Construir panel de detalles
                modalDetalles.innerHTML = `
                    <li><strong>Nombre de Archivo</strong> ${data.nombre}</li>
                    <li><strong>ID de Clúster</strong> <span style="color:#3b82f6; font-weight:bold;">${data.cluster === '-1' ? 'Aislada (Ruido)' : data.cluster}</span></li>
                    <li><strong>Método de Agrupación</strong> ${data.metodo}</li>
                    <li><strong>¿Es Representativa?</strong> ${data.representativa}</li>
                    <li><strong>pHash (Decimal)</strong> ${data.phash}</li>
                    <li><strong>Ruta Completa</strong> ${data.ruta}</li>
                `;
                
                modal.classList.add('activo');
            }
        });

        // Cerrar modal
        modalCerrar.addEventListener('click', () => {
            modal.classList.remove('activo');
            modalImg.src = '';
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal || e.target.classList.contains('modal-imagen-contenedor')) {
                modal.classList.remove('activo');
                modalImg.src = '';
            }
        });

        // Filtrado de Clústeres
        document.getElementById('filtro-cluster').addEventListener('change', (e) => {
            const filtro = e.target.value;
            document.querySelectorAll('.drag-cluster').forEach(el => {
                if (filtro === 'todos') {
                    el.style.display = 'block';
                } else {
                    el.style.display = el.dataset.clusterType === filtro ? 'block' : 'none';
                }
            });
        });

        function calcularDistanciaHamming(hashAstr, hashBstr) {
            let a = BigInt(hashAstr);
            let b = BigInt(hashBstr);
            let xor = a ^ b;
            let dist = 0;
            while(xor > 0n) {
                dist += Number(xor & 1n);
                xor >>= 1n;
            }
            return dist;
        }

        let draggedType = null;
        let draggedHash = null;
        let draggedClusterId = null;
        let draggedNombre = null;

        document.addEventListener('dragstart', (e) => {
            let item = e.target.closest('.drag-cluster, .drag-ruido');
            if (!item) return;
            
            if (item.classList.contains('drag-cluster')) {
                draggedType = 'cluster';
                draggedHash = item.dataset.avgPhash;
                draggedClusterId = item.dataset.clusterId;
            } else {
                draggedType = 'ruido';
                draggedHash = item.dataset.phash;
                draggedNombre = item.dataset.nombre;
            }
            e.dataTransfer.effectAllowed = 'copyMove';
            e.dataTransfer.setData('text/plain', '');
            
            if (draggedType === 'cluster') document.querySelector('.panel-der').classList.add('zona-activa');
            if (draggedType === 'ruido') document.querySelector('.panel-izq').classList.add('zona-activa');
        });

        document.addEventListener('dragend', () => {
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('zona-activa'));
        });

        const panelIzq = document.querySelector('.panel-izq');
        const panelDer = document.querySelector('.panel-der');

        panelDer.addEventListener('dragover', e => {
            if (draggedType === 'cluster') {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            }
        });

        panelDer.addEventListener('drop', async e => {
            e.preventDefault();
            if (draggedType !== 'cluster' || !draggedHash) return;
            
            const metodoOrden = document.getElementById('metodo-orden').value;
            const contenedor = document.getElementById('lista-ruido');
            const items = Array.from(contenedor.querySelectorAll('.drag-ruido'));
            
            if (metodoOrden === 'phash') {
                items.sort((a, b) => {
                    let distA = calcularDistanciaHamming(draggedHash, a.dataset.phash);
                    let distB = calcularDistanciaHamming(draggedHash, b.dataset.phash);
                    return distA - distB;
                });
                contenedor.innerHTML = '';
                items.forEach(item => contenedor.appendChild(item));
            } else {
                panelDer.style.opacity = '0.5';
                const targets = items.map(i => i.dataset.nombre);
                try {
                    const res = await fetch('/api/sort_orb', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({source_type: 'cluster', source_id: draggedClusterId, targets: targets})
                    });
                    const sortedTargets = await res.json();
                    contenedor.innerHTML = '';
                    sortedTargets.forEach(targetId => {
                        const item = items.find(i => i.dataset.nombre === targetId);
                        if (item) contenedor.appendChild(item);
                    });
                } catch (err) { console.error("Error en ordenamiento ORB:", err); }
                panelDer.style.opacity = '1';
            }
        });

        panelIzq.addEventListener('dragover', e => {
            if (draggedType === 'ruido') {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            }
        });

        panelIzq.addEventListener('drop', async e => {
            e.preventDefault();
            if (draggedType !== 'ruido' || !draggedHash) return;
            
            const metodoOrden = document.getElementById('metodo-orden').value;
            const contenedor = document.getElementById('lista-clusteres');
            const allItems = Array.from(contenedor.querySelectorAll('.drag-cluster'));
            
            const visibleItems = allItems.filter(i => i.style.display !== 'none');
            const hiddenItems = allItems.filter(i => i.style.display === 'none');
            
            if (metodoOrden === 'phash') {
                visibleItems.sort((a, b) => {
                    let distA = calcularDistanciaHamming(draggedHash, a.dataset.avgPhash);
                    let distB = calcularDistanciaHamming(draggedHash, b.dataset.avgPhash);
                    return distA - distB;
                });
                contenedor.innerHTML = '';
                visibleItems.forEach(item => contenedor.appendChild(item));
                hiddenItems.forEach(item => contenedor.appendChild(item));
            } else {
                panelIzq.style.opacity = '0.5';
                const targets = visibleItems.map(i => parseInt(i.dataset.clusterId));
                try {
                    const res = await fetch('/api/sort_orb', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({source_type: 'ruido', source_id: draggedNombre, targets: targets})
                    });
                    const sortedTargets = await res.json();
                    contenedor.innerHTML = '';
                    sortedTargets.forEach(targetId => {
                        const item = visibleItems.find(i => parseInt(i.dataset.clusterId) === targetId);
                        if (item) contenedor.appendChild(item);
                    });
                    hiddenItems.forEach(item => contenedor.appendChild(item));
                } catch (err) { console.error("Error en ordenamiento ORB:", err); }
                panelIzq.style.opacity = '1';
            }
        });
    """

def _generar_html(clusters: Dict[int, List[Tuple[str, str, int, str, int]]], ruido: List[Tuple[str, str, int, str]]) -> str:
    css = """
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 20px; height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; overflow: hidden; }
        .cabecera { background-color: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 15px 20px; margin-bottom: 20px; flex-shrink: 0; }
        .contenedor-flex { display: flex; gap: 20px; flex: 1; min-height: 0; overflow: hidden; }
        
        .panel { background-color: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; display: flex; flex-direction: column; overflow-y: auto; transition: background-color 0.3s, opacity 0.3s; }
        .panel-izq { flex: 2; }
        .panel-der { flex: 1; }
        .zona-activa { background-color: #e2e8f0; border: 2px dashed #94a3b8; }
        
        .controles-superiores { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; padding-bottom: 10px; border-bottom: 2px solid #f1f5f9; }
        .grupo-selectores { display: flex; gap: 10px; }
        .control-select { padding: 8px 12px; border-radius: 6px; border: 1px solid #cbd5e1; outline: none; font-family: inherit; font-size: 14px; cursor: pointer; background: white; color: #334155; font-weight: 500; }
        .control-select:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2); }
        
        details { background-color: #ffffff; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e0e6ed; box-shadow: 0 2px 4px rgba(0,0,0,0.02); transition: all 0.3s ease; }
        details[open] { background-color: #f8fafc; border-color: #cbd5e1; }
        summary { display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; cursor: pointer; list-style: none; font-weight: 600; color: #2c3e50; font-size: 16px; user-select: none; position: relative; }
        summary::-webkit-details-marker { display: none; }
        summary:hover { background-color: #f1f5f9; border-radius: 8px; }
        
        .contenedor-previa { display: flex; gap: 8px; align-items: center; }
        .fila-cluster { display: flex; overflow-x: auto; gap: 12px; padding: 15px; border-top: 1px solid #e2e8f0; align-items: center; min-height: 130px; }
        .grilla-ruido { display: flex; flex-wrap: wrap; gap: 10px; align-content: flex-start; }
        
        .contenedor-miniatura { position: relative; display: inline-block; }
        .resumen-cluster { display: flex; align-items: center; gap: 10px; }
        
        .miniatura { width: 120px; height: 120px; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); cursor: grab; flex-shrink: 0; background-color: #ecf0f1; transition: transform 0.2s; display: block; }
        .miniatura:hover { transform: scale(1.05); }
        .miniatura-previa { width: 40px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #cbd5e1; flex-shrink: 0; background-color: #ecf0f1; display: block; }
        
        .icono-info { 
            display: flex; justify-content: center; align-items: center; 
            width: 22px; height: 22px; border-radius: 50%; 
            background-color: #3b82f6; color: white; font-weight: bold; font-size: 14px;
            cursor: pointer; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            transition: background-color 0.2s;
        }
        .icono-info:hover { background-color: #2563eb; }
        .icono-imagen { position: absolute; top: -8px; right: -8px; }
        
        /* Tooltip Flotante Mejorado */
        #tooltip {
            position: absolute; background-color: #1e293b; color: #f8fafc;
            padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 500;
            pointer-events: auto; /* Permite hover en el propio tooltip */
            z-index: 9999; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            opacity: 0; visibility: hidden; transition: opacity 0.2s; white-space: nowrap;
        }
        
        h1 { margin: 0; color: #2c3e50; font-size: 24px; }
        p { margin: 5px 0 0 0; color: #7f8c8d; font-size: 14px; }
        h2 { margin: 0; color: #2c3e50; }

        /* Estilos del Modal (Vista Completa) */
        #modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.9); z-index: 10000; display: flex; justify-content: center; align-items: center; opacity: 0; visibility: hidden; transition: opacity 0.2s ease, visibility 0.2s ease; backdrop-filter: blur(5px); }
        #modal-overlay.activo { opacity: 1; visibility: visible; }
        .modal-contenido { display: flex; background: white; border-radius: 12px; overflow: hidden; width: 90vw; height: 85vh; max-width: 1400px; position: relative; box-shadow: 0 20px 40px rgba(0,0,0,0.4); flex-direction: row; }
        @media (max-width: 768px) { .modal-contenido { flex-direction: column; } }
        
        .modal-imagen-contenedor { flex: 2; background: #000; display: flex; justify-content: center; align-items: center; overflow: hidden; padding: 20px; position: relative;}
        #modal-img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        
        .modal-detalles { flex: 1; background: #f8fafc; padding: 30px; overflow-y: auto; border-left: 1px solid #e2e8f0; min-width: 350px; max-width: 400px; display: flex; flex-direction: column;}
        .modal-detalles h3 { margin-top: 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; color: #1e293b; font-size: 20px;}
        .modal-detalles ul { list-style: none; padding: 0; margin: 0; }
        .modal-detalles li { padding: 14px 0; border-bottom: 1px solid #e2e8f0; font-size: 15px; word-break: break-all; color: #475569;}
        .modal-detalles li strong { color: #334155; display: block; margin-bottom: 5px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;}
        
        #modal-cerrar { position: absolute; top: 15px; right: 25px; font-size: 36px; font-weight: bold; color: #94a3b8; cursor: pointer; z-index: 10; line-height: 1; transition: color 0.2s;}
        #modal-cerrar:hover { color: #0f172a; }
    """
    
    html = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Visor de Clusters</title><style>{css}</style></head><body>"]
    html.append("<div id='tooltip'></div>")
    
    html.append(f"<div class='cabecera'><h1>🗂️ Biblioteca de Clústeres Semánticos</h1>")
    html.append(f"<p>Arrastra un clúster al panel de ruido para ordenar las imágenes aisladas, o viceversa.</p></div>")
    
    html.append("<div class='contenedor-flex'>")
    
    # Panel Izquierdo
    html.append("<div class='panel panel-izq'>")
    
    # Controles Superiores
    html.append("<div class='controles-superiores'>")
    html.append("<h2>Clústeres Consolidados</h2>")
    html.append("<div class='grupo-selectores'>")
    html.append("""
        <select id='filtro-cluster' class='control-select'>
            <option value='todos'>Mostrar Todos</option>
            <option value='phash'>Solo pHash</option>
            <option value='combinado'>Combinados</option>
        </select>
        <select id='metodo-orden' class='control-select'>
            <option value='phash'>Afinamiento por pHash</option>
            <option value='orb'>Afinamiento por ORB</option>
        </select>
    """)
    html.append("</div></div>")
    
    html.append("<div id='lista-clusteres'>")
    for cluster_id in sorted(clusters.keys()):
        imagenes_cluster = clusters[cluster_id]
        
        es_combinado = any(img[3] == 'ORB' for img in imagenes_cluster)
        tipo_cluster = 'combinado' if es_combinado else 'phash'
        
        vista_previa = [(img[0], img[1]) for img in imagenes_cluster if img[4] == 1]
        if not vista_previa: 
            vista_previa = [(img[0], img[1]) for img in imagenes_cluster[:3]]
            
        hashes_cluster = [img[2] for img in imagenes_cluster]
        phash_promedio = _calcular_phash_promedio(hashes_cluster)
        
        html.append(f"<details class='drag-cluster' draggable='true' data-cluster-id='{cluster_id}' data-cluster-type='{tipo_cluster}' data-avg-phash='{phash_promedio}'>")
        html.append("<summary><div class='resumen-cluster'>")
        html.append(f"<div class='icono-info' data-info='Promedio pHash: {phash_promedio}'>!</div>")
        html.append(f"<span>Cluster {cluster_id} — ({len(imagenes_cluster)} imágenes)</span></div>")
        
        html.append("<div class='contenedor-previa'>")
        for nombre, ruta in vista_previa:
            src = f"/api/miniatura?ruta={urllib.parse.quote(ruta)}&size=40"
            html.append(f"<img src='{src}' class='miniatura-previa' loading='lazy' title='{nombre}'>")
        html.append("</div></summary>")
        
        html.append("<div class='fila-cluster'>")
        for nombre, ruta, phash_int, metodo, es_rep in imagenes_cluster:
            es_rep_str = "Sí" if es_rep == 1 else "No"
            src = f"/api/miniatura?ruta={urllib.parse.quote(ruta)}&size=150"
            # Inyección de atributos data-* para el modal
            html.append(f"<div class='contenedor-miniatura' data-nombre='{nombre}' data-ruta='{ruta}' data-cluster='{cluster_id}' data-phash='{phash_int}' data-metodo='{metodo}' data-representativa='{es_rep_str}'>")
            html.append(f"<div class='icono-info icono-imagen' data-info='pHash: {phash_int} | Método: {metodo}'>!</div>")
            html.append(f"<img src='{src}' title='{nombre}' class='miniatura' loading='lazy'>")
            html.append("</div>")
        html.append("</div></details>")
        
    html.append("</div></div>") 
    
    # Panel Derecho
    html.append("<div class='panel panel-der'><h2>Ruido (Aisladas)</h2><div id='lista-ruido' class='grilla-ruido'>")
    for nombre, ruta, phash_int, metodo in ruido:
        src = f"/api/miniatura?ruta={urllib.parse.quote(ruta)}&size=150"
        # Inyección de atributos data-* para el modal
        html.append(f"<div class='contenedor-miniatura drag-ruido' draggable='true' data-nombre='{nombre}' data-ruta='{ruta}' data-cluster='-1' data-phash='{phash_int}' data-metodo='{metodo}' data-representativa='No'>")
        html.append(f"<div class='icono-info icono-imagen' data-info='pHash: {phash_int} | Método: {metodo}'>!</div>")
        html.append(f"<img src='{src}' title='{nombre}' class='miniatura' loading='lazy'>")
        html.append("</div>")
    html.append("</div></div>")
    
    html.append("</div>")
    
    # Bloque HTML del Modal (Lightbox)
    html.append("""
        <div id='modal-overlay'>
            <div class='modal-contenido'>
                <span id='modal-cerrar'>&times;</span>
                <div class='modal-imagen-contenedor'>
                    <img id='modal-img' src=''>
                </div>
                <div class='modal-detalles'>
                    <h3>Detalles de la Imagen</h3>
                    <ul id='modal-lista-detalles'>
                        <!-- Se llena mediante JS -->
                    </ul>
                </div>
            </div>
        </div>
    """)
    
    html.append(f"<script>{_generar_script_js()}</script>")
    html.append("</body></html>")
    
    return "".join(html)

class ClusterAnalyzerApp:
    def __init__(self, ruta_db: Path):
        self.ruta_db = ruta_db
        self.app = flask.Flask(__name__)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self._configurar_rutas()

    def _configurar_rutas(self) -> None:
        @self.app.route('/')
        def indice():
            registros = GestorBaseDatos.extraer_registros(self.ruta_db)
            clusters, ruido = _agrupar_por_cluster(registros)
            return _generar_html(clusters, ruido)

        @self.app.route('/api/miniatura')
        def servir_miniatura():
            ruta_str = flask.request.args.get('ruta')
            tamano_req = flask.request.args.get('size', '150')
            tamano = int(tamano_req) if tamano_req.isdigit() else 150
            
            if not ruta_str:
                return flask.abort(400, "Ruta no proporcionada")
            
            ruta = Path(ruta_str)
            if not ruta.exists():
                return flask.abort(404, "Imagen no encontrada")
                
            try:
                with Image.open(ruta) as img:
                    img.thumbnail((tamano, tamano))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    buffer_memoria = io.BytesIO()
                    img.save(buffer_memoria, format="JPEG", quality=70)
                    buffer_memoria.seek(0)
                    return flask.send_file(buffer_memoria, mimetype='image/jpeg')
            except Exception as error:
                Eventos.error_miniatura(ruta_str, str(error))
                return flask.abort(500, "Error procesando la imagen")

        @self.app.route('/api/imagen')
        def servir_imagen_completa():
            """API auxiliar para servir la imagen original al modal."""
            ruta_str = flask.request.args.get('ruta')
            if not ruta_str:
                return flask.abort(400, "Ruta no proporcionada")
            ruta = Path(ruta_str)
            if not ruta.exists():
                return flask.abort(404, "Imagen no encontrada")
            return flask.send_file(ruta)

        @self.app.route('/api/sort_orb', methods=['POST'])
        def sort_orb():
            """API Asíncrona para ordenar por ORB sin renderizar de nuevo la página"""
            data = flask.request.json
            source_type = data.get('source_type')
            source_id = data.get('source_id')
            targets = data.get('targets', [])
            
            if not targets:
                return flask.jsonify([])
                
            with sqlite3.connect(str(self.ruta_db)) as conn:
                cursor = conn.cursor()
                
                if source_type == 'cluster':
                    cursor.execute("SELECT orb_descriptores FROM imagenes_cluster_orb_re WHERE cluster_id = ? AND es_representativa = 1", (source_id,))
                    camp_blobs = [row[0] for row in cursor.fetchall() if row[0]]
                    
                    placeholders = ','.join('?' for _ in targets)
                    cursor.execute(f"SELECT nombre_archivo, orb_descriptores FROM imagenes_cluster_orb_re WHERE nombre_archivo IN ({placeholders})", targets)
                    target_data = {row[0]: row[1] for row in cursor.fetchall()}
                    
                    scores = {}
                    for target_name in targets:
                        blob = target_data.get(target_name)
                        if not blob or not camp_blobs:
                            scores[target_name] = -1
                            continue
                        
                        max_match = 0
                        for c_blob in camp_blobs:
                            m = _calcular_buenos_matches(blob, c_blob, self.matcher)
                            if m > max_match: max_match = m
                        scores[target_name] = max_match
                        
                    sorted_targets = sorted(targets, key=lambda t: scores.get(t, -1), reverse=True)
                    return flask.jsonify(sorted_targets)
                    
                elif source_type == 'ruido':
                    cursor.execute("SELECT orb_descriptores FROM imagenes_cluster_orb_re WHERE nombre_archivo = ?", (source_id,))
                    row = cursor.fetchone()
                    ruido_blob = row[0] if row else None
                    
                    placeholders = ','.join('?' for _ in targets)
                    cursor.execute(f"SELECT cluster_id, orb_descriptores FROM imagenes_cluster_orb_re WHERE cluster_id IN ({placeholders}) AND es_representativa = 1", targets)
                    
                    camp_por_cluster = {}
                    for c_id, blob in cursor.fetchall():
                        if blob:
                            if c_id not in camp_por_cluster:
                                camp_por_cluster[c_id] = []
                            camp_por_cluster[c_id].append(blob)
                            
                    scores = {}
                    for target_id in targets:
                        blobs = camp_por_cluster.get(target_id, [])
                        if not ruido_blob or not blobs:
                            scores[target_id] = -1
                            continue
                            
                        max_match = 0
                        for c_blob in blobs:
                            m = _calcular_buenos_matches(ruido_blob, c_blob, self.matcher)
                            if m > max_match: max_match = m
                        scores[target_id] = max_match
                        
                    sorted_targets = sorted(targets, key=lambda t: scores.get(t, -1), reverse=True)
                    return flask.jsonify(sorted_targets)

    def ejecutar_servidor(self, puerto: int) -> None:
        Eventos.inicio_servidor(puerto)
        self.app.run(debug=True, port=puerto, threaded=True)

if __name__ == '__main__':
    app_visualizador = ClusterAnalyzerApp(RUTA_BASE_DATOS_CLUSTERS)
    app_visualizador.ejecutar_servidor(PUERTO_SERVIDOR)