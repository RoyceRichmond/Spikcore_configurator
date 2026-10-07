from machine import Pin
from time import sleep_us, sleep_ms

#****

import array, time
from machine import Pin
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
    out(x, 1)                 .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")    .side(1)    [T1 - 1]
    jmp("bitloop")           .side(1)    [T2 - 1]
    label("do_zero")
    nop()                    .side(0)    [T2 - 1]
    wrap()

# Create the StateMachine with the ws2812 program, outputting on Pin(PIN_NUM).
sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(PIN_NUM))

# Start the StateMachine, it will wait for data on its FIFO.
sm.active(1)

# Display a pattern on the LEDs via an array of LED RGB values.
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

STATE_LED=25
START_PIN=7


# Periodo completo del reloj en microsegundos
# Ejemplo: 10 us = 100 kHz
CLK_PERIOD_US = 10000

NUMBER_OF_BITS = 240

# Tiempo antirrebote del botón
DEBOUNCE_MS = 30


# -----------------------------
# Inicialización de pines
# -----------------------------

data = Pin(DATA_PIN, Pin.OUT, value=0)
clk = Pin(CLK_PIN, Pin.OUT, value=0)
enable = Pin(EN_PIN, Pin.OUT, value=0)

# El botón se conecta entre GPIO 5 y GND.
# Sin presionar: 1
# Presionado: 0
latchup = Pin(LATCH_UP_PIN, Pin.IN, Pin.PULL_UP)

start = Pin(START_PIN, Pin.IN, Pin.PULL_UP)
status_led=Pin(STATE_LED, Pin.OUT, value=1)


def send_zero_bitstream():
    """
    Envía 240 bits de valor cero.

    La señal DATA permanece en cero y se generan
    240 ciclos de reloj en CLK.
    """

    half_period_us = CLK_PERIOD_US // 2

    if half_period_us < 1:
        half_period_us = 1

    data.value(0)

    for _ in range(NUMBER_OF_BITS):
        # Flanco de subida del reloj
        clk.value(1)
        
        pixels_fill(RED)
        pixels_show()

        sleep_us(half_period_us)

        # Flanco de bajada del reloj
        clk.value(0)
        
        pixels_fill(BLACK)
        pixels_show()
        
        sleep_us(half_period_us)


# -----------------------------
# Programa principal
# -----------------------------

enable_activado = False

latchup_previous = 1
start_previous = 1

status_led.value(1)
enable.value(0)

bit_stream_transmitted=0
while True:
    start_current = start.value()
    if start_previous == 1 and start_current == 0:
        sleep_ms(DEBOUNCE_MS)
        enable.value(0)        
        status_led.value(0)
        send_zero_bitstream()
        status_led.value(1)
        bit_stream_transmitted=1

    if bit_stream_transmitted == 1 and latchup_previous == 1 and latchup.value() == 0:
        sleep_ms(DEBOUNCE_MS)
        enable.value(1)
        pixels_fill(GREEN)
        pixels_show()

    latchup_previous = latchup.value()
    start_previous = start.value()
    sleep_ms(1)
