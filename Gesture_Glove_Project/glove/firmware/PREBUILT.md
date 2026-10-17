# Compiled firmware supplied with the transfer package

The `prebuilt/` directory in the transfer package contains images from all seven successful builds. These images have not been uploaded or tested against physical sensors. Read the manual and identify the chip/board before selecting one.

| Environment | Intended wiring |
| --- | --- |
| esp32-direct | Original ESP32 DevKit, one glove, five direct ADC1 inputs; recommended baseline |
| esp32-usb | Original ESP32 DevKit, one glove through an analog multiplexer |
| esp32-bluetooth | Same multiplexer wiring plus ESP32 Classic Bluetooth SPP |
| esp32-two-hands | Two sets of flex sensors through the multiplexer and two MPU6050 addresses |
| esp32-audio | Multiplexer wiring plus optional DFPlayer serial control |
| nano-usb | ATmega328P Nano, direct analog inputs |
| nano-bluetooth | Nano plus HC-05; slower sensor packets over the 9600-baud Bluetooth link |

Normal USB monitoring uses 115200 baud. ESP32-S2/S3/C3 boards need their own verified pin assignments and build targets; do not upload an `esp32dev` image to them.

Use the documented `Flash-ESP32.ps1` / `Invoke-Firmware.ps1` workflow. PlatformIO selects upload addresses and bootloader settings for the configured board. Retain the ESP32 bootloader and partition files with their matching firmware environment. The shared `boot_app0.bin` comes from the pinned Arduino ESP32 framework. Nano HEX images use the configured Nano bootloader; check whether your board actually uses the old or new bootloader before uploading.

Source and pinned settings are included so a future change can be rebuilt. None of these images contains a trained gesture model: the firmware streams measurements to the laptop application.
