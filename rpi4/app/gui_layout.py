#gui_layout
import tkinter as tk
from app.gui_style import *




class DashboardLayout:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.values = {}
        self.cov_indicators = {}
        self.heating_buttons = {}


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
        # PRAVÝ PANEL – HISTORIE TEPLOT + CYKLY ČERPADEL
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

        cycles = tk.Frame(
            right,
            bg=BG_TILE,
            highlightthickness=1,
            highlightbackground="#333333"
        )
        cycles.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cycles.grid_columnconfigure(0, weight=2)
        cycles.grid_columnconfigure(1, weight=1)
        cycles.grid_columnconfigure(2, weight=1)
        cycles.grid_columnconfigure(3, weight=1)

        tk.Label(
            cycles,
            text="Posledních 10 čerpacích cyklů",
            fg=FG_MAIN,
            bg=BG_TILE,
            font=("DejaVu Sans", 12, "bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 6))

        headers = ("Čas", "Pumpa 1", "Pumpa 2", "Rozdíl")
        for col, title in enumerate(headers):
            tk.Label(
                cycles,
                text=title,
                fg=FG_LABEL,
                bg=BG_TILE,
                font=("DejaVu Sans", 10, "bold"),
                anchor="w" if col == 0 else "e"
            ).grid(row=1, column=col, sticky="ew", padx=8, pady=(0, 4))

        for row in range(10):
            bg = ROW_A if row % 2 == 0 else ROW_B
            for col, key_suffix in enumerate(("time", "p1", "p2", "diff")):
                value = tk.Label(
                    cycles,
                    text="--",
                    fg=FG_MAIN,
                    bg=bg,
                    font=("DejaVu Sans", 10, "bold"),
                    anchor="w" if col == 0 else "e"
                )
                value.grid(row=row + 2, column=col, sticky="ew", padx=8, pady=3)
                self.values[f"cov_cycle_{row}_{key_suffix}"] = value

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

    def build_fve_view(self):
        root = self.view_fve

        root.grid_rowconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=0)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        panel = tk.Frame(
            root,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground="#333333",
        )
        panel.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        tk.Label(
            panel,
            text="RUČNÍ OVLÁDÁNÍ OHŘEVU",
            fg=FG_MAIN,
            bg=BG_PANEL,
            font=FONT_TITLE,
        ).pack(anchor="w", padx=18, pady=(8, 2))

        temperatures = tk.Frame(panel, bg=BG_PANEL)
        temperatures.pack(fill="x", padx=18, pady=(0, 4))
        for column in range(4):
            temperatures.grid_columnconfigure(column, weight=1)

        for column, (title, key) in enumerate((
            ("TUV", "heat_tuv_temp"),
            ("AKU – horní", "heat_aku_top_temp"),
            ("AKU – dolní", "heat_aku_temp"),
            ("Místnost", "heat_room_temp"),
        )):
            box = tk.Frame(temperatures, bg=BG_TILE)
            box.grid(row=0, column=column, sticky="nsew", padx=6)
            tk.Label(
                box,
                text=title,
                fg=FG_LABEL,
                bg=BG_TILE,
                font=FONT_LABEL,
            ).pack(pady=(4, 2))
            value = tk.Label(
                box,
                text="--.- °C",
                fg=FG_MAIN,
                bg=BG_TILE,
                font=FONT_VALUE,
            )
            value.pack(pady=(0, 4))
            self.values[key] = value

        energy = tk.Frame(panel, bg=BG_PANEL)
        energy.pack(fill="x", padx=24, pady=(0, 4))
        energy.grid_columnconfigure(1, weight=1)
        energy.grid_columnconfigure(3, weight=1)
        metrics = (
            ("AKU průměr:", "fve_tank_average"),
            ("Tepelná ztráta:", "fve_heat_loss"),
            ("FVE dnes:", "fve_energy_today"),
            ("FVE celkem:", "fve_energy_total"),
        )
        for index, (label, key) in enumerate(metrics):
            row, side = divmod(index, 2)
            column = side * 2
            tk.Label(energy, text=label, fg=FG_LABEL, bg=BG_PANEL,
                     font=FONT_LABEL, anchor="w").grid(row=row, column=column, sticky="w", padx=(0, 5) if side == 0 else (12, 5), pady=1)
            value = tk.Label(energy, text="---", fg=FG_MAIN, bg=BG_PANEL,
                             font=FONT_VALUE, anchor="e")
            value.grid(row=row, column=column + 1, sticky="e", pady=1)
            self.values[key] = value

        controls = tk.Frame(panel, bg=BG_PANEL)
        controls.pack(fill="both", expand=True, padx=18, pady=2)
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

        for column, (key, title) in enumerate((
            ("tuv", "TUV"),
            ("aku", "AKU"),
        )):
            button = tk.Button(
                controls,
                text=f"{title}\nRUČNĚ ZAPNOUT",
                fg="white",
                bg="#3a3a3a",
                activeforeground="white",
                activebackground="#555555",
                font=("DejaVu Sans", 16, "bold"),
                height=2,
            )
            button.grid(row=0, column=column, sticky="nsew", padx=6, pady=4)
            self.heating_buttons[key] = button

        pump_row = tk.Frame(panel, bg=BG_PANEL)
        pump_row.pack(fill="x", padx=24, pady=4)
        self.pump_button = tk.Button(
            pump_row, text="ČERPADLO – RUČNĚ ZAPNOUT", font=FONT_LABEL,
            fg="white", bg="#3a3a3a", activeforeground="white",
            activebackground="#555555", state="disabled", pady=8,
        )
        self.pump_button.pack(side="left")
        pump_status = tk.Label(
            pump_row, text="BEZ ZPĚTNÉHO STAVU", fg=FG_MAIN,
            bg=BG_PANEL, font=FONT_LABEL, anchor="e",
        )
        pump_status.pack(side="right", padx=(10, 0))
        self.values["pump_status"] = pump_status

        status = tk.Frame(panel, bg=BG_PANEL)
        status.pack(fill="x", padx=24, pady=(2, 2))
        status.grid_columnconfigure(1, weight=1)

        for row, (label, key) in enumerate((
            ("Režim:", "heat_mode"),
            ("Skutečný výstup:", "heat_active"),
            ("Stav:", "heat_reason"),
        )):
            tk.Label(
                status,
                text=label,
                fg=FG_LABEL,
                bg=BG_PANEL,
                font=FONT_LABEL,
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=2)
            value = tk.Label(
                status,
                text="---",
                fg=FG_MAIN,
                bg=BG_PANEL,
                font=FONT_VALUE,
                anchor="w",
            )
            value.grid(row=row, column=1, sticky="w", pady=2)
            self.values[key] = value

        auto_button = tk.Button(
            panel,
            text="ZPĚT DO AUTOMATICKÉHO REŽIMU",
            fg="white",
            bg="#315a31",
            activeforeground="white",
            activebackground="#427742",
            font=FONT_VALUE,
        )
        auto_button.pack(fill="x", padx=24, pady=(4, 8))
        self.heating_buttons["auto"] = auto_button

        # === ZPĚT ===
        tk.Button(
            root,
            text="ZPĚT",
            font=FONT_VALUE,
            command=lambda: self.show_view("main")
        ).grid(row=1, column=0, columnspan=2, pady=10)


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
                "Max. napětí baterie dnes",
                f"main_r{rid}_vmax",
                colors[1]
            )

            self.zebra_row(
                block,
                "Min. napětí baterie dnes",
                f"main_r{rid}_vmin",
                colors[0]
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
            width=24,
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
