#gui_layout
import tkinter as tk
from app.gui_style import *




class DashboardLayout:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.values = {}
        self.indicators = {}
        self.cov_indicators = {}


        self.setup_window()
        self.create_layout()

        self.view_main = tk.Frame(self.main_area, bg=BG_MAIN)
        self.view_cov  = tk.Frame(self.main_area, bg=BG_MAIN)
        self.view_fve  = tk.Frame(self.main_area, bg=BG_MAIN)

        self.view_main.pack(fill="both", expand=True)

        self.build_main_view()
        self.build_cov_view()
        self.build_fve_view()


    # =====================================================
    # OKNO A LAYOUT
    # =====================================================
    def setup_window(self):
        self.root.title("RPi Dashboard")
        self.root.geometry("1024x600")
        self.root.configure(bg="black")
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def create_layout(self):
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.top_bar = tk.Frame(self.root, height=60, bg="#222222")
        self.top_bar.grid(row=0, column=0, sticky="nsew")

        self.main_area = tk.Frame(self.root, bg="black")
        self.main_area.grid(row=1, column=0, sticky="nsew")

        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(1, weight=1)


        self.create_top_bar()

    # =====================================================
    # HORNÍ LIŠTA
    # =====================================================
    def create_top_bar(self):
        self.top_bar.grid_rowconfigure(0, weight=0)
        self.top_bar.grid_rowconfigure(1, weight=0)

        self.top_bar.grid_columnconfigure(0, weight=1)
        self.top_bar.grid_columnconfigure(1, weight=1)
        self.top_bar.grid_columnconfigure(2, weight=1)

        self.title_label = tk.Label(
            self.top_bar,
            text="FVE / ČOV – ŘÍDICÍ PANEL",
            fg="white",
            bg="#222222",
            font=("DejaVu Sans", 16, "bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20)

        self.status_label = tk.Label(
            self.top_bar,
            text="STAV: OK",
            fg="black",
            bg="#00aa00",
            font=("DejaVu Sans", 14, "bold"),
            padx=15,
            pady=5,
        )
        self.status_label.grid(row=0, column=1)

        self.status_reason = tk.Label(
            self.top_bar,
            text="",
            fg="white",
            bg="#222222",
            font=("DejaVu Sans", 11),
        )
        self.status_reason.grid(row=1, column=1, pady=(2, 0))

        self.time_label = tk.Label(
            self.top_bar,
            text="--:--:--",
            fg="white",
            bg="#222222",
            font=("DejaVu Sans", 14),
        )
        self.time_label.grid(row=0, column=2, sticky="e", padx=20)

    # =====================================================
    # LEVÝ PANEL
    # =====================================================
    def create_left_panel(self):
        self.left_panel.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            self.left_panel,
            text="ČOV – STAV SYSTÉMU",
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 14, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 15))

        row = 2
        self.create_status_row(self.left_panel, row, "Pumpa 1", "pump1")
        row += 1
        self.create_status_row(self.left_panel, row, "Pumpa 2", "pump2")
        row += 1
        self.create_status_row(self.left_panel, row, "Vzduchování", "air")

        row += 1
        self.create_section_label(self.left_panel, "PLOVÁKY", row)
        row += 1
        self.create_status_row(self.left_panel, row, "Plovák 1", "float1")
        row += 1
        self.create_status_row(self.left_panel, row, "Plovák 2", "float2")
        row += 1
        self.create_status_row(self.left_panel, row, "Plovák 3", "float3")
        row += 1
        self.create_status_row(self.left_panel, row, "Plovák 4", "float4")

        row += 1
        self.create_section_label(self.left_panel, "TEPLOTA", row)
        row += 1
        self.create_temp_row(self.left_panel, row, "Voda:", "temp_water")
        row += 1
        self.create_temp_row(self.left_panel, row, "Venkovní:", "temp_air")

    def create_section_label(self, parent, text, row):
        label = tk.Label(
            parent,
            text=text,
            fg="#aaaaaa",
            bg="#111111",
            font=("DejaVu Sans", 12, "bold"),
        )
        label.grid(row=row, column=0, sticky="w", padx=10, pady=(10, 5))

    def create_status_row(self, parent, row, text, key):
        frame = tk.Frame(parent, bg="#111111")
        frame.grid(row=row, column=0, sticky="w", padx=10, pady=5)

        indicator = tk.Canvas(
            frame, width=16, height=16, bg="#111111", highlightthickness=0
        )
        circle = indicator.create_oval(2, 2, 14, 14, fill="#555555")
        indicator.pack(side="left")

        label = tk.Label(
            frame,
            text=text,
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 12),
        )
        label.pack(side="left", padx=10)

        self.indicators[key] = (indicator, circle)

    def create_temp_row(self, parent, row, label_text, key):
        frame = tk.Frame(parent, bg="#111111")
        frame.grid(row=row, column=0, sticky="w", padx=10, pady=5)

        label = tk.Label(
            frame,
            text=label_text,
            fg="#aaaaaa",
            bg="#111111",
            font=("DejaVu Sans", 12),
        )
        label.pack(side="left")

        value = tk.Label(
            frame,
            text="--.- °C",
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 12, "bold"),
        )
        value.pack(side="left", padx=10)

        self.values[key] = value

    # =====================================================
    # PRAVÝ PANEL
    # =====================================================
    def create_right_panel(self):
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(1, weight=1)

        title = tk.Label(
            self.right_panel,
            text="FVE – REGULÁTORY",
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 14, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 15))

        self.create_regulator_block(self.right_panel, 1, 0, 1, "REGULÁTOR 1")

        # ===== TEPLOTY (SPOLEČNÉ) =====
        temp_title = tk.Label(
            self.right_panel,
            text="TEPLOTY",
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 13, "bold"),
        )
        temp_title.grid(row=10, column=0, sticky="w", padx=10, pady=(15, 5))

        self.create_value_row(self.right_panel, 11, "Nádrž – horní:", "tank_top")
        self.create_value_row(self.right_panel, 12, "Nádrž – dolní:", "tank_bottom")
        self.create_value_row(self.right_panel, 13, "Vnitřní prostor:", "tank_in")
        self.create_value_row(self.right_panel, 14, "TUV:", "tank_tuv")



    def create_regulator_block(self, parent, row, column, rid, name):
        block = tk.Frame(parent, bg="#111111", bd=1, relief="solid")
        block.grid(row=row, column=column, sticky="nsew", padx=10, pady=(0, 10))

        block.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            block,
            text=name,
            fg="#dddddd",
            bg="#111111",
            font=("DejaVu Sans", 13, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(4, 4))

        self.create_value_row(block, 1, "Napětí baterie:", f"r{rid}_batt")
        self.create_value_row(block, 2, "Výkon panelů:", f"r{rid}_power")
        self.create_value_row(block, 3, "Vyrobeno dnes:", f"r{rid}_energy_day")
        self.create_value_row(block, 4, "Vyrobeno měsíc (kWh):", f"r{rid}_energy_month")
        self.create_value_row(block, 5, "Vyrobeno rok (kWh):", f"r{rid}_energy_year")
        self.create_value_row(block, 6, "Max napětí aku (dnes):", f"r{rid}_vmax")
        self.create_value_row(block, 7, "Min napětí aku (dnes):", f"r{rid}_vmin")
        self.create_value_row(block, 8, "Teplota reg.:", f"r{rid}_3111")
        self.create_value_row(block, 9, "Stav nabíjení:", f"r{rid}_state")



    def create_value_row(self, parent, row, label_text, key):
        frame = tk.Frame(parent, bg="#111111")
        frame.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
        frame.grid_columnconfigure(1, weight=1)

        label = tk.Label(
            frame,
            text=label_text,
            fg="#aaaaaa",
            bg="#111111",
            font=("DejaVu Sans", 12),
            width=20,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        value = tk.Label(
            frame,
            text="---",
            fg="white",
            bg="#111111",
            font=("DejaVu Sans", 12, "bold"),
            anchor="w",
        )
        value.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.values[key] = value

    def build_cov_view(self):
        root = self.view_cov

        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # === NADPIS ===
        tk.Label(
            root,
            text="ČOV – DETAIL",
            fg=FG_MAIN,
            bg=BG_MAIN,
            font=FONT_TITLE
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=12)

        # =================================================
        # LEVÝ PANEL – ČOV
        # =================================================
        left = tk.Frame(
            root,
            bg=BG_PANEL,
            bd=1,
            relief="solid"
        )
        left.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.grid_columnconfigure(0, weight=1)

        # ---- ČERPADLA + VZDUCH ----
        self._cov_row(left, "Pumpa 1", "pump1")
        self._cov_row(left, "Pumpa 2", "pump2")
        self._cov_row(left, "Vzduchování", "air")

        tk.Frame(left, height=1, bg=SEP_COLOR).pack(fill="x", padx=10, pady=8)

        # ---- PLOVÁKY ----
        self._cov_row(left, "Plovák 1", "float1")
        self._cov_row(left, "Plovák 2", "float2")
        self._cov_row(left, "Plovák 3", "float3")
        self._cov_row(left, "Plovák 4", "float4")

        tk.Frame(left, height=1, bg=SEP_COLOR).pack(fill="x", padx=10, pady=8)

        # ---- HODNOTY ČOV ----
        self._cov_value(left, "Voda", "cov_temp_water")
        self._cov_value(left, "Režim", "cov_mode")

        # =================================================
        # PRAVÝ PANEL – HISTORIE TEPLOT VZDUCHU
        # =================================================
        right = tk.Frame(
            root,
            bg=BG_PANEL,
            bd=1,
            relief="solid"
        )
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        tk.Label(
            right,
            text="HISTORIE VENKOVNÍ TEPLOTY",
            fg=FG_LABEL,
            bg=BG_PANEL,
            font=FONT_LABEL
        ).pack(anchor="w", padx=12, pady=12)

        summary_wrap = tk.Frame(right, bg=BG_PANEL)
        summary_wrap.pack(fill="x", padx=10, pady=(0, 10))

        for idx, (title, prefix) in enumerate((
            ("Dnes", "cov_hist_day"),
            ("Měsíc", "cov_hist_month"),
            ("Rok", "cov_hist_year"),
        )):
            card = tk.Frame(
                summary_wrap,
                bg=ROW_A if idx % 2 == 0 else ROW_B,
                highlightthickness=1,
                highlightbackground="#333333"
            )
            card.pack(side="left", expand=True, fill="both", padx=4)

            tk.Label(
                card,
                text=title,
                fg=FG_MAIN,
                bg=card["bg"],
                font=("DejaVu Sans", 12, "bold")
            ).pack(anchor="w", padx=10, pady=(8, 4))

            self._cov_history_metric(card, "Min", f"{prefix}_min", card["bg"])
            self._cov_history_metric(card, "Max", f"{prefix}_max", card["bg"])

        monthly = tk.Frame(
            right,
            bg=BG_TILE,
            highlightthickness=1,
            highlightbackground="#333333"
        )
        monthly.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        monthly.grid_columnconfigure(0, weight=1)
        monthly.grid_columnconfigure(1, weight=1)

        tk.Label(
            monthly,
            text="Měsíční extrémy venkovní teploty",
            fg=FG_MAIN,
            bg=BG_TILE,
            font=("DejaVu Sans", 12, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 6))

        month_names = (
            "Led", "Úno", "Bře", "Dub", "Kvě", "Čvn",
            "Čvc", "Srp", "Zář", "Říj", "Lis", "Pro",
        )

        for idx, month_name in enumerate(month_names, start=1):
            column = 0 if idx <= 6 else 1
            row = idx if idx <= 6 else idx - 6
            bg = ROW_A if row % 2 == 1 else ROW_B
            row_frame = tk.Frame(monthly, bg=bg)
            row_frame.grid(row=row, column=column, sticky="ew", padx=8, pady=2)

            tk.Label(
                row_frame,
                text=month_name,
                fg=FG_MAIN,
                bg=bg,
                font=("DejaVu Sans", 11, "bold"),
                width=4,
                anchor="w"
            ).pack(side="left", padx=(10, 8), pady=6)

            min_key = f"cov_hist_m{idx:02d}_min"
            max_key = f"cov_hist_m{idx:02d}_max"
            self._cov_history_inline(row_frame, "min", min_key, bg)
            self._cov_history_inline(row_frame, "max", max_key, bg)

        # =================================================
        # ZPĚT
        # =================================================
        tk.Button(
            root,
            text="ZPĚT",
            font=FONT_VALUE,
            command=lambda: self.show_view("main")
        ).grid(row=2, column=0, columnspan=2, pady=(0, 10))



    def _cov_row(self, parent, label, key):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=3)

        canvas = tk.Canvas(row, width=16, height=16, bg=BG_PANEL, highlightthickness=0)
        circle = canvas.create_oval(2, 2, 14, 14, fill=FG_MUTED)
        canvas.pack(side="left", padx=6)

        tk.Label(row, text=label, fg=FG_MAIN, bg=BG_PANEL, font=FONT_VALUE).pack(side="left")

        self.cov_indicators[key] = (canvas, circle)




    def _cov_value(self, parent, label, key):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure(1, weight=1)

        tk.Label(
            row,
            text=f"{label}:",
            fg=FG_LABEL,
            bg=BG_PANEL,
            font=FONT_LABEL,
            width=12,
            anchor="w"
        ).grid(row=0, column=0, sticky="w")

        val = tk.Label(
            row,
            text="--.- °C",
            fg=FG_MAIN,
            bg=BG_PANEL,
            font=FONT_VALUE,
            anchor="w"
        )
        val.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.values[key] = val

    def _cov_history_metric(self, parent, label, key, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=10, pady=3)
        row.grid_columnconfigure(1, weight=1)

        tk.Label(
            row,
            text=f"{label}:",
            fg=FG_LABEL,
            bg=bg,
            font=("DejaVu Sans", 11),
            width=6,
            anchor="w"
        ).grid(row=0, column=0, sticky="w")

        value = tk.Label(
            row,
            text="--.- °C",
            fg=FG_MAIN,
            bg=bg,
            font=("DejaVu Sans", 12, "bold"),
            anchor="w"
        )
        value.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.values[key] = value

    def _cov_history_inline(self, parent, label, key, bg):
        tk.Label(
            parent,
            text=f"{label}:",
            fg=FG_LABEL,
            bg=bg,
            font=("DejaVu Sans", 10)
        ).pack(side="left", padx=(0, 4))

        value = tk.Label(
            parent,
            text="--.-",
            fg=FG_MAIN,
            bg=bg,
            font=("DejaVu Sans", 10, "bold"),
            width=5,
            anchor="e"
        )
        value.pack(side="left", padx=(0, 10))
        self.values[key] = value

    def _main_cov_pair_row(self, parent, label, key, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=8, pady=2)
        row.grid_columnconfigure(1, weight=1)

        tk.Label(
            row,
            text=label,
            fg=FG_LABEL,
            bg=bg,
            font=FONT_LABEL,
            width=10,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=6)

        value = tk.Label(
            row,
            text="--.- °C",
            fg=FG_MAIN,
            bg=bg,
            font=FONT_VALUE,
            anchor="w"
        )
        value.grid(row=0, column=1, sticky="w", padx=(8, 12))
        self.values[key] = value

    def _main_cov_primary_temp_row(self, parent, label, key, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="both", expand=True, padx=8, pady=2)

        tk.Label(
            row,
            text=label,
            fg=FG_LABEL,
            bg=bg,
            font=("DejaVu Sans", 13)
        ).pack(anchor="center", pady=(24, 6))

        value = tk.Label(
            row,
            text="--.- °C",
            fg=FG_MAIN,
            bg=bg,
            font=("DejaVu Sans", 28, "bold")
        )
        value.pack(anchor="center", pady=(0, 24))
        self.values[key] = value

    def _main_cov_content_row(self, parent, key, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=8, pady=2)

        value = tk.Label(
            row,
            text="• ---",
            fg=FG_MAIN,
            bg=bg,
            font=FONT_VALUE,
            justify="left",
            anchor="w"
        )
        value.pack(fill="x", padx=12, pady=6)
        self.values[key] = value

        
    def build_fve_view(self):
        root = self.view_fve

        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        tk.Label(
            root,
            text="FVE – DETAIL",
            fg=FG_MAIN,
            bg=BG_MAIN,
            font=FONT_TITLE
        ).grid(row=0, column=0, sticky="w", padx=12, pady=12)

        ROW_A = "#1e1e1e"
        ROW_B = "#242424"

        SEP_COLOR = "#2F3645"

        for rid in (1,):
            panel = tk.Frame(root, bg=BG_PANEL)
            panel.grid(row=1, column=rid - 1, sticky="nsew", padx=10, pady=10)

            # === NADPIS REGULÁTORU ===
            tk.Label(
                panel,
                text=f"REGULÁTOR {rid}",
                fg=FG_MAIN,
                bg=BG_PANEL,
                font=FONT_TITLE
            ).pack(anchor="w", padx=12, pady=(10, 6))

            # tenká linka pod nadpisem
            tk.Frame(panel, height=1, bg=SEP_COLOR).pack(fill="x", padx=8, pady=(0, 12))

            row_idx = 0

            def row(label, key, is_state=False):
                nonlocal row_idx
                bg = ROW_A if row_idx % 2 == 0 else ROW_B
                row_idx += 1

                r = tk.Frame(panel, bg=bg)
                r.pack(fill="x", padx=8, pady=2)
                r.grid_columnconfigure(1, weight=1)

                tk.Label(
                    r,
                    text=label,
                    fg=FG_LABEL,
                    bg=bg,
                    font=("DejaVu Sans", 13),
                    width=22,
                    anchor="w"
                ).grid(row=0, column=0, sticky="w", padx=14)

                val = tk.Label(
                    r,
                    text="---",
                    fg=FG_MAIN,
                    bg=bg,
                    font=("DejaVu Sans", 14, "bold"),
                    anchor="w"
                )
                val.grid(row=0, column=1, sticky="w", padx=(8, 14))

                self.values[key] = val

                if is_state:
                    val._is_charge_state = True


            # =====================
            # ⚡ OKAMŽITÉ HODNOTY
            # =====================
            row("⚡  Napětí baterie", f"fve{rid}_batt")
            row("☀️ Výkon panelů", f"fve{rid}_power")

            tk.Frame(panel, height=1, bg=SEP_COLOR).pack(fill="x", padx=8, pady=12)

            # =====================
            # 📊 DENNÍ BILANCE
            # =====================
            row("📈 Vyrobeno dnes", f"fve{rid}_energy_day")
            row("📈 Vyrobeno měsíc (kWh)", f"fve{rid}_energy_month")
            row("📈 Vyrobeno rok (kWh)", f"fve{rid}_energy_year")
            row("🔋 Max napětí aku (dnes)", f"fve{rid}_vmax")
            row("🔋 Min napětí aku (dnes)", f"fve{rid}_vmin")

            tk.Frame(panel, height=1, bg=SEP_COLOR).pack(fill="x", padx=8, pady=12)

            # =====================
            # 🌡 STAV
            # =====================
            row("🌡 Teplota regulátoru", f"fve{rid}_3111")
            row("⚡ Stav nabíjení", f"fve{rid}_state", is_state=True)

        # === ZPĚT ===
        tk.Button(
            root,
            text="ZPĚT",
            font=FONT_VALUE,
            command=lambda: self.show_view("main")
        ).grid(row=2, column=0, pady=10)


    def _fve_value(self, parent, label, key):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=3)

        tk.Label(
            row,
            text=label,
            fg=FG_LABEL,
            bg=BG_PANEL,
            font=FONT_LABEL
        ).pack(side="left")

        val = tk.Label(
            row,
            text="---",
            fg=FG_MAIN,
            bg=BG_PANEL,
            font=FONT_VALUE
        )
        val.pack(side="right")

        self.values[key] = val


    #přepínač pohledů
    def show_view(self, name: str):
        # schovej vše
        self.view_main.pack_forget()
        self.view_cov.pack_forget()
        self.view_fve.pack_forget()

        # zobraz požadovaný pohled
        if name == "main":
            self.view_main.pack(fill="both", expand=True)
        elif name == "cov":
            self.view_cov.pack(fill="both", expand=True)
        elif name == "fve":
            self.view_fve.pack(fill="both", expand=True)


        #rozložení hl. obrazovky
    def build_main_view(self):
        root = self.view_main
        ROW_A = "#1e1e1e"
        ROW_B = "#242424"
        root.grid_rowconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=0)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # =================================================
        # ČOV – HLAVNÍ KARTA
        # =================================================

        cov = tk.Frame(root, bg=BG_TILE)
        cov.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        cov.pack_propagate(False)

        content = tk.Frame(cov, bg=BG_TILE)
        content.pack(fill="both", expand=True)

        tk.Label(
            content,
            text="Venkovní teplota",
            fg=FG_LABEL,
            bg=BG_TILE,
            font=FONT_LABEL
        ).pack(anchor="w", padx=16, pady=(14, 4))

        outdoor_box = tk.Frame(
            content,
            bg=BG_TILE,
            highlightthickness=1,
            highlightbackground="#333333"
        )
        outdoor_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._main_cov_primary_temp_row(outdoor_box, "Aktuálně", "main_temp_air", ROW_A)

        tk.Label(
            content,
            text="Venkovní dnes",
            fg=FG_LABEL,
            bg=BG_TILE,
            font=FONT_LABEL
        ).pack(anchor="w", padx=16, pady=(0, 3))

        history_box = tk.Frame(
            content,
            bg=BG_TILE,
            highlightthickness=1,
            highlightbackground="#333333"
        )
        history_box.pack(fill="x", padx=16, pady=(0, 8))

        self._main_cov_pair_row(history_box, "Minimum", "main_cov_air_day_min", ROW_A)
        self._main_cov_pair_row(history_box, "Maximum", "main_cov_air_day_max", ROW_B)

        # spacer → tlačítko dolů
        tk.Frame(cov, bg=BG_TILE).pack(expand=True)

        tk.Button(
            cov,
            text="DETAIL ČOV",
            font=FONT_VALUE,
            command=lambda: self.show_view("cov")
        ).pack(fill="x", padx=16, pady=(0, 14))


        # =================================================
        # FVE – HLAVNÍ KARTA
        # =================================================
        # === FVE BLOK (pravá strana hlavní obrazovky) ===
        fve = tk.Frame(root, bg=BG_TILE)
        fve.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)

        # umožní roztahování bloku
        fve.pack_propagate(False)

        tk.Label(
            fve,
            text="FVE",
            fg=FG_LABEL,
            bg=BG_TILE,
            font=FONT_LABEL
        ).pack(anchor="w", padx=16, pady=(14, 6))

        # === OBSAH REGULÁTORŮ ===
        content = tk.Frame(fve, bg=BG_TILE)
        content.pack(fill="both", expand=True)

        for rid in (1,):
            block = tk.Frame(
                content,
                bg=BG_TILE,
                highlightthickness=1,
                highlightbackground="#333333"
            )
            block.pack(fill="x", padx=16, pady=(6, 10))

            tk.Label(
                block,
                text=f"REGULÁTOR {rid}",
                fg=FG_LABEL,
                bg=BG_TILE,
                font=FONT_LABEL
            ).pack(anchor="w", pady=(0, 4))

            colors = [ROW_A, ROW_B]

            self.zebra_row(
                block,
                "Napětí baterie",
                f"main_r{rid}_batt",
                colors[0]
            )

            self.zebra_row(
                block,
                "Výkon panelů",
                f"main_r{rid}_power",
                colors[1]
            )

            self.zebra_row(
                block,
                "Vyrobeno dnes",
                f"main_r{rid}_energy_day",
                colors[0]
            )

            self.zebra_row(
                block,
                "Teplota reg.",
                f"main_r{rid}_temp",
                colors[1]
            )

            self.zebra_row(
                block,
                "Stav",
                f"main_r{rid}_state",
                colors[0]
            )

            self.zebra_row(
                block,
                "Vytěžování",
                "main_fve_load",
                colors[1]
            )

        # === TLAČÍTKO DOLE ===
        tk.Button(
            fve,
            text="DETAIL FVE",
            font=FONT_VALUE,
            command=lambda: self.show_view("fve")
        ).pack(side="bottom", fill="x", padx=16, pady=12)


        # =================================================
        # SPODNÍ TEPLOTY – BEZE ZMĚN
        # =================================================
        temp_block = tk.Frame(root, bg=BG_PANEL)
        temp_block.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

        tk.Label(
            temp_block,
            text="TEPLOTY",
            fg=FG_MAIN,
            bg=BG_PANEL,
            font=FONT_TITLE
        ).pack(anchor="w", padx=12, pady=(8, 4))

        row = tk.Frame(temp_block, bg=BG_PANEL)
        row.pack(fill="x", padx=8)

        for key, label in [
            ("tank_top", "Horní"),
            ("tank_bottom", "Dolní"),
            ("tank_tuv", "TUV"),
            ("tank_in", "Vnitřní"),
        ]:
            box = tk.Frame(row, bg=BG_TILE)
            box.pack(side="left", expand=True, fill="both", padx=6, pady=4)

            self.values[key] = tk.Label(
                box,
                text="--.- °C",
                fg=FG_MAIN,
                bg=BG_TILE,
                font=FONT_VALUE
            )
            self.values[key].pack()

            tk.Label(
                box,
                text=label,
                fg=FG_LABEL,
                bg=BG_TILE,
                font=FONT_LABEL
            ).pack()

    def zebra_row(self, parent, text, value_key, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=1)
        row.grid_columnconfigure(1, weight=1)

        tk.Label(
            row,
            text=text,
            fg=FG_LABEL,
            bg=bg,
            font=FONT_LABEL,
            width=13,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=6)

        self.values[value_key] = tk.Label(
            row,
            text="---",
            fg=FG_MAIN,
            bg=bg,
            font=FONT_VALUE,
            anchor="w"
        )
        self.values[value_key].grid(row=0, column=1, sticky="w", padx=(8, 6))
