# Sensor protocol and feature contract

Firmware sends newline-delimited ASCII at 115200 baud over USB. Original ESP32 SPP exposes the same byte stream. The Nano HC-05 alternative uses 9600 baud and 250 ms scans.

```text
G1,sequence,millis,hands,adc_max,imu_mask,[eleven values per hand]
```

Each hand supplies `thumb,index,middle,ring,little,ax,ay,az,gx,gy,gz`. Flex values are ADC counts; acceleration is **g** and angular rate is **degrees per second**. A timestamp covers a full sequential sensor scan. It is not a claim that every channel was sampled at exactly the same instant. At two hands, the first hand is channels 0–4/address 0x68 and the second channels 5–9/address 0x69.

`sequence` and `millis` are uint32 counters. The host accepts wraparound and rejects duplicate samples, resets or intervals over 500 ms. `hands` is 1 or 2; `adc_max` is 4095 (ESP32) or 1023 (Nano). Each IMU sets one bit in `imu_mask` when its complete I2C sample succeeds. All configured IMU bits must be present. A sensor read failure must never masquerade as zero-valued valid data.

Startup/command messages begin with `#I`, `#A` or `#E`; they are information, acknowledgements or errors, and never sensor samples. The host limits lines to 1000 bytes and discards accumulated stale queues before resuming live recognition.

## Host features

Feature version: `flex5_gravity3_gyro3_v1`. For each hand, in order:

1. Five endpoint-normalized bends, `(raw-open)/(closed-open)`. Both divider directions work. A reading outside -0.25..1.25 before clipping is rejected; valid values clip to 0..1. Values near ADC rails are rejected.
2. Three acceleration components divided by acceleration-vector magnitude, preserving wrist tilt. Magnitude must be 0.85..1.15 g.
3. Three gyro components after stationary bias removal, divided by 250 degrees/s. Motion over 35 degrees/s suppresses a static gesture.

Do not reinterpret these values as true joint angles, absolute yaw or motion recognition. Changing calculations requires a new feature version and compatible data/model.

## Output commands

`PING\n` returns `#A,PONG`. `PLAY n\n` accepts tracks 1..199 only if the DFPlayer firmware flag is enabled. Tracks 1..99 represent English, 101..199 Hindi. REST never sends a command. Frames target the player's numbered `/mp3/NNNN.mp3` files. Firmware rate-limits commands 600 ms apart. The acknowledgement means a UART command was sent; it does not prove playback.

## Files and integrity

CSV recordings contain label, participant, session, trial, UTC timestamp, source, hands, feature version, vocabulary and calibration SHA256 fingerprints, then feature columns. Source is `hardware` or `synthetic`; they cannot mix. Calibration is JSON and model is trusted local joblib serialization. Training saves metrics, grouped partitions and a confusion matrix. Only load models you created or trust, because joblib is executable serialization.
