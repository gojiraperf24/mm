# Build journal for Group 39

Implementation date: 3 October 2026. This journal describes the work performed, the reason for each step, its checks and the remaining device work.

## Step 1 Read the actual project and choose an achievable first build

Read the root proposal DOCX and prototype-plan PDF, the existing CV README/vocabulary and prior project decisions. The proposal uses ESP32, ten flex sensors, two IMUs, a mux and laptop/phone speech. The later plan uses Nano, HC-05 and DFPlayer. Tarun confirmed an ESP32 and MPU6050, so the primary path uses them. The first version has one glove and eight static team-defined messages plus REST. This avoids waiting for a second glove or an Android application to demonstrate the main pipeline.

The code retains Nano and two-hand options rather than forcing a hardware purchase. An added direct-input ESP32 configuration uses GPIO32/33/34/35/36, so a one-glove prototype needs no mux. The old source documents were preserved.

## Step 2 Define the wire protocol before attaching the classifier

Created `core.py` and `PROTOCOL.md`. Each complete ASCII packet carries schema G1, device sequence, uptime, hand count, ADC range, IMU success bits and the measured channels. A versioned contract means firmware, collection and recognition can reject incompatible data instead of silently interpreting another signal as a finger.

Checks covered round trip, two hands, malformed length, NaN, unit limits, missing IMU bits, counter range, replay/reset and rollover. Invalid readings suppress live output. The serial reader uses a bounded queue; it rejects corrupt lines and discards a backlog rather than debouncing old data into words.

## Step 3 Make calibration and recognition use exactly the same features

Created endpoint captures with medians, stable-capture checks, per-finger span checks, rail checks, gyro bias and JSON profiles. The normalization formula handles both increasing and decreasing voltage. Each hand yields five normalized bends, gravity direction and angular-rate features. Movement is rejected before labeling a static pose.

Why: training on one feature calculation and predicting with another is a frequent integration failure. Calibration also needs to follow the actual wearer and glove fit. Unit tests covered reversed divider direction, rails, invalid span, movement, short captures, file identity and different hardware layouts. Native UI tests exercised both capture buttons and saving their resulting calibration.

## Step 4 Store real examples with their provenance

Created `dataset.py` and the app's recording workflow. A trial has a preparation countdown, fixed target label, bounded sample rate, automatic burst stop and immediate disk flushes. Each CSV row identifies participant, visit, trial, feature/vocabulary/calibration versions and hardware versus synthetic origin.

Why: adjacent sensor readings are correlated, and undocumented changes can invalidate an experiment. The writer refuses mixed layouts or synthetic/real samples. Native UI testing confirmed that changing the visible label during recording does not relabel an in-progress trial. No participant sensor recordings were fabricated.

## Step 5 Train with an honest evaluation boundary

Created `training.py`: dataset audit, participant or session grouping, disjoint train/validation/test partitions, balanced 200-tree Random Forest, validation cutoff search, model save, metrics, confusion and partition CSVs. The final model is trained only on training groups. Threshold selection never examines test accuracy.

Why: randomly splitting adjacent frames can put essentially the same gesture hold on both sides of evaluation. Entire groups stay separate here. The code rejects exact feature duplicates across groups, though this does not prove the absence of all near duplicates or correlated source conditions.

The integration check generated **explicitly synthetic** data: six artificial participants, nine classes, 40 samples each, 2,160 rows. It fit 1,080 rows, validated 360 and tested 720, reloaded the model and produced all eight expected word events. Perfect accuracy on those clean simulated patterns is only a software check. It is not glove performance and is not reported as such in the manual/report template.

## Step 6 Make speech an event rather than a stream of repeated words

Created `EventGate`: 0.45-second active-pose hold, confidence cutoff and 0.35-second REST rearm. A held gesture emits once. A different stable gesture can emit a new word directly. Invalid input does not rearm the last word. A long sample gap resets the candidate.

Why: a classifier returning FIST 25 times per second must not speak Yes 25 times per second. Checks covered sustained gesture, low score, short/long REST, faults, transitions, stream gaps and immediate clearing of a stale display.

## Step 7 Build the actual native workflow

Created `app.py` with Live recognition, Calibrate and record, Train and evaluate and Vocabulary tabs. The app displays finger gauges, raw candidate score, stable outcome, phrase history and explanations. Training and speech run outside the UI thread. Data stay local under the application's `user_data` directory.

Native Tk smoke verification exercised synthetic recognition, and additional controller tests exercised recording and calibration controls. The source and packaged executable were run in a desktop-capable session. The restricted execution sandbox could not initialize Tk; this was an execution-permission boundary rather than a missing Tcl installation. The packaging pass was repeated with access to the working desktop runtime so Tk was actually included.

## Step 8 Implement and compile the device firmware

Created `firmware/src/main.cpp` and pinned PlatformIO configurations. The sensor firmware scans direct ADC channels or mux channels; mux mode waits after switching, discards the first conversion and averages four readings. MPU ranges are ±2 g and ±250 degrees/s. A checked complete I2C read is decoded directly so bus faults cannot use stale library data. Packet values use g and degrees/s.

All seven environments compiled: esp32-direct, esp32-usb, esp32-bluetooth, esp32-two-hands, esp32-audio, nano-usb and nano-bluetooth. The actual build log records memory usage and success. ESP32 direct firmware is approximately 305 KB; the baseline Nano USB build uses 673 of 2,048 RAM bytes and 14,212 of 30,720 flash bytes.

Windows fixes are preserved in the development scripts: PlatformIO 6.1.18 did not quote a package-script Python path with spaces; `tools/pio.py` corrects that exact prefix. The ESP32 GCC toolchain also failed under the spaced path; `Invoke-Firmware.ps1` uses and removes a temporary unused drive alias. Missing esptool Python dependencies are explicit in build requirements. No connected COM port was present, and Tarun cannot connect the board during this session, so no upload or physical sensor operation is claimed.

## Step 9 Complete local English and Hindi speech

The actual Windows speech enumeration returned David Desktop and Zira Desktop, both English. Created a persistent PowerShell speech worker using JSON over stdin and explicit default-audio output. Input phrases never become shell code.

Added an unmodified portable eSpeak NG 1.52.0 runtime from the official release for offline Hindi and English fallback. The MSI was extracted into the project without a machine-wide installation. Runtime DLLs, upstream licensing information and corresponding source are included. The worker renders local WAV files and plays them without blocking sensor input.

The silent waveform check exported all eight English and eight Hindi phrases and confirmed valid nonempty PCM audio. The full application check also rendered English and Hindi. This verifies synthesis output, not human-rated pronunciation, speaker audibility or DFPlayer playback. The compact synthetic Hindi voice should be listened to by the team; polished recorded clips remain an option.

## Step 10 Supply the physical build and testing documents

Created the parameterized wrist-enclosure SCAD, an illustrated 17-chapter Word/PDF manual, Markdown manual, protocol contract, report template and blank acceptance log. The manual explains the action, reason, expected result and failure response at each stage. It includes wiring, calibration, learning concepts, data requirements, limitations, Bluetooth/audio and final experiments.

The bundled DOCX renderer reported missing LibreOffice on Windows. The manual was rendered through a hidden installed Microsoft Word instance, exported to PDF, rasterized with bundled Poppler and visually reviewed. The editable DOCX remains available. No enclosure print, sensor fabrication or physical fit is represented as verified.

## Step 11 Verify and prepare the transfer package

Ran 38 automated tests, including four native UI-controller tests, plus the synthetic integration and portable executable checks. The final evidence is under `artifacts/`. The package contains the complete executable folder, firmware images, source and documentation. It excludes project virtual environments, compiler caches and participant recordings.

The first portable full-pipeline check exposed a dynamically imported SciPy array-API FFT module that PyInstaller had omitted. Added collection of SciPy and scikit-learn array-API submodules to the reproducible build script, rebuilt the executable and reran the complete check. The corrected executable exited successfully after training and reloading the synthetic model, emitting all eight expected gesture events, checking the native interface and rendering English/Hindi waveforms. This catches a packaging failure that a simple window-opening check would miss.

The app can run on another Windows x64 computer without a Python installation. Firmware development/setup still needs the documented toolchain and a board USB driver where appropriate. Keep the whole app folder and its third-party notices together. Hash manifests identify the packaged files.

## Step 12 Finish the work that requires your device

1. Identify the exact ESP32 variant and battery-module markings.
2. Build and meter-check five sensor dividers and the MPU6050 wiring; use pots only for the first electronics check if necessary.
3. Upload the matching firmware and verify each real channel before mounting the glove.
4. Fit, calibrate and collect independent labeled recordings; freeze an actually distinguishable vocabulary.
5. Train and perform final held-out, idle, unknown, fault and latency trials.
6. Review English/Hindi pronunciation and audibility. Physically test wireless and wearable audio only if used.
7. Measure/print the enclosure, complete the bench evidence and fill the report's measured-results table.

The exact battery module called TP4065 remains unidentified. USB power is the delivered baseline. A module name alone is not enough to specify charging, protection, regulation or power-path wiring.
