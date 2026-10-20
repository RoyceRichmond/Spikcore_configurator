import re
import textwrap
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

HEX_LENGTH = 64
NUMBER_OF_BITS = 250
SYNAPSE_BITS = 6
FIXED_TRAILER = "1011"
IO_NUMBERS = (
    45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34,
    30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19,
)
BAUDRATE = 115200


def normalize_hex(value):
    value = value.strip().replace(" ", "")
    if value.lower().startswith("0x"):
        value = value[2:]
    if len(value) != HEX_LENGTH:
        raise ValueError("El valor debe tener exactamente 64 caracteres hexadecimales.")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError("El valor contiene caracteres que no son hexadecimales.")
    return value.upper()


def _detect_ports():
    if list_ports is None:
        return []
    return [port.device for port in list_ports.comports()]


def build_remote_script(hex_value, action):
    """Build one complete raw-REPL command for the selected Pico action."""
    if action not in ("R", "P", "L"):
        raise ValueError("Acción serial inválida.")

    return textwrap.dedent(
        f"""
        import array
        import time
        import rp2
        from machine import Pin

        NUM_LEDS = 1
        PIN_NUM = 23
        brightness = 0.1

        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
        def ws2812():
            T1 = 2
            T2 = 5
            T3 = 3
            wrap_target()
            label("bitloop")
            out(x, 1).side(0)[T3 - 1]
            jmp(not_x, "do_zero").side(1)[T1 - 1]
            jmp("bitloop").side(1)[T2 - 1]
            label("do_zero")
            nop().side(0)[T2 - 1]
            wrap()

        sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(PIN_NUM))
        sm.active(1)
        ar = array.array("I", [0 for _ in range(NUM_LEDS)])

        def pixels_show():
            dimmer_ar = array.array("I", [0 for _ in range(NUM_LEDS)])
            for i, c in enumerate(ar):
                r = int(((c >> 8) & 0xFF) * brightness)
                g = int(((c >> 16) & 0xFF) * brightness)
                b = int((c & 0xFF) * brightness)
                dimmer_ar[i] = (g << 16) + (r << 8) + b
            sm.put(dimmer_ar, 8)
            time.sleep_ms(10)

        def pixels_set(i, color):
            ar[i] = (color[1] << 16) + (color[0] << 8) + color[2]

        def pixels_fill(color):
            for i in range(len(ar)):
                pixels_set(i, color)

        BLACK = (0, 0, 0)
        RED = (255, 0, 0)
        GREEN = (0, 255, 0)
        DATA_PIN = 2
        CLK_PIN = 3
        EN_PIN = 4
        STATE_LED = 25
        CLK_PERIOD_US = 10
        NUMBER_OF_BITS = 250

        data = Pin(DATA_PIN, Pin.OUT, value=0)
        clk = Pin(CLK_PIN, Pin.OUT, value=0)
        enable = Pin(EN_PIN, Pin.OUT, value=0)
        status_led = Pin(STATE_LED, Pin.OUT, value=1)
        variable_bytes = bytes.fromhex({hex_value!r})

        def send_bitstream(data_bytes):
            half_period_us = max(1, CLK_PERIOD_US // 2)
            for i in range(NUMBER_OF_BITS):
                byte_idx = i // 8
                bit_idx = 7 - (i % 8)
                current_bit = (data_bytes[byte_idx] >> bit_idx) & 1
                data.value(current_bit)
                status_led.value(current_bit)
                clk.value(1)
                pixels_fill(RED)
                pixels_show()
                time.sleep_us(half_period_us)
                clk.value(0)
                pixels_fill(BLACK)
                pixels_show()
                time.sleep_us(half_period_us)

        enable.value(0)
        status_led.value(0)
        pixels_fill(BLACK)
        pixels_show()

        if {action!r} == "R":
            print("Bitstream actualizado")
        elif {action!r} == "P":
            send_bitstream(variable_bytes)
            status_led.value(1)
            print("Bitstream enviado")
        else:
            enable.value(1)
            pixels_fill(GREEN)
            pixels_show()
            print("Latch-up activado")
        print("READY")
        """
    )


class MosbiusMatrixConfigurator:
    def __init__(self, root):
        self.root = root
        self.root.title("Mosbius Crossbar Configurator (24x10)")
        self.root.resizable(True, True)

        self.ROWS = 24
        self.COLS = 10

        self.matrix = [[0 for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.buttons = [[None for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.synapses = [0 for _ in range(SYNAPSE_BITS)]
        self.synapse_buttons = [None for _ in range(SYNAPSE_BITS)]

        self._build_ui()
        self.update_bitstream()

    def _build_ui(self):
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        self.scrollable_frame = scrollable_frame

        scrollable_frame.bind(
            "<Configure>",
            lambda event: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=v_scrollbar.set)

        v_scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

        matrix_frame = ttk.LabelFrame(
            scrollable_frame,
            text="Matriz de Interconexión (24 filas × 10 columnas)",
        )
        matrix_frame.pack(padx=16, pady=12)

        ttk.Label(
            matrix_frame,
            text="R\\C",
            font=("Consolas", 10, "bold"),
        ).grid(row=0, column=0, padx=4, pady=4)
        for column in range(self.COLS):
            ttk.Label(
                matrix_frame,
                text="C{}".format(column),
                font=("Consolas", 10, "bold"),
            ).grid(row=0, column=column + 1, padx=3, pady=4)

        for row in range(self.ROWS):
            ttk.Label(
                matrix_frame,
                text="I/O-{}".format(IO_NUMBERS[row]),
                font=("Consolas", 9, "bold"),
            ).grid(row=row + 1, column=0, padx=6, pady=2)
            for column in range(self.COLS):
                button = tk.Canvas(
                    matrix_frame,
                    width=18,
                    height=18,
                    highlightthickness=0,
                    bd=0,
                    cursor="hand2",
                )
                button.create_oval(
                    2,
                    2,
                    16,
                    16,
                    fill="#FFFFFF",
                    outline="#555555",
                    width=1,
                )
                button.bind(
                    "<Button-1>",
                    lambda event, selected_row=row, selected_column=column:
                    self.toggle_cell(selected_row, selected_column),
                )
                button.grid(row=row + 1, column=column + 1, padx=2, pady=2)
                self.buttons[row][column] = button

        synapse_frame = ttk.LabelFrame(
            scrollable_frame,
            text="Sinapsis (rojo excitatoria, blanco inhibitoria)",
        )
        synapse_frame.pack(fill="x", padx=16, pady=(4, 8))
        for index in range(SYNAPSE_BITS):
            synapse = tk.Canvas(
                synapse_frame,
                width=24,
                height=24,
                highlightthickness=0,
                bd=0,
                cursor="hand2",
            )
            synapse.create_oval(
                3,
                3,
                21,
                21,
                fill="#FFFFFF",
                outline="#555555",
                width=1,
            )
            synapse.bind(
                "<Button-1>",
                lambda event, selected_index=index:
                self.toggle_synapse(selected_index),
            )
            synapse.grid(row=0, column=index, padx=10, pady=(6, 2))
            ttk.Label(synapse_frame, text="S{}".format(index)).grid(
                row=1,
                column=index,
                padx=10,
                pady=(0, 6),
            )
            self.synapse_buttons[index] = synapse

        control_frame = ttk.Frame(scrollable_frame)
        control_frame.pack(fill="x", padx=16, pady=8)

        ttk.Button(
            control_frame,
            text="Limpiar Todo (Todo en 0 / Blanco)",
            command=self.clear_all,
        ).pack(side="left", padx=6)
        ttk.Button(
            control_frame,
            text="Conectar Todo (Todo en 1 / Rojo)",
            command=self.fill_all,
        ).pack(side="left", padx=6)
       #tk.Button(
       #    control_frame,
       #    text="Copiar Bitstream",
       #    command=self.copy_bitstream,
       #).pack(side="right", padx=6)
       #ttk.Button(
       #    control_frame,
       #    text="Copiar Hexadecimal",
       #    command=self.copy_hexstream,
       #).pack(side="right", padx=6)

        output_frame = ttk.LabelFrame(
            scrollable_frame,
            text="Bitstream Generado (250 bits: matriz + 6 sinapsis + 1011)",
        )
        output_frame.pack(fill="x", padx=16, pady=10)

        self.order_var = tk.StringVar(value="row_major")
        order_selector_frame = ttk.Frame(output_frame)
        order_selector_frame.pack(anchor="w", padx=6, pady=4)
        ttk.Radiobutton(
            order_selector_frame,
            text="Orden Fila por Fila (R0C0...R0C9, R1C0...)",
            variable=self.order_var,
            value="row_major",
            command=self.update_bitstream,
        ).pack(side="left", padx=6)

        self.txt_bitstream = tk.Text(
            output_frame,
            height=4,
            width=70,
            font=("Consolas", 10),
            wrap="char",
        )
        self.txt_bitstream.pack(padx=6, pady=(6, 2), fill="both")

        ttk.Label(
            output_frame,
            text="Valor Hexadecimal (64 caracteres, 250 bits + 6 bits de relleno):",
            font=("Consolas", 9, "bold"),
        ).pack(anchor="w", padx=6)
        self.txt_hex = tk.Text(
            output_frame,
            height=2,
            width=70,
            font=("Consolas", 10),
            wrap="char",
        )
        self.txt_hex.pack(padx=6, pady=(2, 6), fill="both")

        self.lbl_stats = ttk.Label(
            output_frame,
            text="Total: 250 bits | Activos (1): 2 | Inactivos (0): 248",
            font=("Consolas", 9),
        )
        self.lbl_stats.pack(anchor="w", padx=6, pady=4)

        self.root.bind_all(
            "<MouseWheel>",
            lambda event: main_canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units",
            ),
        )
        self.root.bind_all(
            "<Button-4>",
            lambda event: main_canvas.yview_scroll(-1, "units"),
        )
        self.root.bind_all(
            "<Button-5>",
            lambda event: main_canvas.yview_scroll(1, "units"),
        )

    def toggle_cell(self, row, column):
        self.matrix[row][column] = 1 - self.matrix[row][column]
        self._update_button_color(row, column)
        self.update_bitstream()

    def toggle_synapse(self, index):
        self.synapses[index] = 1 - self.synapses[index]
        color = "#FF0702" if self.synapses[index] else "#FFFFFF"
        self.synapse_buttons[index].itemconfig(1, fill=color)
        self.update_bitstream()

    def _update_button_color(self, row, column):
        color = "#FF0702" if self.matrix[row][column] else "#FFFFFF"
        self.buttons[row][column].itemconfig(1, fill=color)

    def _get_bitstream_string(self):
        bits = []
        if self.order_var.get() == "row_major":
            for row in range(self.ROWS):
                for column in range(self.COLS):
                    bits.append(str(self.matrix[row][column]))
        else:
            for column in range(self.COLS):
                for row in range(self.ROWS):
                    bits.append(str(self.matrix[row][column]))
        return "".join(bits) + "".join(str(value) for value in self.synapses) + FIXED_TRAILER

    def update_bitstream(self):
        stream_str = self._get_bitstream_string()
        active_count = stream_str.count("1")
        payload_bits = stream_str + "0" * (8 - (len(stream_str) % 8))
        hex_value = format(
            int(payload_bits, 2),
            "0{}X".format(len(payload_bits) // 4),
        ) if stream_str else "0"

        self.txt_bitstream.delete("1.0", tk.END)
        self.txt_bitstream.insert(tk.END, stream_str)
        self.txt_hex.delete("1.0", tk.END)
        self.txt_hex.insert(tk.END, "0x{}".format(hex_value))
        self.lbl_stats.config(
            text="Total: 250 bits | Activos (1): {} | Inactivos (0): {}".format(
                active_count,
                NUMBER_OF_BITS - active_count,
            ),
        )

    def clear_all(self):
        for row in range(self.ROWS):
            for column in range(self.COLS):
                self.matrix[row][column] = 0
                self._update_button_color(row, column)
        for index in range(SYNAPSE_BITS):
            self.synapses[index] = 0
            self.synapse_buttons[index].itemconfig(1, fill="#FFFFFF")
        self.update_bitstream()

    def fill_all(self):
        for row in range(self.ROWS):
            for column in range(self.COLS):
                self.matrix[row][column] = 1
                self._update_button_color(row, column)
        for index in range(SYNAPSE_BITS):
            self.synapses[index] = 1
            self.synapse_buttons[index].itemconfig(1, fill="#FF0702")
        self.update_bitstream()

    def copy_bitstream(self):
        content = self.txt_bitstream.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo(
            "Copiado",
            "Bitstream de 250 bits copiado al portapapeles.",
        )

    def copy_hexstream(self):
        content = self.txt_hex.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(content[2:])
        messagebox.showinfo(
            "Copiado",
            "Valor hexadecimal copiado al portapapeles.",
        )


class SpikcoreGui(MosbiusMatrixConfigurator):
    def __init__(self, root):
        self.serial_connection = None
        self.serial_lock = threading.Lock()
        self.programmed = False
        self._generated_hex = None
        self.hex_var = None
        super().__init__(root)
        self._build_serial_controls()

    def update_bitstream(self):
        super().update_bitstream()
        generated_hex = self.txt_hex.get("1.0", tk.END).strip()
        generated_hex = generated_hex.replace("0x", "").replace("0X", "")
        if self.hex_var is not None:
            current_hex = self.hex_var.get().strip()
            if not current_hex or current_hex == self._generated_hex:
                self.hex_var.set(generated_hex)
        self._generated_hex = generated_hex

    def _build_serial_controls(self):
        frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Programación Raspberry Pi Pico",
        )
        frame.pack(fill="x", padx=16, pady=(0, 12))

        ttk.Label(frame, text="Puerto:").grid(row=0, column=0, padx=4, pady=4)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=12, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(frame, text="Actualizar", command=self.refresh_ports).grid(row=0, column=2, padx=4)
        self.connect_button = ttk.Button(frame, text="Conectar", command=self.connect)
        self.connect_button.grid(row=0, column=3, padx=4)
        self.disconnect_button = ttk.Button(frame, text="Desconectar", command=self.disconnect, state="disabled")
        self.disconnect_button.grid(row=0, column=4, padx=4)

        self.status_var = tk.StringVar(value="Desconectado")
        ttk.Label(frame, textvariable=self.status_var).grid(row=0, column=5, padx=8, sticky="w")

        ttk.Label(frame, text="Hex (250 bits):").grid(row=1, column=0, padx=4, pady=4)
        self.hex_var = tk.StringVar()
        self.hex_entry = ttk.Entry(frame, textvariable=self.hex_var, width=62)
        self.hex_entry.grid(row=1, column=1, columnspan=4, padx=4, pady=4, sticky="ew")
        ttk.Button(frame, text="R  Cambiar", command=lambda: self.run_action("R")).grid(row=1, column=5, padx=4)
        ttk.Button(frame, text="P  Programar", command=lambda: self.run_action("P")).grid(row=1, column=6, padx=4)
        ttk.Button(frame, text="L  Latch-up", command=lambda: self.run_action("L")).grid(row=1, column=7, padx=4)

        self.log = tk.Text(frame, height=5, width=100, state="disabled", font=("Consolas", 9))
        self.log.grid(row=2, column=0, columnspan=8, padx=4, pady=4, sticky="ew")
        for column in range(8):
            frame.columnconfigure(column, weight=1 if column == 1 else 0)

        self.hex_var.set(self.txt_hex.get("1.0", tk.END).strip().replace("0x", "").replace("0X", ""))
        self.refresh_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def refresh_ports(self):
        ports = _detect_ports()
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        if not ports:
            self.port_var.set("")
        self._append_log("Puertos disponibles: {}".format(", ".join(ports) or "ninguno"))

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert(tk.END, text.rstrip() + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _set_status(self, text):
        self.status_var.set(text)

    def connect(self):
        if serial is None:
            messagebox.showerror("Dependencia faltante", "Instala pyserial con: pip install pyserial")
            return
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Puerto serial", "Selecciona un puerto serial.")
            return
        try:
            connection = serial.Serial(port, BAUDRATE, timeout=1)
            time.sleep(2)
            connection.reset_input_buffer()
            self._enter_raw_repl(connection)
            self.serial_connection = connection
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")
            self._set_status("Conectado a {}".format(port))
            self._append_log("Conectado y listo en raw REPL.")
        except (serial.SerialException, RuntimeError) as exc:
            self._append_log("Error al conectar: {}".format(exc))
            messagebox.showerror("Error de conexión", str(exc))

    def _enter_raw_repl(self, connection):
        connection.write(b"\r\r\x03\x03")
        time.sleep(0.2)
        connection.reset_input_buffer()
        connection.write(b"\r\x01")
        time.sleep(0.2)
        response = connection.read(connection.in_waiting or 1).decode("utf-8", errors="ignore")
        if "raw REPL" not in response and ">" not in response:
            raise RuntimeError("La Pico no respondió con raw REPL.")

    def disconnect(self):
        connection = self.serial_connection
        self.serial_connection = None
        if connection is not None:
            connection.close()
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self._set_status("Desconectado")
        self._append_log("Puerto serial cerrado.")

    def _get_hex(self):
        candidate = self.hex_var.get().strip() or self.txt_hex.get("1.0", tk.END).strip()
        return normalize_hex(candidate)

    def run_action(self, action):
        try:
            hex_value = self._get_hex()
        except ValueError as exc:
            messagebox.showerror("Bitstream inválido", str(exc))
            return
        if self.serial_connection is None:
            messagebox.showerror("Puerto serial", "Conecta primero la Raspberry Pi Pico.")
            return
        if action == "L" and not self.programmed:
            messagebox.showwarning("Latch-up", "Primero ejecuta P para programar el bitstream.")
            return

        self.hex_var.set(hex_value)
        self._append_log("Enviando {}...".format(action))
        threading.Thread(
            target=self._execute_action,
            args=(action, hex_value),
            daemon=True,
        ).start()

    def _execute_action(self, action, hex_value):
        try:
            with self.serial_lock:
                script = build_remote_script(hex_value, action)
                self.serial_connection.write(script.encode("utf-8") + b"\x04")
                self.serial_connection.flush()
                response = self._read_until_ready(self.serial_connection, 30)
            self.root.after(0, self._action_completed, action, response)
        except (serial.SerialException, RuntimeError) as exc:
            self.root.after(0, self._action_failed, str(exc))

    @staticmethod
    def _read_until_ready(connection, timeout):
        deadline = time.time() + timeout
        buffer = ""
        while time.time() < deadline:
            if connection.in_waiting:
                buffer += connection.read(connection.in_waiting).decode("utf-8", errors="ignore")
                if "READY" in buffer:
                    if "Traceback" in buffer or "SyntaxError" in buffer:
                        raise RuntimeError(buffer)
                    return buffer
            else:
                time.sleep(0.05)
        raise RuntimeError("Tiempo agotado esperando respuesta READY de la Pico.")

    def _action_completed(self, action, response):
        self._append_log(response)
        if action == "P":
            self.programmed = True
        elif action == "R":
            self.programmed = False

    def _action_failed(self, error):
        self._append_log("Error: {}".format(error))
        messagebox.showerror("Error serial", error)

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    app_root.geometry("900x900")
    SpikcoreGui(app_root)
    app_root.mainloop()
