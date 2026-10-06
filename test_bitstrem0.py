from machine import Pin
from time import sleep_us, sleep_ms


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
CLK_PERIOD_US = 10

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
        sleep_us(half_period_us)

        # Flanco de bajada del reloj
        clk.value(0)
        sleep_us(half_period_us)


# -----------------------------
# Programa principal
# -----------------------------

enable_activado = False

latchup_previous = 1
start_previous = 1

status_led.value(1)
enable.value(0)
while True:
    start_current = start.value()
    if start_previous == 1 and start_current == 0:
        sleep_ms(DEBOUNCE_MS)
        enable.value(0)        
        status_led.value(0)
        send_zero_bitstream()
        status_led.value(1)

    if latchup_previous == 1 and latchup.value() == 0:
        sleep_ms(DEBOUNCE_MS)
        enable.value(1)

    latchup_previous = latchup.value()
    start_previous = start.value()
    sleep_ms(1)