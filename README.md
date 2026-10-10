# Spikcore_configurator
The Spikcore has a 24X10 switch matrix, this needs to be reconfigured to make new circuits.

This Repo contains two scripts:

- gui_config.py: This script render a gui with buttons to select which cells connect to which buss and then the ios
- main.py: This script is uploadede to a raspberry pi pico, and uses the input from the gui to upload the bitstream and reconfigure switch matrix on the asic.


The upload process is inspired by the [MOSbius project](https://github.com/Jianxun/MOSbius_MicroPython_Flow/tree/main)
