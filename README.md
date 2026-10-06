# Spikcore_configurator
The Spikcore has a 24X10 switch matrix, this needs to be reconfigured to make new circuits.

This Repo contains two scripts:

- configurator_gui.py: This script render a gui with buttons to select which cells connect to which buss and then the ios
- bitstream.json: is the bitstream that is uploaded to the switch matrix
- rasp_upload: This script controls a raspberry pi pico to upload the bitstream and enable the chip
The upload process is inspired by the [MOSbius project](https://github.com/Jianxun/MOSbius_MicroPython_Flow/tree/main)
