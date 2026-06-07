"""
DEV_MediaAnalyzer - Interfaz Gráfica
Requiere: pip install Pillow imagehash opencv-python (cv2 es opcional)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import io
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ── Importar los scripts del proyecto ───────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from img_vid_merge import separar_multimedia, unir_multimedia
    from img_sim_cluster import agrupar_similares, desagrupar_similares
    SCRIPTS_OK = True
except ImportError as e:
    SCRIPTS_OK = False
    IMPORT_ERROR = str(e)

# ── Paleta de colores ────────────────────────────────────────────────────────
BG      = "#16161e"   # fondo principal
BG2     = "#1a1b26"   # paneles laterales
BG3     = "#24283b"   # cards / hover
BG4     = "#2f3347"   # elementos interactivos
BORDER  = "#3b3f5c"
ACCENT  = "#7aa2f7"   # azul Tokyo Night
ACCENT2 = "#bb9af7"   # violeta
GREEN   = "#9ece6a"
RED     = "#f7768e"
YELLOW  = "#e0af68"
TEXT    = "#c0caf5"
TEXT2   = "#565f89"
TEXT3   = "#a9b1d6"

THUMB_W, THUMB_H = 140, 105

EXTS_FOTOS  = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.raw'}
EXTS_VIDEOS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
EXTS_MEDIA  = EXTS_FOTOS | EXTS_VIDEOS


# ── Utilidades visuales ──────────────────────────────────────────────────────

def make_placeholder(width, height, text, color):
    """Crea una imagen PIL de placeholder con icono centrado."""
    if not HAS_PIL:
        return None
    img = Image.new("RGBA", (width, height), color + "22")
    draw = ImageDraw.Draw(img)
    # borde redondeado simulado
    draw.rectangle([0, 0, width-1, height-1], outline=color + "66", width=1)
    # texto centrado
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2), text, fill=color, font=font)
    return img


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  ÁRBOL DE CARPETAS                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class FolderTree(tk.Frame):
    def __init__(self, parent, on_select, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self.on_select = on_select
        self._path_map = {}
        self._build()

    def _build(self):
        style = ttk.Style()
        style.configure("Tree.Treeview",
                        background=BG2, foreground=TEXT3,
                        fieldbackground=BG2, borderwidth=0,
                        rowheight=26, font=("Consolas", 9))
        style.configure("Tree.Treeview.Heading", background=BG3, foreground=TEXT2)
        style.map("Tree.Treeview",
                  background=[("selected", BG4)],
                  foreground=[("selected", ACCENT)])
        style.layout("Tree.Treeview", [("Tree.Treeview.treearea", {"sticky": "nswe"})])

        vbar = tk.Scrollbar(self, orient="vertical", bg=BG3,
                            troughcolor=BG2, relief="flat", width=8)
        hbar = tk.Scrollbar(self, orient="horizontal", bg=BG3,
                            troughcolor=BG2, relief="flat", width=8)
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")

        self.tv = ttk.Treeview(self, style="Tree.Treeview",
                               yscrollcommand=vbar.set,
                               xscrollcommand=hbar.set,
                               selectmode="browse", show="tree")
        self.tv.pack(fill="both", expand=True)
        vbar.config(command=self.tv.yview)
        hbar.config(command=self.tv.xview)

        self.tv.bind("<<TreeviewSelect>>", self._on_select)
        self.tv.bind("<<TreeviewOpen>>",   self._on_open)

    def load(self, root_path):
        self.tv.delete(*self.tv.get_children())
        self._path_map.clear()
        p = Path(root_path)
        root_id = self.tv.insert("", "end", text=f"  📁  {p.name}", open=True)
        self._path_map[root_id] = str(p)
        self._populate(root_id, p)

    def _populate(self, parent_id, path):
        try:
            dirs = sorted(
                [d for d in Path(path).iterdir()
                 if d.is_dir() and not d.name.startswith(".")],
                key=lambda x: x.name.lower()
            )
            for d in dirs:
                nid = self.tv.insert(parent_id, "end", text=f"  📁  {d.name}")
                self._path_map[nid] = str(d)
                # dummy child si tiene subcarpetas
                has_sub = any(x.is_dir() for x in d.iterdir()
                              if not x.name.startswith("."))
                if has_sub:
                    dummy = self.tv.insert(nid, "end", text="__dummy__")
                    self._path_map[dummy] = "__dummy__"
        except PermissionError:
            pass

    def _on_open(self, _event):
        nid = self.tv.focus()
        children = self.tv.get_children(nid)
        if children and self.tv.item(children[0], "text") == "__dummy__":
            self.tv.delete(children[0])
            path = self._path_map.get(nid)
            if path:
                self._populate(nid, path)

    def _on_select(self, _event):
        nid = self.tv.focus()
        path = self._path_map.get(nid)
        if path and path != "__dummy__" and self.on_select:
            self.on_select(path)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  VISOR DE MINIATURAS                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class ThumbnailViewer(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._refs = []   # evitar GC de PhotoImages
        self._cols = 5
        self._build()

    def _build(self):
        # Barra superior
        bar = tk.Frame(self, bg=BG, pady=6, padx=10)
        bar.pack(fill="x")
        self.title_lbl = tk.Label(bar, text="Selecciona una carpeta en el árbol",
                                  bg=BG, fg=TEXT2, font=("Segoe UI", 10))
        self.title_lbl.pack(side="left")
        self.count_lbl = tk.Label(bar, text="", bg=BG, fg=TEXT2,
                                  font=("Segoe UI", 9))
        self.count_lbl.pack(side="right")

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

        # Canvas scrolleable
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                            bg=BG3, troughcolor=BG, relief="flat", width=8)
        self.canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(
                            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<MouseWheel>",  self._scroll)
        self.canvas.bind("<Button-4>",    lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>",    lambda e: self.canvas.yview_scroll( 1, "units"))

    def _on_resize(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _scroll(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def load(self, folder_path):
        for w in self.inner.winfo_children():
            w.destroy()
        self._refs.clear()

        p = Path(folder_path)
        self.title_lbl.config(text=f"📂  {p.name}", fg=TEXT)

        files = sorted(
            [f for f in p.iterdir() if f.is_file()
             and f.suffix.lower() in EXTS_MEDIA],
            key=lambda x: x.name.lower()
        )

        if not files:
            tk.Label(self.inner, text="Sin archivos multimedia en esta carpeta",
                     bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(pady=60)
            self.count_lbl.config(text="")
            return

        self.count_lbl.config(text=f"{len(files)} archivo{'s' if len(files)!=1 else ''}")

        # Calcular columnas dinámicamente
        self.update_idletasks()
        w = self.canvas.winfo_width()
        cols = max(1, w // (THUMB_W + 16)) if w > 10 else 5

        for i, f in enumerate(files):
            row, col = divmod(i, cols)
            self._make_card(f, row, col)

        # Configurar pesos de columnas para centrado
        for c in range(cols):
            self.inner.columnconfigure(c, weight=1)

    def _make_card(self, path, row, col):
        card = tk.Frame(self.inner, bg=BG3, cursor="hand2",
                        padx=3, pady=3, relief="flat")
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        is_video = path.suffix.lower() in EXTS_VIDEOS

        img_lbl = tk.Label(card, bg=BG3,
                           width=THUMB_W, height=THUMB_H)
        img_lbl.pack()

        # Nombre truncado
        name = path.name
        name_disp = (name[:17] + "…") if len(name) > 18 else name
        name_lbl = tk.Label(card, text=name_disp, bg=BG3, fg=TEXT2,
                            font=("Segoe UI", 8), wraplength=THUMB_W)
        name_lbl.pack(pady=(2, 3))

        # Carga en hilo
        threading.Thread(target=self._load_thumb,
                         args=(path, img_lbl, is_video),
                         daemon=True).start()

        # Eventos
        def _open(e, p=path):  self._open_file(p)
        def _enter(e, c=card): self._hover(c, True)
        def _leave(e, c=card): self._hover(c, False)

        for w in (card, img_lbl, name_lbl):
            w.bind("<Double-Button-1>", _open)
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

    def _hover(self, card, enter):
        color = BG4 if enter else BG3
        card.configure(bg=color)
        for w in card.winfo_children():
            try: w.configure(bg=color)
            except Exception: pass

    def _load_thumb(self, path, label, is_video):
        photo = None
        try:
            if not is_video and HAS_PIL:
                img = Image.open(path).convert("RGBA")
                img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
                # Canvas con fondo oscuro del tamaño exacto
                canvas = Image.new("RGBA", (THUMB_W, THUMB_H), BG3 + "ff")
                ox = (THUMB_W - img.width)  // 2
                oy = (THUMB_H - img.height) // 2
                canvas.paste(img, (ox, oy), img if img.mode == "RGBA" else None)
                photo = ImageTk.PhotoImage(canvas)

            elif is_video and HAS_CV2:
                cap = cv2.VideoCapture(str(path))
                ret, frame = cap.read()
                cap.release()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
                    canvas = Image.new("RGB", (THUMB_W, THUMB_H),
                                       tuple(int(BG3.lstrip("#")[i:i+2], 16) for i in (0,2,4)))
                    ox = (THUMB_W - img.width)  // 2
                    oy = (THUMB_H - img.height) // 2
                    canvas.paste(img, (ox, oy))
                    photo = ImageTk.PhotoImage(canvas)

            else:
                icon = "🎬" if is_video else "🖼"
                label.after(0, lambda: label.config(
                    text=icon, font=("Segoe UI", 30),
                    width=10, height=4, fg=ACCENT if is_video else ACCENT2))
                return

        except Exception:
            label.after(0, lambda: label.config(
                text="✗", font=("Segoe UI", 20), fg=RED,
                width=10, height=4))
            return

        if photo:
            self._refs.append(photo)
            label.after(0, lambda ph=photo: label.config(
                image=ph, width=THUMB_W, height=THUMB_H))

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("Error al abrir", str(e))


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  PANEL DE CONTROL                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class ControlPanel(tk.Frame):
    def __init__(self, parent, get_folder_fn, refresh_fn, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self.get_folder = get_folder_fn
        self.refresh    = refresh_fn
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG2, pady=12)
        hdr.pack(fill="x", padx=12)

        tk.Label(hdr, text="Panel de Control", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self._folder_lbl = tk.Label(hdr, text="Sin carpeta activa",
                                    bg=BG2, fg=TEXT2,
                                    font=("Segoe UI", 8), wraplength=210,
                                    justify="left")
        self._folder_lbl.pack(anchor="w", pady=(2, 0))

        # Status bar
        self._status = tk.StringVar(value="")
        self._status_lbl = tk.Label(self, textvariable=self._status,
                                    bg=BG2, fg=GREEN,
                                    font=("Segoe UI", 8, "bold"),
                                    wraplength=210, justify="left")
        self._status_lbl.pack(fill="x", padx=12)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", pady=(4, 0))

        # Notebook
        style = ttk.Style()
        style.configure("CP.TNotebook", background=BG2, borderwidth=0)
        style.configure("CP.TNotebook.Tab", background=BG3, foreground=TEXT2,
                        padding=[12, 6], font=("Segoe UI", 9))
        style.map("CP.TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        nb = ttk.Notebook(self, style="CP.TNotebook")
        nb.pack(fill="both", expand=True, pady=8)

        t1 = tk.Frame(nb, bg=BG2)
        nb.add(t1, text="  📂 Multimedia  ")
        self._tab_multimedia(t1)

        t2 = tk.Frame(nb, bg=BG2)
        nb.add(t2, text="  🔍 Similares  ")
        self._tab_similares(t2)

    # ── Tab 1 ───────────────────────────────────────────────────────────────

    def _tab_multimedia(self, p):
        desc = ("Separa los archivos de la carpeta activa en subcarpetas "
                "/Fotos y /Videos según su extensión.")
        self._desc_label(p, desc)

        self._section(p, "Acción")
        self._btn(p, "▶  Separar Multimedia",
                  ACCENT, BG, self._do_separar,
                  "Crea /Fotos y /Videos y mueve los archivos")

        self._section(p, "Reversión")
        self._btn(p, "↩  Unir Multimedia",
                  BG4, TEXT, self._do_unir,
                  "Devuelve todos los archivos a la raíz")

    # ── Tab 2 ───────────────────────────────────────────────────────────────

    def _tab_similares(self, p):
        desc = ("Agrupa imágenes visualmente similares usando hashes "
                "perceptuales (pHash). Cada grupo va a una carpeta propia.")
        self._desc_label(p, desc)

        # Parámetro: umbral
        self._section(p, "Parámetro")
        box = tk.Frame(p, bg=BG3, padx=12, pady=10)
        box.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(box, text="Umbral de diferencia", bg=BG3, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(box,
                 text="0 = idénticas   5-10 = recortes/filtros   >10 = muy permisivo",
                 bg=BG3, fg=TEXT2, font=("Segoe UI", 7),
                 wraplength=195, justify="left").pack(anchor="w", pady=(1, 6))

        slider_row = tk.Frame(box, bg=BG3)
        slider_row.pack(fill="x")

        self.umbral_var = tk.IntVar(value=5)
        val_lbl = tk.Label(slider_row, textvariable=self.umbral_var,
                           bg=BG3, fg=ACCENT, font=("Segoe UI", 16, "bold"),
                           width=3)
        val_lbl.pack(side="right")

        sl = tk.Scale(slider_row, from_=0, to=20, orient="horizontal",
                      variable=self.umbral_var, showvalue=False,
                      bg=BG3, fg=TEXT, highlightthickness=0,
                      troughcolor=BG2, activebackground=ACCENT,
                      length=150, sliderlength=18, width=10)
        sl.pack(side="left", fill="x", expand=True)

        self._section(p, "Acción")
        self._btn(p, "▶  Agrupar Similares",
                  ACCENT2, BG, self._do_agrupar,
                  "Crea carpetas Grupo_Similar_XXX")

        self._section(p, "Reversión")
        self._btn(p, "↩  Desagrupar Similares",
                  BG4, TEXT, self._do_desagrupar,
                  "Devuelve imágenes a la raíz y elimina las carpetas")

    # ── Helpers de UI ───────────────────────────────────────────────────────

    def _desc_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 8), wraplength=215,
                 justify="left").pack(anchor="w", padx=12, pady=(10, 4))

    def _section(self, parent, title):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(f, text=title.upper(), bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(side="left", fill="x",
                                              expand=True, padx=(6, 0))

    def _btn(self, parent, label, bg, fg, cmd, hint=""):
        btn = tk.Button(parent, text=label, bg=bg, fg=fg,
                        activebackground=BG4, activeforeground=TEXT,
                        relief="flat", font=("Segoe UI", 9, "bold"),
                        padx=10, pady=7, cursor="hand2",
                        command=cmd, anchor="w")
        btn.pack(fill="x", padx=12, pady=(3, 0))
        if hint:
            tk.Label(parent, text=hint, bg=BG2, fg=TEXT2,
                     font=("Segoe UI", 7)).pack(anchor="w", padx=14)

    # ── Acciones ────────────────────────────────────────────────────────────

    def update_folder_label(self, path):
        name = Path(path).name if path else "Sin carpeta activa"
        self._folder_lbl.config(text=f"📌 {name}" if path else name)

    def _get_folder_or_warn(self):
        f = self.get_folder()
        if not f:
            messagebox.showwarning("Sin carpeta",
                                   "Selecciona una carpeta en el árbol primero.")
        return f

    def _run(self, fn, *args, success_msg="✅ Completado"):
        if not SCRIPTS_OK:
            messagebox.showerror("Error de importación",
                                 f"No se pudieron cargar los scripts:\n{IMPORT_ERROR}")
            return
        self._set_status("⏳ Procesando…", YELLOW)

        def task():
            try:
                fn(*args)
                self.after(0, lambda: self._set_status(success_msg, GREEN))
                self.after(0, self.refresh)
            except Exception as e:
                self.after(0, lambda: self._set_status(f"❌ Error: {e}", RED))

        threading.Thread(target=task, daemon=True).start()

    def _set_status(self, msg, color=GREEN):
        self._status.set(msg)
        self._status_lbl.config(fg=color)

    def _do_separar(self):
        f = self._get_folder_or_warn()
        if f: self._run(separar_multimedia, f,
                        success_msg="✅ Multimedia separada")

    def _do_unir(self):
        f = self._get_folder_or_warn()
        if f: self._run(unir_multimedia, f,
                        success_msg="✅ Multimedia unida")

    def _do_agrupar(self):
        f = self._get_folder_or_warn()
        if f: self._run(agrupar_similares, f, self.umbral_var.get(),
                        success_msg="✅ Imágenes agrupadas")

    def _do_desagrupar(self):
        f = self._get_folder_or_warn()
        if f: self._run(desagrupar_similares, f,
                        success_msg="✅ Imágenes desagrupadas")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  VENTANA PRINCIPAL                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DEV_MediaAnalyzer")
        self.geometry("1400x820")
        self.minsize(1000, 600)
        self.configure(bg=BG)

        self._active_folder: str | None = None
        self._build()

        if not HAS_PIL:
            messagebox.showwarning(
                "Pillow no encontrado",
                "Instala Pillow para ver miniaturas de imágenes:\n"
                "pip install Pillow")

    # ── Construcción de UI ───────────────────────────────────────────────────

    def _build(self):
        self._build_topbar()

        pane = tk.PanedWindow(self, orient="horizontal",
                              bg=BG, sashwidth=4,
                              sashrelief="flat", sashpad=2,
                              handlesize=0)
        pane.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── Columna izquierda: árbol ────────────────────────────────────────
        left = tk.Frame(pane, bg=BG2, width=220)
        pane.add(left, minsize=160, width=220)

        tk.Label(left, text="ÁRBOL DE CARPETAS", bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 8, "bold"), pady=8).pack(fill="x", padx=12)
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x")

        self.tree = FolderTree(left, on_select=self._on_folder_select)
        self.tree.pack(fill="both", expand=True)

        # ── Columna central: visor ──────────────────────────────────────────
        center = tk.Frame(pane, bg=BG)
        pane.add(center, minsize=400)

        self.viewer = ThumbnailViewer(center)
        self.viewer.pack(fill="both", expand=True)

        # ── Columna derecha: panel de control ──────────────────────────────
        right = tk.Frame(pane, bg=BG2, width=260)
        pane.add(right, minsize=230, width=260)

        self.panel = ControlPanel(right,
                                  get_folder_fn=lambda: self._active_folder,
                                  refresh_fn=self._refresh_viewer)
        self.panel.pack(fill="both", expand=True)

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG2, pady=10, padx=14)
        bar.pack(fill="x")

        # Logo / título
        tk.Label(bar, text="DEV_MediaAnalyzer", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        # Ruta activa
        self._path_var = tk.StringVar(value="Ningún directorio seleccionado")
        tk.Label(bar, textvariable=self._path_var, bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="left", padx=16)

        # Botón
        btn = tk.Button(bar, text="  📂  Abrir directorio  ",
                        command=self._pick_dir,
                        bg=ACCENT, fg=BG, activebackground=ACCENT2,
                        activeforeground=BG, relief="flat",
                        font=("Segoe UI", 9, "bold"),
                        padx=8, pady=4, cursor="hand2")
        btn.pack(side="right")

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _pick_dir(self):
        path = filedialog.askdirectory(title="Seleccionar directorio raíz")
        if path:
            self._active_folder = path
            self._path_var.set(path)
            self.tree.load(path)
            self.panel.update_folder_label(path)

    def _on_folder_select(self, folder_path):
        self._active_folder = folder_path
        self.viewer.load(folder_path)
        self.panel.update_folder_label(folder_path)

    def _refresh_viewer(self):
        if self._active_folder:
            self.viewer.load(self._active_folder)


# ── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()