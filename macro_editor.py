import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import sys
import json
import datetime
import logging

# Get logger for this module
logger = logging.getLogger(__name__)
# Importa le funzioni dal repository macro
from repositories.macro_repository import (
    get_all_macros,
    get_macro_metadata_by_name,
    load_macro_events,
    update_macro_events_only,
    update_macro_full,
)
from core.config_store import (
    DEFAULT_APP_CONFIG,
    get_window_geometry,
    load_app_config,
    load_style_config,
    save_app_config,
    set_window_geometry,
)

# Import opzionale per visualizzazione timeline (matplotlib)
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

class MacroEditorApp:
    def __init__(self, root, macro_name):
        logger.info(f"Inizializzazione MacroEditorApp per macro: {macro_name}")
        self.root = root
        self.macro_name = macro_name
        self.macro_metadata = None # Memorizzerà {id, nome, descrizione, eseguibile, durata_sec}
        self.original_events = []
        self.current_events = []
        self.event_filter_vars = {}
        self.event_filter_button = None
        self.event_filter_menu = None
        self._event_filter_options = {
            "mouse": "Mouse",
            "keyboard": "Keyboard",
        }

        self.root.title(f"Editor Macro: {self.macro_name}")
        self.root.geometry("1200x800") # Dimensione ottimizzata per layout a due colonne
        self.load_window_geometry()  # Ripristina posizione/dimensione se presenti
        
        # Stili allineati alla configurazione principale del progetto
        self.load_theme_config()

        self.root.configure(bg=self.bg_color)
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' o 'alt' o 'default'
        self.style.configure('.', background=self.bg_color, foreground=self.text_color, font=(self.font_family, self.font_size_medium))
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color)
        self.style.configure('TButton', background=self.button_bg_color, foreground=self.button_fg_color, font=(self.font_family, self.font_size_medium, 'bold'), borderwidth=1, relief="solid")
        self.style.map('TButton', 
                       background=[('active', self.button_bg_color)],
                       foreground=[('active', self.button_fg_color)])
        self.style.configure('Treeview', background="#3e4452", foreground=self.text_color, fieldbackground="#3e4452", borderwidth=1, relief="solid")
        self.style.map('Treeview', background=[('selected', '#61afef')]) # Colore selezione
        self.style.configure('Treeview.Heading', background="#3e4452", foreground=self.text_color, font=(self.font_family, self.font_size_medium, 'bold'))
        
        self.style.configure('TEntry', fieldbackground="#3e4452", foreground=self.text_color, borderwidth=1, relief="solid")
        self.style.configure('TScrolledText', background="#3e4452", foreground=self.text_color, borderwidth=1, relief="solid")
        self.style.configure('TCheckbutton', background=self.bg_color, foreground=self.text_color)
        self.style.map('TCheckbutton', background=[('active', self.bg_color)])


        self.load_macro_data()
        self.create_widgets()
        self.populate_events_tree()
        self.update_diff_display() # Inizializza il display delle modifiche
        
        # Binding per salvare configurazione alla chiusura
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_theme_config(self):
        """Carica il tema dell'editor dalla configurazione centralizzata."""
        config = load_app_config()
        style_name = config.get("selected_style", "default")
        style_theme = load_style_config(style_name)
        theme = dict(DEFAULT_APP_CONFIG["theme"])
        theme.update(style_theme)

        self.bg_color = theme["background_color"]
        self.text_color = theme["text_color"]
        self.button_bg_color = theme["button_bg_color"]
        self.button_fg_color = theme["button_fg_color"]
        self.border_color = theme["border_color"]
        self.font_family = theme["font_family"]
        self.font_size_large = theme["font_size_large"]
        self.font_size_medium = theme["font_size_medium"]
        self.font_size_small = theme["font_size_small"]

    def load_macro_data(self):
        logger.info(f"Caricamento dati macro: {self.macro_name}")
        self.macro_metadata = get_macro_metadata_by_name(self.macro_name)
        if self.macro_metadata:
            logger.info(f"Macro trovata, ID: {self.macro_metadata['id']}")
            self.original_events = load_macro_events(self.macro_metadata['id'])
            self.current_events = list(self.original_events) # Lavoriamo su una copia
            logger.info(f"Eventi caricati: {len(self.original_events)} eventi")
        else:
            logger.error(f"Macro '{self.macro_name}' non trovata")
            messagebox.showerror("Errore", f"Macro '{self.macro_name}' non trovata.")
            self.root.destroy()
            sys.exit()

    def create_widgets(self):
        logger.info("Creazione widget dell'interfaccia")
        # Frame principale con due colonne
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        
        # Configurazione layout - default prima di caricare da config
        self.left_column_weight = 3
        self.right_column_weight = 1
        # Carica configurazione layout
        self.load_layout_config()
        logger.info(f"Pesi colonne caricati: left={self.left_column_weight}, right={self.right_column_weight}")
        
        # Configura il grid per tre colonne: sinistra, separatore, destra
        # Usa 'uniform' per mantenere proporzioni stabili tra le colonne
        self.main_frame.grid_columnconfigure(0, weight=self.left_column_weight, uniform="editor_columns")  # Colonna sinistra
        self.main_frame.grid_columnconfigure(1, weight=0)  # Separatore (fisso)
        self.main_frame.grid_columnconfigure(2, weight=self.right_column_weight, uniform="editor_columns")  # Colonna destra
        self.main_frame.grid_rowconfigure(0, weight=1)

        # --- COLONNA SINISTRA (LARGA) ---
        left_column = ttk.Frame(self.main_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        left_column.grid_columnconfigure(0, weight=1)
        left_column.grid_rowconfigure(1, weight=1)  # La tabella eventi si espande

        # --- SEPARATORE RIDIMENSIONABILE ---
        separator = tk.Frame(self.main_frame, width=6, bg=self.border_color, cursor="size_we")
        separator.grid(row=0, column=1, sticky="ns")
        
        # Variabili per il ridimensionamento
        self.separator_x = None
        self.dragging = False
        
        # Binding per il ridimensionamento
        separator.bind("<Button-1>", self.start_resize)
        separator.bind("<B1-Motion>", self.resize_columns)
        separator.bind("<ButtonRelease-1>", self.stop_resize)
        logger.info("Separatore ridimensionabile configurato")

        # Timeline degli eventi (in alto)
        timeline_frame = ttk.LabelFrame(left_column, text="Timeline Eventi", padding="10")
        timeline_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 3), dpi=100)
            self.ax = self.figure.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.figure, master=timeline_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            self.figure = None
            self.ax = None
            self.canvas = None
            ttk.Label(
                timeline_frame,
                text="Per vedere il grafico installa 'matplotlib' (pip install matplotlib)",
            ).pack()

        # Tabella degli eventi (sotto)
        events_frame = ttk.LabelFrame(left_column, text="Eventi Macro", padding="10")
        events_frame.grid(row=1, column=0, sticky="nsew")

        filter_frame = ttk.Frame(events_frame)
        filter_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(filter_frame, text="Filtra tipo evento:").pack(side="left")

        self.event_filter_button = ttk.Menubutton(filter_frame, text="Tutti")
        self.event_filter_button.pack(side="left", padx=(8, 0))

        self.event_filter_menu = tk.Menu(self.event_filter_button, tearoff=False)
        self.event_filter_button["menu"] = self.event_filter_menu

        self.event_filter_vars = {}
        for key, label in self._event_filter_options.items():
            var = tk.BooleanVar(value=True)
            self.event_filter_vars[key] = var
            self.event_filter_menu.add_checkbutton(
                label=label,
                variable=var,
                command=self.on_event_filter_change,
            )

        self.event_filter_menu.add_separator()
        self.event_filter_menu.add_command(
            label="Seleziona Tutti",
            command=lambda: self.set_all_event_filters(True),
        )
        self.event_filter_menu.add_command(
            label="Deseleziona Tutti",
            command=lambda: self.set_all_event_filters(False),
        )
        self.update_event_filter_label()

        self.events_tree = ttk.Treeview(events_frame, columns=("Time", "Type", "Event", "Name", "Button", "X", "Y", "Delta", "Pressed"), show="headings")
        self.events_tree.heading("Time", text="Tempo (ms)")
        self.events_tree.heading("Type", text="Tipo")
        self.events_tree.heading("Event", text="Evento")
        self.events_tree.heading("Name", text="Nome")
        self.events_tree.heading("Button", text="Pulsante")
        self.events_tree.heading("X", text="X Norm.")
        self.events_tree.heading("Y", text="Y Norm.")
        self.events_tree.heading("Delta", text="Delta Scroll")
        self.events_tree.heading("Pressed", text="Premuto")

        # Configura la larghezza delle colonne
        self.events_tree.column("Time", width=80, anchor="center")
        self.events_tree.column("Type", width=70, anchor="center")
        self.events_tree.column("Event", width=80, anchor="center")
        self.events_tree.column("Name", width=100, anchor="center")
        self.events_tree.column("Button", width=70, anchor="center")
        self.events_tree.column("X", width=60, anchor="center")
        self.events_tree.column("Y", width=60, anchor="center")
        self.events_tree.column("Delta", width=80, anchor="center")
        self.events_tree.column("Pressed", width=70, anchor="center")

        self.events_tree.pack(fill="both", expand=True)
        self.events_tree.bind("<Double-1>", self.on_event_double_click)

        # Pulsanti di modifica eventi
        event_buttons_frame = ttk.Frame(events_frame)
        event_buttons_frame.pack(fill="x", pady=5)

        ttk.Button(event_buttons_frame, text="Aggiungi Evento", command=self.add_event).pack(side="left", padx=2)
        ttk.Button(event_buttons_frame, text="Modifica Evento", command=self.edit_selected_event).pack(side="left", padx=2)
        ttk.Button(event_buttons_frame, text="Elimina Evento", command=self.delete_selected_event).pack(side="left", padx=2)
        ttk.Button(event_buttons_frame, text="Sposta Su", command=self.move_event_up).pack(side="left", padx=2)
        ttk.Button(event_buttons_frame, text="Sposta Giù", command=self.move_event_down).pack(side="left", padx=2)
        ttk.Button(event_buttons_frame, text="Re-registra Eventi", command=self.rerecord_events_dialog).pack(side="right", padx=2)

        # --- COLONNA DESTRA (STRETTA) ---
        right_column = ttk.Frame(self.main_frame)
        right_column.grid(row=0, column=2, sticky="nsew", padx=(2, 0))  # Spostato a column=2 per fare spazio al separatore
        right_column.grid_columnconfigure(0, weight=1)

        # Dettagli Macro
        metadata_frame = ttk.LabelFrame(right_column, text="Dettagli Macro", padding="10")
        metadata_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(metadata_frame, text="Nome:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.name_entry = ttk.Entry(metadata_frame)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.name_entry.insert(0, self.macro_metadata['nome'])

        ttk.Label(metadata_frame, text="Descrizione:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.desc_entry = ttk.Entry(metadata_frame)
        self.desc_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.desc_entry.insert(0, self.macro_metadata['descrizione'])
        
        ttk.Label(metadata_frame, text="Durata (sec):").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.duration_entry = ttk.Entry(metadata_frame)
        self.duration_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.duration_entry.insert(0, str(self.macro_metadata['durata_sec']))

        ttk.Label(metadata_frame, text="Eseguibile:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.exe_entry = ttk.Entry(metadata_frame)
        self.exe_entry.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.exe_entry.insert(0, self.macro_metadata['eseguibile'])

        metadata_frame.grid_columnconfigure(1, weight=1)

        # Visualizzazione delle modifiche
        diff_frame = ttk.LabelFrame(right_column, text="Modifiche Pendenti", padding="10")
        diff_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.diff_text = scrolledtext.ScrolledText(diff_frame, wrap="word", height=8, font=(self.font_family, self.font_size_small), bg="#3e4452", fg=self.text_color, insertbackground=self.text_color)
        self.diff_text.pack(fill="both", expand=True)
        self.diff_text.config(state="disabled") # Non modificabile dall'utente

        # Pulsanti Salva/Annulla
        action_buttons_frame = ttk.Frame(right_column)
        action_buttons_frame.pack(fill="x", pady=(0, 10))

        ttk.Button(action_buttons_frame, text="Salva Modifiche", command=self.save_macro).pack(fill="x", pady=2)
        ttk.Button(action_buttons_frame, text="Annulla Modifiche", command=self.reset_changes).pack(fill="x", pady=2)

        # Primo render della timeline
        self.render_timeline()

    def start_resize(self, event):
        """Inizia il ridimensionamento delle colonne."""
        logger.info(f"Start resize: x_root={event.x_root}")
        self.dragging = True
        self.separator_x = event.x_root

    def resize_columns(self, event):
        """Ridimensiona le colonne durante il trascinamento."""
        if not self.dragging:
            logger.debug("Resize chiamato ma non in modalità dragging")
            return
        
        delta_x = event.x_root - self.separator_x
        logger.debug(f"Resize: delta_x={delta_x}, x_root={event.x_root}, separator_x={self.separator_x}")
        
        if abs(delta_x) < 5:  # Ignora movimenti molto piccoli
            logger.debug("Movimento troppo piccolo, ignorato")
            return
        
        # Ottieni le dimensioni attuali della finestra
        window_width = self.root.winfo_width()
        logger.debug(f"Window width: {window_width}")
        if window_width <= 0:
            logger.debug("Window width <= 0, ignorato")
            return
        
        # Calcola le nuove proporzioni usando il main_frame
        left_widgets = self.main_frame.grid_slaves(row=0, column=0)
        right_widgets = self.main_frame.grid_slaves(row=0, column=2)
        
        logger.debug(f"Left widgets: {len(left_widgets)}, Right widgets: {len(right_widgets)}")
        
        if not left_widgets or not right_widgets:
            logger.debug("Widget non trovati")
            return
            
        try:
            left_width = left_widgets[0].winfo_width()
            right_width = right_widgets[0].winfo_width()
            logger.debug(f"Widths: left={left_width}, right={right_width}")
        except (IndexError, AttributeError) as e:
            logger.error(f"Errore nel calcolo width: {e}")
            return
            
        total_width = left_width + right_width
        logger.debug(f"Total width: {total_width}")
        
        if total_width <= 0:
            logger.debug("Total width <= 0, ignorato")
            return
        
        # Calcola la nuova proporzione
        new_left_ratio = (left_width + delta_x) / total_width
        new_right_ratio = 1 - new_left_ratio
        
        logger.debug(f"Ratios prima limiti: left={new_left_ratio:.3f}, right={new_right_ratio:.3f}")
        
        # Limita le proporzioni (min 20%, max 80%)
        new_left_ratio = max(0.2, min(0.8, new_left_ratio))
        new_right_ratio = 1 - new_left_ratio
        
        logger.debug(f"Ratios dopo limiti: left={new_left_ratio:.3f}, right={new_right_ratio:.3f}")
        
        # Aggiorna i pesi del grid del main_frame
        self.left_column_weight = int(new_left_ratio * 100)
        self.right_column_weight = int(new_right_ratio * 100)
        
        logger.info(f"Nuovi pesi: left={self.left_column_weight}, right={self.right_column_weight}")
        
        self.main_frame.grid_columnconfigure(0, weight=self.left_column_weight)
        self.main_frame.grid_columnconfigure(2, weight=self.right_column_weight)
        
        self.separator_x = event.x_root

    def stop_resize(self, event):
        """Termina il ridimensionamento delle colonne."""
        logger.info("Stop resize")
        self.dragging = False
        self.separator_x = None
        # Salva la configurazione del layout
        self.save_layout_config()

    def load_layout_config(self):
        """Carica la configurazione del layout dalla config centralizzata."""
        try:
            config = load_app_config()
            layout_config = config.get('macro_editor_layout', {})
            self.left_column_weight = layout_config.get('left_column_weight', 3)
            self.right_column_weight = layout_config.get('right_column_weight', 1)
            logger.info(f"Configurazione caricata: left={self.left_column_weight}, right={self.right_column_weight}")
        except Exception as e:
            logger.error(f"Errore nel caricamento configurazione layout: {e}")
            self.left_column_weight = 3
            self.right_column_weight = 1

    def load_window_geometry(self):
        """Carica posizione e dimensione della finestra dalla config centralizzata."""
        try:
            window_config = get_window_geometry('macro_editor_window')
            if window_config:
                x = window_config.get('x', 200)
                y = window_config.get('y', 150)
                width = window_config.get('width', 1200)
                height = window_config.get('height', 800)
                geom = f"{width}x{height}+{x}+{y}"
                self.root.geometry(geom)
                logger.info(f"Ripristinata posizione/dimensione macro editor: {geom}")
        except Exception as e:
            logger.warning(f"Nessuna posizione/dimensione salvata per macro editor o errore: {e}")

    def save_window_geometry(self):
        """Salva posizione e dimensione della finestra nella config centralizzata."""
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            set_window_geometry('macro_editor_window', x=x, y=y, width=width, height=height)
            logger.info(f"Salvata posizione/dimensione macro editor: x={x}, y={y}, w={width}, h={height}")
        except Exception as e:
            logger.error(f"Errore nel salvataggio posizione/dimensione macro editor: {e}")

    def save_layout_config(self):
        """Salva la configurazione del layout nella config centralizzata."""
        try:
            config = load_app_config()
            logger.info("Salvataggio configurazione layout editor")
            if 'macro_editor_layout' not in config:
                config['macro_editor_layout'] = {}
            config['macro_editor_layout']['left_column_weight'] = self.left_column_weight
            config['macro_editor_layout']['right_column_weight'] = self.right_column_weight
            logger.info(f"Salvando pesi: left={self.left_column_weight}, right={self.right_column_weight}")
            save_app_config(config)
            logger.info("Configurazione layout salvata con successo")
        except Exception as e:
            logger.error(f"Errore nel salvataggio configurazione layout: {e}")

    def restore_dialog_geometry(self, dialog, config_key):
        """Ripristina la geometria salvata per un dialog dell'editor."""
        try:
            window_config = get_window_geometry(config_key)
            if window_config:
                geom = (
                    f"{window_config.get('width', 440)}x{window_config.get('height', 372)}"
                    f"+{window_config.get('x', 200)}+{window_config.get('y', 150)}"
                )
                dialog.geometry(geom)
                logger.info(f"Ripristinata geometria dialog {config_key}: {geom}")
        except Exception as e:
            logger.warning(f"Nessuna geometria valida per {config_key}: {e}")

    def save_dialog_geometry(self, dialog, config_key):
        """Salva la geometria corrente per un dialog dell'editor."""
        try:
            set_window_geometry(
                config_key,
                x=dialog.winfo_x(),
                y=dialog.winfo_y(),
                width=dialog.winfo_width(),
                height=dialog.winfo_height(),
            )
            logger.info(f"Salvata geometria dialog {config_key}")
        except Exception as e:
            logger.error(f"Errore salvataggio geometria dialog {config_key}: {e}")

    def get_selected_event_types(self):
        """Restituisce l'insieme normalizzato dei tipi evento attualmente filtrati."""
        if not self.event_filter_vars:
            return set()
        selected = {key for key, var in self.event_filter_vars.items() if var.get()}
        return selected

    def update_event_filter_label(self):
        """Aggiorna il testo del menubutton in base alla selezione corrente."""
        if not self.event_filter_button:
            return
        selected_labels = [
            self._event_filter_options[key]
            for key, var in self.event_filter_vars.items()
            if var.get()
        ]
        if not selected_labels:
            text = "Nessun tipo"
        elif len(selected_labels) == len(self._event_filter_options):
            text = "Tutti"
        else:
            text = ", ".join(selected_labels)
        self.event_filter_button.configure(text=text)

    def set_all_event_filters(self, state: bool):
        """Imposta tutti i filtri a True/False e aggiorna la vista."""
        if not self.event_filter_vars:
            return
        for var in self.event_filter_vars.values():
            var.set(state)
        self.update_event_filter_label()
        self.populate_events_tree()

    def on_event_filter_change(self):
        """Richiamato quando l'utente modifica la selezione dei filtri."""
        self.update_event_filter_label()
        self.populate_events_tree()

    def iter_filtered_events(self):
        """Genera le coppie (indice, evento) che superano il filtro attivo."""
        selected_types = self.get_selected_event_types()
        for idx, event in enumerate(self.current_events):
            if self._event_passes_filter(event, selected_types):
                yield idx, event

    def _event_passes_filter(self, event, selected_types=None):
        """Determina se l'evento deve essere mostrato in base ai filtri."""
        if selected_types is None:
            selected_types = self.get_selected_event_types()
        if not selected_types:
            return True
        event_type = (event.get('type') or '').lower()
        if "mouse" in selected_types and "mouse" in event_type:
            return True
        if "keyboard" in selected_types and ("keyboard" in event_type or "key" in event_type):
            return True
        return False

    def on_closing(self):
        """Gestisce la chiusura della finestra salvando la configurazione."""
        logger.info("Chiusura editor macro")
        self.save_layout_config()
        self.save_window_geometry()  # <--- Salva anche posizione/dimensione
        self.root.destroy()


    def populate_events_tree(self):
        logger.debug(f"Popolamento tree con {len(self.current_events)} eventi")
        for iid in self.events_tree.get_children():
            self.events_tree.delete(iid)

        for idx, event in self.iter_filtered_events():
            self.events_tree.insert("", "end", values=(
                event.get('time'),
                event.get('type'),
                event.get('event'),
                event.get('name', ''),
                event.get('button', ''),
                f"{event.get('normalized_x', ''):.4f}" if event.get('normalized_x') is not None else '',
                f"{event.get('normalized_y', ''):.4f}" if event.get('normalized_y') is not None else '',
                event.get('delta', ''),
                "Sì" if event.get('is_pressed') else "No" if event.get('is_pressed') is not None else ''
            ), iid=str(idx))
        self.update_diff_display() # Aggiorna display dopo popolazione
        # Aggiorna la timeline ad ogni ricarica
        self.render_timeline()

    def _categorize_event(self, event):
        """Raggruppa gli eventi per tipologia sintetica per l'asse Y."""
        event_type = (event.get('type') or '').lower()
        event_name = (event.get('event') or '').lower()
        button = (event.get('button') or '').lower()
        delta = event.get('delta')
        is_pressed = event.get('is_pressed')

        if event_type == 'mouse':
            if 'scroll' in event_name or (delta is not None and delta != 0):
                return 'Mouse Scroll'
            if event_name == 'move':
                return 'Mouse Move'
            if ('click' in event_name) or ('down' in event_name) or ('up' in event_name) or (button and event_name in ('press', 'release')):
                if button in ('left', 'right', 'middle'):
                    return f"Mouse Click ({button})"
                return 'Mouse Click'
            return 'Mouse Altro'
        if event_type == 'keyboard' or 'key' in event_type:
            if is_pressed is True or event_name in ('down', 'press'):
                return 'Key Press'
            if is_pressed is False or event_name in ('up', 'release'):
                return 'Key Release'
            return 'Keyboard'
        return f"Altro: {event_type or 'n/d'}"

    def render_timeline(self):
        """Renderizza il grafico della timeline con tempo su X e tipologia su Y."""
        logger.debug("Render timeline")
        if not MATPLOTLIB_AVAILABLE or getattr(self, 'ax', None) is None:
            logger.debug("Matplotlib non disponibile o ax non inizializzato")
            return

        events = [event for _, event in self.iter_filtered_events() if event.get('time') is not None]
        if not events:
            self.ax.clear()
            self.ax.set_title('Nessun evento')
            self.ax.set_xlabel('Tempo (s)')
            self.ax.set_yticks([])
            self.ax.grid(True, axis='x', linestyle='--', alpha=0.3)
            self.figure.tight_layout()
            self.canvas.draw_idle()
            return

        categories = [self._categorize_event(ev) for ev in events]
        unique_categories = list(dict.fromkeys(categories))

        preferred_order = [
            'Mouse Move',
            'Mouse Scroll',
            'Mouse Click (left)',
            'Mouse Click (right)',
            'Mouse Click (middle)',
            'Mouse Click',
            'Key Press',
            'Key Release',
            'Keyboard',
            'Mouse Altro',
        ]
        def sort_key(cat):
            return (preferred_order.index(cat) if cat in preferred_order else 999, cat)
        unique_categories.sort(key=sort_key)

        category_to_y = {cat: idx for idx, cat in enumerate(unique_categories)}

        color_map = {
            'Mouse Move': '#61afef',
            'Mouse Scroll': '#e5c07b',
            'Mouse Click (left)': '#e06c75',
            'Mouse Click (right)': '#be5046',
            'Mouse Click (middle)': '#d19a66',
            'Mouse Click': '#e06c75',
            'Key Press': '#98c379',
            'Key Release': '#56b6c2',
            'Keyboard': '#56b6c2',
            'Mouse Altro': '#c678dd',
        }
        marker_map = {
            'Mouse Move': '.',
            'Mouse Scroll': 'v',
            'Mouse Click (left)': 'o',
            'Mouse Click (right)': 's',
            'Mouse Click (middle)': 'D',
            'Mouse Click': 'o',
            'Key Press': '^',
            'Key Release': '+',
            'Keyboard': '+',
            'Mouse Altro': 'P',
        }

        max_time_ms = max(e.get('time', 0) for e in events)
        duration_ms = max(max_time_ms, int(self.macro_metadata.get('durata_sec', 0)) * 1000)
        x_max_s = max(1.0, duration_ms / 1000.0)

        self.ax.clear()
        for cat in unique_categories:
            cat_y = category_to_y[cat]
            times_ms = [e['time'] for e in events if self._categorize_event(e) == cat]
            if not times_ms:
                continue
            max_points = 2000
            if len(times_ms) > max_points:
                step = max(1, len(times_ms) // max_points)
                times_ms = times_ms[::step]
            times_s = [t / 1000.0 for t in times_ms]
            ys = [cat_y] * len(times_s)
            # Determina se il marker supporta edgecolor
            marker = marker_map.get(cat, 'o')
            color = color_map.get(cat, '#abb2bf')
            
            # Per i marker che sono linee (x, +, |, _), usa solo color senza edgecolors
            if marker in ['x', '+', '|', '_']:
                self.ax.scatter(
                    times_s,
                    ys,
                    s=8 if cat != 'Mouse Move' else 3,
                    alpha=0.8 if cat != 'Mouse Move' else 0.5,
                    marker=marker,
                    color=color,
                )
            else:
                # Per i marker che hanno area (o, s, ^, v, <, >), usa edgecolors
                self.ax.scatter(
                    times_s,
                    ys,
                    s=8 if cat != 'Mouse Move' else 3,
                    alpha=0.8 if cat != 'Mouse Move' else 0.5,
                    marker=marker,
                    color=color,
                    edgecolors='none',
                )

        self.ax.set_yticks(list(category_to_y.values()))
        self.ax.set_yticklabels(list(category_to_y.keys()))
        self.ax.set_xlabel('Tempo (s)')
        self.ax.set_ylim(-1, len(unique_categories))
        self.ax.set_xlim(0, x_max_s)
        self.ax.grid(True, axis='x', linestyle='--', alpha=0.3)
        self.ax.set_title('Eventi nel Tempo')
        self.figure.tight_layout()
        if getattr(self, 'canvas', None):
            self.canvas.draw_idle()

    def add_event(self):
        # Implementa una finestra di dialogo per aggiungere un nuovo evento
        # Per semplicità, qui si aggiunge un evento fittizio
        new_event = {
            "time": self.current_events[-1]['time'] + 100 if self.current_events else 0,
            "type": "mouse",
            "event": "move",
            "x": 0.5, "y": 0.5,
            "normalized_x": 0.5, "normalized_y": 0.5,
            "name": "", "button": "", "delta": 0, "is_pressed": False
        }
        self.current_events.append(new_event)
        self.populate_events_tree() # Ricarica la Treeview

    def edit_selected_event(self):
        selected_item = self.events_tree.selection()
        if not selected_item:
            messagebox.showwarning("Modifica Evento", "Seleziona un evento da modificare.")
            return
        selected_iid = selected_item[0]
        try:
            item_index = int(selected_iid)
        except ValueError:
            logger.error(f"IID selezionato non valido per l'evento: {selected_iid}")
            messagebox.showerror("Errore", "Impossibile identificare l'evento selezionato.")
            return

        if item_index < 0 or item_index >= len(self.current_events):
            logger.error(f"Indice evento fuori range: {item_index}")
            messagebox.showerror("Errore", "L'evento selezionato non è più disponibile.")
            return

        event_to_edit = self.current_events[item_index]

        # Creare una finestra di dialogo per modificare i campi
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title("Modifica Evento")
        edit_dialog.transient(self.root)
        edit_dialog.grab_set()
        
        # Carica posizione/dimensione salvata per questa finestra
        self.restore_dialog_geometry(edit_dialog, 'edit_event_dialog_window')
        
        # Salva posizione/dimensione alla chiusura
        def save_dialog_geometry():
            self.save_dialog_geometry(edit_dialog, 'edit_event_dialog_window')
        
        def on_dialog_close():
            save_dialog_geometry()
            edit_dialog.destroy()
        
        edit_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        fields = [
            ("Time (ms):", "time", int),
            ("Type:", "type", str),
            ("Event:", "event", str),
            ("Name:", "name", str),
            ("Button:", "button", str),
            ("X Norm.:", "normalized_x", float),
            ("Y Norm.:", "normalized_y", float),
            ("Delta Scroll:", "delta", int),
            ("Is Pressed (0/1):", "is_pressed", int) # Sarà convertito a bool dopo
        ]

        entries = {}
        for i, (label_text, key, data_type) in enumerate(fields):
            ttk.Label(edit_dialog, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            entry = ttk.Entry(edit_dialog, width=30)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky="ew")
            
            # Popola con il valore esistente
            current_value = event_to_edit.get(key, '')
            if key == "is_pressed":
                entry.insert(0, "1" if current_value else "0")
            elif key in ["normalized_x", "normalized_y"]:
                if current_value is None:
                    entry.insert(0, "")
                else:
                    entry.insert(0, f"{current_value:.4f}")
            else:
                entry.insert(0, str(current_value))
            entries[key] = entry
        
        def save_changes():
            try:
                for label_text, key, data_type in fields:
                    value = entries[key].get().strip()
                    if value == '' and key not in ['name', 'button', 'delta', 'normalized_x', 'normalized_y', 'is_pressed']:
                         # Se il campo è vuoto e non è un campo che può essere vuoto, alza un errore
                        raise ValueError(f"Il campo '{label_text}' non può essere vuoto.")
                    
                    if value == '' and key in ['name', 'button']:
                        event_to_edit[key] = '' # I campi 'name' e 'button' possono essere stringhe vuote
                    elif value == '' and key in ['delta']:
                        event_to_edit[key] = 0 # Delta può essere 0
                        continue
                    elif value == '' and key in ['normalized_x', 'normalized_y']:
                        # Se x o y sono vuoti, impostali a None o 0.0 a seconda della logica
                        # Attenzione: se il campo è di tipo mouse, non dovrebbe essere None
                        if event_to_edit.get('type') == 'mouse':
                            raise ValueError(f"I campi '{label_text}' non possono essere vuoti per eventi mouse.")
                        event_to_edit[key] = None # Imposta a None se non è un evento mouse
                        continue
                    else:
                        if data_type == int:
                            try:
                                event_to_edit[key] = int(value)
                            except ValueError as exc:
                                raise ValueError(f"Il campo '{label_text}' richiede un numero intero.") from exc
                        elif data_type == float:
                            if value.lower() == 'none':
                                event_to_edit[key] = None
                                continue
                            normalized_value = value.replace(',', '.')
                            try:
                                event_to_edit[key] = float(normalized_value)
                            except ValueError as exc:
                                raise ValueError(
                                    f"Il campo '{label_text}' richiede un numero decimale. Usa il punto come separatore (es. 2.0)."
                                ) from exc
                        elif data_type == str:
                            event_to_edit[key] = value
                
                # Conversione finale per is_pressed
                event_to_edit['is_pressed'] = bool(event_to_edit['is_pressed'])

                # Aggiorna anche i campi x e y (non normalizzati) se normalizzati_x/y cambiano
                # Questo è un placeholder, in un'app reale servirebbe la logica della finestra di gioco
                if 'normalized_x' in event_to_edit and event_to_edit['normalized_x'] is not None:
                    event_to_edit['x'] = event_to_edit['normalized_x']
                if 'normalized_y' in event_to_edit and event_to_edit['normalized_y'] is not None:
                    event_to_edit['y'] = event_to_edit['normalized_y']
                        
                self.populate_events_tree()
                edit_dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Errore di Input", f"Errore nel formato del campo: {e}")
            except Exception as e:
                messagebox.showerror("Errore", f"Si è verificato un errore: {e}")

        ttk.Button(edit_dialog, text="Salva", command=save_changes).grid(row=len(fields), column=0, columnspan=2, pady=10)


    def on_event_double_click(self, event):
        item_id = self.events_tree.identify_row(event.y)
        if not item_id:
            return
        self.events_tree.selection_set(item_id)
        self.edit_selected_event()

    def delete_selected_event(self):
        selected_item = self.events_tree.selection()
        if not selected_item:
            messagebox.showwarning("Elimina Evento", "Seleziona un evento da eliminare.")
            return

        confirm = messagebox.askyesno("Conferma Eliminazione", "Sei sicuro di voler eliminare l'evento selezionato?")
        if confirm:
            selected_iid = selected_item[0]
            try:
                item_index = int(selected_iid)
            except ValueError:
                logger.error(f"IID selezionato non valido per eliminazione: {selected_iid}")
                messagebox.showerror("Errore", "Impossibile identificare l'evento selezionato.")
                return
            if item_index < 0 or item_index >= len(self.current_events):
                logger.error(f"Indice evento fuori range per eliminazione: {item_index}")
                messagebox.showerror("Errore", "L'evento selezionato non è più disponibile.")
                return

            del self.current_events[item_index]
            self.populate_events_tree()

            next_index = min(item_index, len(self.current_events) - 1)
            if next_index >= 0:
                next_iid = str(next_index)
                if self.events_tree.exists(next_iid):
                    self.events_tree.selection_set(next_iid)
                    self.events_tree.focus(next_iid)
                    self.events_tree.see(next_iid)
                elif self.events_tree.get_children():
                    first_child = self.events_tree.get_children()[0]
                    self.events_tree.selection_set(first_child)
                    self.events_tree.focus(first_child)

    def move_event_up(self):
        selected_item = self.events_tree.selection()
        if not selected_item:
            messagebox.showwarning("Sposta Evento", "Seleziona un evento da spostare.")
            return

        selected_iid = selected_item[0]
        try:
            item_index = int(selected_iid)
        except ValueError:
            logger.error(f"IID selezionato non valido per spostamento su: {selected_iid}")
            messagebox.showerror("Errore", "Impossibile identificare l'evento selezionato.")
            return

        if item_index > 0:
            event = self.current_events.pop(item_index)
            self.current_events.insert(item_index - 1, event)
            self.populate_events_tree()
            new_iid = str(item_index - 1)
            if self.events_tree.exists(new_iid):
                self.events_tree.selection_set(new_iid)
                self.events_tree.focus(new_iid)
                self.events_tree.see(new_iid)
            elif self.events_tree.get_children():
                first_child = self.events_tree.get_children()[0]
                self.events_tree.selection_set(first_child)
                self.events_tree.focus(first_child)

    def move_event_down(self):
        selected_item = self.events_tree.selection()
        if not selected_item:
            messagebox.showwarning("Sposta Evento", "Seleziona un evento da spostare.")
            return

        selected_iid = selected_item[0]
        try:
            item_index = int(selected_iid)
        except ValueError:
            logger.error(f"IID selezionato non valido per spostamento giù: {selected_iid}")
            messagebox.showerror("Errore", "Impossibile identificare l'evento selezionato.")
            return

        if item_index < len(self.current_events) - 1:
            event = self.current_events.pop(item_index)
            self.current_events.insert(item_index + 1, event)
            self.populate_events_tree()
            new_iid = str(item_index + 1)
            if self.events_tree.exists(new_iid):
                self.events_tree.selection_set(new_iid)
                self.events_tree.focus(new_iid)
                self.events_tree.see(new_iid)
            elif self.events_tree.get_children():
                last_child = self.events_tree.get_children()[-1]
                self.events_tree.selection_set(last_child)
                self.events_tree.focus(last_child)

    def rerecord_events_dialog(self):
        # Placeholder for re-record functionality. This would open a new dialog
        # and integrate with macro_recorder_fullscreen.
        messagebox.showinfo("Re-registra Eventi", "Questa funzione ti permetterà di re-registrare una sequenza di eventi per la macro selezionata. (Non ancora implementata)")
        # Da implementare:
        # 1. Chiedere durata e forse nome eseguibile
        # 2. Avviare la registrazione con macro_recorder_fullscreen.registra_eventi
        # 3. Al termine, sostituire self.current_events con i nuovi eventi
        # 4. Aggiornare self.duration_entry e self.populate_events_tree()

    def update_diff_display(self):
        # Questa funzione dovrebbe confrontare self.current_events con self.original_events
        # e i metadati correnti con quelli caricati.
        # Per ora, mostriamo solo una semplice indicazione se ci sono modifiche.
        diff_lines = []

        # Confronto metadati
        current_name = self.name_entry.get()
        current_desc = self.desc_entry.get()
        current_duration = self.duration_entry.get()
        current_exe = self.exe_entry.get()

        if current_name != self.macro_metadata['nome']:
            diff_lines.append(f"- Nome: {self.macro_metadata['nome']} -> {current_name}")
        if current_desc != self.macro_metadata['descrizione']:
            diff_lines.append(f"- Descrizione: '{self.macro_metadata['descrizione']}' -> '{current_desc}'")
        if current_duration != str(self.macro_metadata['durata_sec']):
            diff_lines.append(f"- Durata: {self.macro_metadata['durata_sec']}s -> {current_duration}s")
        if current_exe != self.macro_metadata['eseguibile']:
            diff_lines.append(f"- Eseguibile: '{self.macro_metadata['eseguibile']}' -> '{current_exe}'")

        # Confronto eventi (semplice, solo lunghezza)
        if len(self.current_events) != len(self.original_events):
            diff_lines.append(f"- Numero Eventi: {len(self.original_events)} -> {len(self.current_events)}")
        # Per un confronto profondo, bisognerebbe confrontare ogni singolo evento, ma è più complesso
        # e non strettamente necessario per una semplice indicazione all'utente.
        # Si potrebbe fare un confronto JSON delle liste.
        elif json.dumps(self.current_events, sort_keys=True) != json.dumps(self.original_events, sort_keys=True):
             diff_lines.append("- Contenuto Eventi: Modificato")

        self.diff_text.config(state="normal")
        self.diff_text.delete(1.0, tk.END)
        if diff_lines:
            self.diff_text.insert(tk.END, "\n".join(diff_lines))
        else:
            self.diff_text.insert(tk.END, "Nessuna modifica pendente.")
        self.diff_text.config(state="disabled")

        # Ogni volta che qualcosa cambia nella Treeview, aggiorna il diff display
        self.events_tree.bind("<<TreeviewSelect>>", lambda event: self.update_diff_display())
        self.name_entry.bind("<KeyRelease>", lambda event: self.update_diff_display())
        self.desc_entry.bind("<KeyRelease>", lambda event: self.update_diff_display())
        self.duration_entry.bind("<KeyRelease>", lambda event: self.update_diff_display())
        self.exe_entry.bind("<KeyRelease>", lambda event: self.update_diff_display())


    def save_macro(self):
        logger.info("Tentativo di salvataggio macro")
        new_name = self.name_entry.get()
        new_desc = self.desc_entry.get()
        new_duration_str = self.duration_entry.get()
        new_exe = self.exe_entry.get()

        logger.debug(f"Nuovi valori: nome='{new_name}', desc='{new_desc}', durata='{new_duration_str}', exe='{new_exe}'")

        if not new_name:
            logger.warning("Tentativo di salvataggio con nome vuoto")
            messagebox.showwarning("Salvataggio Macro", "Il nome della macro non può essere vuoto.", parent=self.root)
            return
        
        try:
            new_duration = int(new_duration_str)
            if new_duration <= 0:
                raise ValueError("La durata deve essere un numero intero positivo.")
        except ValueError:
            messagebox.showwarning("Salvataggio Macro", "La durata deve essere un numero intero valido.", parent=self.root)
            return
        
        try:
            # Passa save_backup=True per creare un backup prima di sovrascrivere
            update_macro_full(
                self.macro_metadata['id'],
                new_name,
                new_desc,
                new_duration,
                new_exe,
                self.current_events,
                save_backup=True # Assicurati che un backup venga creato
            )
            
            # Aggiorna i dati "originali" dopo il salvataggio riuscito
            self.macro_name = new_name # Importante se il nome è cambiato
            self.macro_metadata['nome'] = new_name
            self.macro_metadata['descrizione'] = new_desc
            self.macro_metadata['durata_sec'] = new_duration
            self.macro_metadata['eseguibile'] = new_exe
            self.original_events = list(self.current_events) # Sincronizza gli eventi originali con quelli salvati
            self.update_diff_display() # Aggiorna il display per mostrare "Nessuna modifica pendente"

            logger.info("Macro salvata con successo")
            messagebox.showinfo("Salvataggio Completato", "Macro salvata con successo.", parent=self.root)
            self.root.title(f"Editor Macro: {self.macro_name}") # Aggiorna il titolo della finestra
        except ValueError as ve: # Cattura l'errore specifico per nome duplicato
            logger.error(f"Errore di validazione nel salvataggio: {ve}")
            messagebox.showerror("Errore Salvataggio", str(ve), parent=self.root)
        except Exception as e:
            logger.error(f"Errore generico nel salvataggio: {e}")
            messagebox.showerror("Errore Salvataggio", f"Errore durante il salvataggio della macro: {e}", parent=self.root)

    def reset_changes(self):
        if messagebox.askyesno("Annulla Modifiche", "Sei sicuro di voler annullare tutte le modifiche non salvate?", parent=self.root):
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, self.macro_metadata['nome'])
            self.desc_entry.delete(0, tk.END)
            self.desc_entry.insert(0, self.macro_metadata['descrizione'])
            self.duration_entry.delete(0, tk.END)
            self.duration_entry.insert(0, str(self.macro_metadata['durata_sec']))
            self.exe_entry.delete(0, tk.END)
            self.exe_entry.insert(0, self.macro_metadata['eseguibile'])

            self.current_events = list(self.original_events) # Ripristina gli eventi originali
            self.populate_events_tree() # Ricarica la Treeview con gli eventi originali
            self.update_diff_display() # Aggiorna il display del diff

if __name__ == "__main__":
    logger.info("Avvio macro_editor.py")
    from repositories.database import setup_backup_table, setup_main_table
    setup_main_table() # Assicurati che le tabelle siano create/aggiornate all'avvio
    setup_backup_table() # Assicurati che la tabella di backup sia creata/aggiornata all'avvio

    if len(sys.argv) > 1:
        macro_name_arg = sys.argv[1]
        logger.info(f"Avvio editor per macro: {macro_name_arg}")
        root = tk.Tk()
        app = MacroEditorApp(root, macro_name_arg)
        root.mainloop()
    else:
        logger.error("Nome macro non fornito come argomento")
        print("Errore: Il nome della macro deve essere fornito come argomento.")
        print("Esempio: python macro_editor.py \"NomeMacroDiTest\"")
