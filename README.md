# Spikcore_configurator
The Spikcore has a 24X10 switch matrix, this needs to be reconfigured to make new circuits.

This Repo contains two scripts:

- gui_prog.py: This script render a gui with buttons to select which cells connect to which buss and then the ios and programming
- main.py: This script is uploadede to a raspberry pi pico, and uses the input from the gui to upload the bitstream and reconfigure switch matrix on the asic.

The upload process is inspired by the [MOSbius project](https://github.com/Jianxun/MOSbius_MicroPython_Flow/tree/main)

## Aplicación unificada

1. Ejecuta `python gui_prog.py`.
2. Selecciona el puerto COM de la Raspberry Pi Pico y pulsa **Conectar**.
3. Selecciona las celdas de la matriz y configura las seis sinapsis para generar el bitstream de 250 bits. Los últimos cuatro bits son fijos (`1011`).
4. Usa **R Cambiar** para cargar el hexadecimal en la Pico, **P Programar** para transmitirlo y **L Latch-up** para activarlo.

## Packages
The program requieres an additional library named pyserial for the serial comunication with the raspberry pi pico
```bash
pip install pyserial
```
