from machine import Pin
from time import sleep_us, sleep_ms
import array, time
import rp2

# Configure the number of WS2812 LEDs, pins and brightness.
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
    jmp(not_x, "do_zero")    .side(1)    [T1 - 1]
    jmp("bitloop")            .side(1)    [T2 - 1]
    label("do_zero")
    nop()                      .side(0)    [T2 - 1]
    wrap()

# Create the StateMachine with the ws2812 program, outputting on Pin(PIN_NUM).
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
GREEN= (0,255,0)

# -----------------------------
# Configuración
# -----------------------------
DATA_PIN = 2
CLK_PIN = 3
EN_PIN = 4
LATCH_UP_PIN = 5

STATE_LED = 25
START_PIN = 7

CLK_PERIOD_US = 1000
NUMBER_OF_BITS = 240
DEBOUNCE_MS = 30

# -----------------------------
# Inicialización de pines
# -----------------------------
data = Pin(DATA_PIN, Pin.OUT, value=0)
clk = Pin(CLK_PIN, Pin.OUT, value=0)
enable = Pin(EN_PIN, Pin.OUT, value=0)

latchup = Pin(LATCH_UP_PIN, Pin.IN, Pin.PULL_UP)
start = Pin(START_PIN, Pin.IN, Pin.PULL_UP)
status_led = Pin(STATE_LED, Pin.OUT, value=1)


def send_zero_bitstream():
    half_period_us = CLK_PERIOD_US // 2
    if half_period_us < 1:
        half_period_us = 1
    data.value(0)
    for _ in range(NUMBER_OF_BITS):
        clk.value(1)
        pixels_fill(RED)
        pixels_show()
        sleep_us(half_period_us)
        clk.value(0)
        pixels_fill(BLACK)
        pixels_show()
        sleep_us(half_period_us)


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
        sleep_us(half_period_us)

        clk.value(0)
        pixels_fill(BLACK)
        pixels_show()
        sleep_us(half_period_us)

# -----------------------------
# Programa principal interactivo
# -----------------------------
bit_stream_transmitted = 0
status_led.value(1)
enable.value(0)
pixels_fill(BLACK)
pixels_show()


# -----------------------------
# ENTRADA DINÁMICA INICIAL (DESDE LA PC)
# -----------------------------
print("----------------------------------------")
print("Esperando valor hexadecimal de 240 bits...")
print("----------------------------------------")

variable = input("Ingresa el string hex (60 caracteres): ").strip()

if len(variable) != 60:
    print("¡Advertencia! El valor no mide 60 caracteres. Asegúrate de que sean 240 bits.")

# Se guarda el primer valor en memoria para usarlo de inmediato
variable_bytes = bytes.fromhex(variable)
print("¡Valor inicial cargado y convertido a bytes con éxito!\n")

while True:
    print("\n--- MENÚ DE CONTROL ---")
    print("R - Ingresar / Cambiar string hexadecimal (240 bits)")
    print("P - Programar y enviar bitstream actual")
    print("L - Activar Latch-up (Verde)")
    
    choice = input("Elige una opción (R / P / L): ").strip().upper()
    
    if choice == "R":
        pixels_fill(BLACK)
        pixels_show()
        print("\n----------------------------------------")
        print("Ingresa el nuevo valor hexadecimal de 240 bits:")
        print("----------------------------------------")
        variable_hex = input("String hex (60 caracteres): ").strip()
        
        if len(variable_hex) != 60:
            print("⚠️ ¡Advertencia! El valor no mide 60 caracteres exactos.")
        
        try:
            variable_bytes = bytes.fromhex(variable_hex)
            bit_stream_transmitted = 0 
            print("✅ ¡Nuevo valor cargado y convertido a bytes con éxito!\n")
        except ValueError:
            print("❌ Error: El texto ingresado contiene caracteres hexadecimales inválidos.\n")
            variable_bytes = None

    elif choice == "P":
        if variable_bytes is None:
            print("⚠️ Primero debes ingresar un string hexadecimal usando la opción 'R'.\n")
            continue
            
        sleep_ms(DEBOUNCE_MS)
        enable.value(0)        
        status_led.value(0)
        
        send_bitstream(variable_bytes)
        
        status_led.value(1)
        bit_stream_transmitted = 1
        print("🚀 ¡Bitstream enviado con éxito!\n")

    elif choice == "L":
        if bit_stream_transmitted == 1:
            sleep_ms(DEBOUNCE_MS)
            enable.value(1)
            pixels_fill(GREEN)
            pixels_show()
            print("🟢 ¡Latch-up activado y LEDs en verde!\n")
        else:
            print("⚠️ Primero debes enviar el bitstream ('P') antes de hacer Latch-up ('L').\n")
            
    else:
        print("❌ Opción inválida. Por favor usa 'R', 'P' o 'L'.\n")
        
    sleep_ms(1)
