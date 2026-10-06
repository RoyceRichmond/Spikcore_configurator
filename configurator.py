import tkinter as tk
from tkinter import ttk, messagebox

class MosbiusMatrixConfigurator:
    def __init__(self, root):
        self.root = root
        self.root.title("Mosbius Crossbar Configurator (24x10)")
        self.root.resizable(True, True)

        self.ROWS = 10
        self.COLS = 24

        # Estados:
        # 1 = Conectado (Rojo)
        # 0 = Abierto (Blanco)
        self.matrix = [[0 for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.buttons = [[None for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.button_vars = [
            [tk.IntVar(value=0) for _ in range(self.COLS)]
            for _ in range(self.ROWS)
        ]

        self._build_ui()
        self.update_bitstream()

    def _build_ui(self):
        # Frame contenedor con scroll para que quepa cómodamente en pantallas estándar
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=v_scrollbar.set)

        v_scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

        # Matriz de botones
        matrix_frame = ttk.LabelFrame(scrollable_frame, text="Matriz de Interconexión (24 filas × 10 columnas)")
        matrix_frame.pack(padx=16, pady=12)

        # Encabezado de columnas
        ttk.Label(matrix_frame, text="R\\C", font=("Consolas", 10, "bold")).grid(row=0, column=0, padx=4, pady=4)
        for c in range(self.COLS):
            ttk.Label(matrix_frame, text=f"C{c}", font=("Consolas", 10, "bold")).grid(row=0, column=c+1, padx=3, pady=4)

        # Celdas con estado persistente: seleccionada = conectada (rojo).
        for r in range(self.ROWS):
            ttk.Label(matrix_frame, text=f"R{r:02d}", font=("Consolas", 9, "bold")).grid(row=r+1, column=0, padx=6, pady=2)
            for c in range(self.COLS):
                btn = tk.Checkbutton(
                    matrix_frame,
                    text="",
                    width=1,
                    height=1,
                    indicatoron=False,
                    relief="solid",
                    bd=1,
                    bg="#FFFFFF",
                    selectcolor="#FF0702",
                    activebackground="#FF0400",
                    cursor="hand2",
                    variable=self.button_vars[r][c],
                    onvalue=1,
                    offvalue=0,
                    command=lambda row=r, col=c: self.update_cell_from_button(row, col)
                )
                btn.grid(row=r+1, column=c+1, padx=2, pady=2)
                self.buttons[r][c] = btn

        # Barra de acciones
        control_frame = ttk.Frame(scrollable_frame)
        control_frame.pack(fill="x", padx=16, pady=8)

        ttk.Button(control_frame, text="Limpiar Todo (Todo en 0 / Blanco)", command=self.clear_all).pack(side="left", padx=6)
        ttk.Button(control_frame, text="Conectar Todo (Todo en 1 / Rojo)", command=self.fill_all).pack(side="left", padx=6)
        ttk.Button(control_frame, text="Copiar Bitstream", command=self.copy_bitstream).pack(side="right", padx=6)

        # Contenedor inferior para el Bitstream resultante
        output_frame = ttk.LabelFrame(scrollable_frame, text="Bitstream Generado (240 bits: 1=Conectado/Rojo, 0=Abierto/Blanco)")
        output_frame.pack(fill="x", padx=16, pady=10)

        self.order_var = tk.StringVar(value="row_major")
        order_selector_frame = ttk.Frame(output_frame)
        order_selector_frame.pack(anchor="w", padx=6, pady=4)
        ttk.Radiobutton(order_selector_frame, text="Orden Fila por Fila (R0C0...R0C9, R1C0...)", variable=self.order_var, value="row_major", command=self.update_bitstream).pack(side="left", padx=6)
        ttk.Radiobutton(order_selector_frame, text="Orden Columna por Columna (C0R0...C0R23, C1R0...)", variable=self.order_var, value="col_major", command=self.update_bitstream).pack(side="left", padx=6)

        self.txt_bitstream = tk.Text(output_frame, height=4, width=70, font=("Consolas", 10), wrap="char")
        self.txt_bitstream.pack(padx=6, pady=6, fill="both")

        self.lbl_stats = ttk.Label(output_frame, text="Total: 240 bits | Conectados (1): 0 | Abiertos (0): 240", font=("Consolas", 9))
        self.lbl_stats.pack(anchor="w", padx=6, pady=4)

        # Atajo: Scroll con la rueda del ratón
        self.root.bind_all("<MouseWheel>", lambda event: main_canvas.yview_scroll(int(-1*(event.delta/120)), "units"))
        self.root.bind_all("<Button-4>", lambda event: main_canvas.yview_scroll(-1, "units"))
        self.root.bind_all("<Button-5>", lambda event: main_canvas.yview_scroll(1, "units"))

    def update_cell_from_button(self, row, col):
        self.matrix[row][col] = self.button_vars[row][col].get()
        self._update_button_color(row, col)
        self.update_bitstream()

    def _update_button_color(self, row, col):
        value = self.matrix[row][col]
        color = "#FF0702" if value else "#FFFFFF"
        self.button_vars[row][col].set(value)
        self.buttons[row][col].config(
            bg=color,
            activebackground=color,
            selectcolor=color,
        )

    def update_bitstream(self):
        bits = []
        active_count = 0

        if self.order_var.get() == "row_major":
            for r in range(self.ROWS):
                for c in range(self.COLS):
                    val = self.matrix[r][c]
                    bits.append(str(val))
                    if val == 1:
                        active_count += 1
        else:
            for c in range(self.COLS):
                for r in range(self.ROWS):
                    val = self.matrix[r][c]
                    bits.append(str(val))
                    if val == 1:
                        active_count += 1

        stream_str = "".join(bits)
        self.txt_bitstream.delete("1.0", tk.END)
        self.txt_bitstream.insert(tk.END, stream_str)
        self.lbl_stats.config(text=f"Total: 240 bits | Conectados (1): {active_count} | Abiertos (0): {240 - active_count}")

    def clear_all(self):
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self.matrix[r][c] = 0
                self._update_button_color(r, c)
        self.update_bitstream()

    def fill_all(self):
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self.matrix[r][c] = 1
                self._update_button_color(r, c)
        self.update_bitstream()

    def copy_bitstream(self):
        content = self.txt_bitstream.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Copiado", "Bitstream de 240 bits copiado al portapapeles.")

if __name__ == "__main__":
    app_root = tk.Tk()
    # Ajustamos tamaño inicial de la ventana para acomodar botones más grandes
    app_root.geometry("620 Mitsubishi" if False else "640x780")
    app = MosbiusMatrixConfigurator(app_root)
    app_root.mainloop()