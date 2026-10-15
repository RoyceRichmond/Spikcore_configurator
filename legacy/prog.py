import argparse
import re
import sys
import textwrap
import time

import serial
from serial.tools import list_ports


HEX_LENGTH = 60
BAUDRATE = 115200


def normalize_hex(value):
    value = value.strip().replace(" ", "")
    if value.lower().startswith("0x"):
        value = value[2:]

    if len(value) != HEX_LENGTH:
        raise ValueError(f"El valor debe tener exactamente {HEX_LENGTH} caracteres hexadecimales.")

    if not re.fullmatch(r"[0-9a-fA-F]{60}", value):
        raise ValueError("El valor contiene caracteres que no son hexadecimales.")

    return value.upper()


def detect_port(preferred_port):
    if preferred_port:
        return preferred_port

    keywords = ("micropython", "pico", "raspberry pi", "usb serial")
    ports = list(list_ports.comports())

    for port in ports:
        haystack = " ".join(
            part for part in [port.description, port.manufacturer, port.hwid, port.name] if part
        ).lower()
        if any(keyword in haystack for keyword in keywords):
            return port.device

    if ports:
        return ports[0].device

    raise RuntimeError("No se encontró ningún puerto serial disponible.")


def read_lines(ser, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            line = ser.readline().decode("utf-8", errors="ignore")
            if line:
                print(line, end="")
        else:
            time.sleep(0.05)


def wait_for_prompt(ser, marker, timeout=5.0):
    deadline = time.time() + timeout
    buffer = ""
    while time.time() < deadline:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
            buffer += chunk
            print(chunk, end="")
            if marker in buffer:
                return buffer
        else:
            time.sleep(0.05)
    return buffer


def enter_raw_repl(ser):
    ser.reset_input_buffer()
    ser.write(b"\r\r\x03\x03")
    time.sleep(0.2)
    read_lines(ser, timeout=0.5)
    ser.write(b"\r\x01")
    time.sleep(0.2)
    read_lines(ser, timeout=0.5)


def build_remote_script(hex_value, program_bitstream, latchup):
    return textwrap.dedent(
        f'''
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
            out(x, 1)                  .side(0)    [T3 - 1]
            jmp(not_x, "do_zero")     .side(1)    [T1 - 1]
            jmp("bitloop")            .side(1)    [T2 - 1]
            label("do_zero")
            nop()                      .side(0)    [T2 - 1]
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
        CLK_PERIOD_US = 1000
        NUMBER_OF_BITS = 240

        data = Pin(DATA_PIN, Pin.OUT, value=0)
        clk = Pin(CLK_PIN, Pin.OUT, value=0)
        enable = Pin(EN_PIN, Pin.OUT, value=0)
        status_led = Pin(STATE_LED, Pin.OUT, value=1)

        def send_bitstream(data_bytes):
            half_period_us = CLK_PERIOD_US // 2
            if half_period_us < 1:
                half_period_us = 1

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

        variable = {hex_value!r}
        variable_bytes = bytes.fromhex(variable)

        enable.value(0)
        status_led.value(0)
        pixels_fill(BLACK)
        pixels_show()

        if {program_bitstream!r}:
            send_bitstream(variable_bytes)
            print("Bitstream enviado")

        if {latchup!r}:
            enable.value(1)
            pixels_fill(GREEN)
            pixels_show()
            print("Latch-up activado")

        print("READY")
        '''
    )


def main():
    parser = argparse.ArgumentParser(
        description="Envía un string hexadecimal de 60 caracteres a la Raspberry Pi Pico por USB serial."
    )
    parser.add_argument("hex_value", nargs="?", help="String hexadecimal de 60 caracteres.")
    parser.add_argument("--port", help="Puerto serial, por ejemplo COM8.")
    parser.add_argument("--baudrate", type=int, default=BAUDRATE, help="Baudrate del enlace serial.")
    parser.add_argument(
        "--program",
        action="store_true",
        help="Después de enviar el hex, manda el bitstream en la Pico.",
    )
    parser.add_argument(
        "--latchup",
        action="store_true",
        help="Después de programar, activa latch-up en la Pico.",
    )
    args = parser.parse_args()

    hex_value = args.hex_value or input("Ingresa el string hex de 60 caracteres: ")
    try:
        hex_value = normalize_hex(hex_value)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    try:
        port = detect_port(args.port)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(f"Conectando a {port}...")

    try:
        with serial.Serial(port, args.baudrate, timeout=1) as pico:
            time.sleep(2)
            pico.reset_input_buffer()

            print("Entrando en raw REPL...")
            enter_raw_repl(pico)

            remote_script = build_remote_script(hex_value, args.program, args.latchup)

            print("Ejecutando script en la Pico...")
            pico.write(remote_script.encode("utf-8") + b"\x04")
            pico.flush()

            response = wait_for_prompt(pico, "READY", timeout=20.0)
            if "Traceback" in response or "SyntaxError" in response:
                raise RuntimeError("La Pico devolvió un error al ejecutar el script remoto.")

    except serial.SerialException as exc:
        print(f"Error de puerto serial: {exc}. Cierra Thonny u otra app que esté usando el puerto.")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()