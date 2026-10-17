# Group 39 gesture to speech project

The main glove system is now implemented under `glove/`: ESP32 firmware, a native Windows app, calibration, labeled recordings, grouped model training, live recognition, phrase output, local speech and a simulator. Your earlier CV work remains under `CV/`.

**Start now:** double-click `Start-Glove-Demo.cmd`. The portable executable opens synthetic input without installing Python. Use `Start-Glove.cmd` for the regular app. The simulated word mappings are engineering demonstrations, not verified ISL/ASL signs.

Read `glove/docs/Gesture_Glove_Manual.pdf` for the illustrated 17-chapter build/use instructions and `glove/docs/Gesture_Glove_Manual.docx` for an editable copy. `glove/docs/BUILD_JOURNAL.md` explains each implementation step and its verification. `glove/docs/REPORT_TEMPLATE.md` has the report structure and identifies measurements still needed.

## Your hardware and the next step

Confirmed: ESP32, MPU6050 and a module described as TP4065. Begin with USB power. Identify the last module before battery wiring. The physical build still needs five bend sensors (or pots for an electronics test), dividers, glove mounting and real labeled recordings.

The recommended first wiring uses five direct ESP32 ADC1 inputs, avoiding a multiplexer:

| Signal | ESP32 pin |
| --- | --- |
| Thumb divider | GPIO32 |
| Index divider | GPIO33 |
| Middle divider | GPIO34 |
| Ring divider | GPIO35 |
| Little divider | GPIO36 / VP |
| MPU6050 SDA / SCL | GPIO21 / GPIO22 |

Each divider is `3.3 V -> flex sensor -> junction -> fixed resistor -> GND`; the junction goes to its analog pin. Use a breakout verified for 3.3 V operation and a common ground. Follow the manual's voltage and continuity checks before connecting inputs. The build targets the original ESP32 DevKit family; check the actual chip marking.

## Flash and collect

From PowerShell in this project folder, after installing 64-bit Python 3.12 on a fresh development computer:

```powershell
.\Setup-Glove.ps1
.\glove\Flash-ESP32.ps1 -Port COM7 -Environment esp32-direct
```

Replace COM7 with the real port and disconnect the app during flashing. Then connect at 115200, enter a participant pseudonym, capture open/closed hand and save calibration. Record every label and REST across independent people/visits. Train with participant grouping, inspect the metrics, then load the trusted model.

The app refuses mixed synthetic/real datasets and models. A model is not supplied as a real glove classifier before actual sensor recordings exist. A speech event needs 0.45 seconds of consistent above-threshold input; repeating the same gesture requires sustained REST. Invalid input clears recognition.

## Verification and rebuild

```powershell
.\glove\.venv\Scripts\python.exe -m unittest discover -s .\glove\tests -v
.\glove\.venv\Scripts\python.exe .\glove\tools\demo_check.py
.\glove\.venv\Scripts\python.exe .\glove\app.py --full-check .\glove\artifacts\full_check
.\glove\Invoke-Firmware.ps1 -Environment @('esp32-direct','esp32-usb')
.\glove\tools\build.ps1
```

The portable transfer archive includes the entire app folder, source, documentation, compiled firmware and software-verification evidence. Raw participant recordings and project virtual environments are excluded. A target computer may need the USB bridge driver specific to its board.

## Current boundaries

Software simulation and compilation are verified; physical sensor accuracy, flashing, wearability, wireless range, actual audio playback and battery power need the device tests in the manual. The camera archive classifier is an independent alphabet experiment, and no automatic CV failsafe is claimed. See the journal for exact verification results and source references.
