import argparse
import re
import sys
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
    help="Después de enviar el hex, manda P para programar el bitstream.",
  )
  parser.add_argument(
    "--latchup",
    action="store_true",
    help="Después de programar, manda L para activar latch-up.",
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

      print("Leyendo salida inicial del Pico...")
      read_lines(pico, timeout=1.5)

      print("\nEnviando string hexadecimal...")
      pico.write((hex_value + "\n").encode("utf-8"))
      pico.flush()

      wait_for_prompt(pico, "MENÚ DE CONTROL", timeout=5.0)

      if args.program:
        print("\nEnviando opción P...")
        pico.write(b"P\n")
        pico.flush()
        wait_for_prompt(pico, "MENÚ DE CONTROL", timeout=8.0)

      if args.latchup:
        print("\nEnviando opción L...")
        pico.write(b"L\n")
        pico.flush()
        read_lines(pico, timeout=3.0)

  except serial.SerialException as exc:
    print(f"Error de puerto serial: {exc}. Cierra Thonny u otra app que esté usando el puerto.")
    sys.exit(1)


if __name__ == "__main__":
  main()