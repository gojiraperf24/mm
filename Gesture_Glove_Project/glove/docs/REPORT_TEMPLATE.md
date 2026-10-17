# Gesture to Speech Glove Prototype

ID1050A Engineering Design, IIT Palakkad, Group 39

Team lead: Shourya Shamsher Rana. Members from the supplied proposal: Tarun Padmanabhan, Sandip Mondal, Siddamshetty Mani, Susruti Sristi and Dhanunjay Nayak. Verify spelling and author contributions before submission.

## Abstract

We implemented a small-vocabulary gesture-to-speech prototype consisting of ESP32 sensor firmware and a local Windows recognition application. The one-glove configuration measures five bend signals and an MPU6050 acceleration/rotation sample. Per-person calibration normalizes the measurements. A participant-separated Random Forest training pipeline provides a confidence threshold and held-out evaluation. A time gate and REST rearm reduce repeated speech events. The desktop interface supports English and Hindi text and local speech engines, with optional recorded-word output on a DFPlayer.

**Complete after bench testing:** physical glove construction, selected vocabulary and its review status, number of participants/visits, held-out accuracy, coverage, false activation rate, end-to-end latency, comfort observations and the final power configuration.

## Problem and scope

Explain the communication situation the prototype targets. Specify the final static vocabulary and why these measurements can separate it. Describe team-defined mappings as team-defined mappings. Do not present them as verified ISL/ASL unless reviewed by a competent signer. Continuous signing, grammar, facial expression and unrestricted translation are outside the current implementation.

## Final design

Describe the actual assembled divider topology, resistor choices and sensor construction. Include the measured pin map, board model, IMU axis convention, mounting photographs and an annotated enclosure drawing. State whether direct ADC channels or the multiplexer was used. Recognition runs on the laptop; firmware performs sensing and optional audio-command output.

Use the manual's diagrams as architecture illustrations. Replace generic mechanical drawings with measurements of the built device. Identify the battery module and regulator if battery power is actually implemented.

## Calibration and features

Report the open and closed medians for every finger, sensor span and repeatability across wearers. Explain endpoint normalization and the eleven features per hand. Record motion rejection parameters, capture duration, gyro bias procedure and model feature version. Do not claim a yaw estimate from this gravity-direction implementation.

## Data collection and evaluation design

Document consenting participant pseudonyms, counts by label, sessions, trial counts and physical variations. Explain how the entire participant or participant/session group stays in one partition. Include the saved dataset/model SHA256 hashes and partition manifest. Explain any excluded recordings without tuning the test partition.

## Results requiring real measurements

| Measurement | Actual result | Evidence file |
| --- | --- | --- |
| Hardware dataset rows and people | TO MEASURE | samples.csv and consent log |
| Raw held-out accuracy | TO MEASURE | glove_model.metrics.json |
| Rejection coverage | TO MEASURE | glove_model.metrics.json |
| Accepted accuracy | TO MEASURE | glove_model.metrics.json |
| Per-class precision and recall | TO MEASURE | metrics and confusion CSV |
| False word events per idle minute | TO MEASURE | timed acceptance log |
| Unknown/transition false events | TO MEASURE | timed acceptance log |
| Text latency median and p95 | TO MEASURE | timestamped trial observations |
| Audible latency median and p95 | TO MEASURE | timed audio observations |
| Wear comfort and mechanical fit | TO MEASURE | participant notes and photos |
| Radio range and battery runtime if used | TO MEASURE | bench log |

Software checks and synthetic integration results belong in a separate implementation-verification subsection. Perfect synthetic accuracy is not evidence of physical gesture recognition. The pre-existing archive HOG/SVM metrics are also separate from glove metrics.

## Limitations and discussion

Discuss finger-spread ambiguity, unobservable absolute yaw, soft-sensor hysteresis/drift, participant variation, unknown-pose overconfidence and the limits of a closed-set classifier. Describe rejected coverage as well as accuracy. Identify which optional hardware features were physically verified. Report inaccurate predictions and uncomfortable mounts alongside successes.

## Cost and contributions

Use actual receipts/current quotes, not the source plan's old estimates. Attribute tasks actually completed by each member. Include software/firmware versions, assembly dates, data-recording dates and lessons from failed iterations.

## Conclusion

Complete with the demonstrated result and measurements, then identify the next improvements justified by the data. Avoid claims of complete sign-language translation or clinical/accessibility effectiveness from a classroom demonstration.

## References

Use the manufacturer and method references in Gesture_Glove_Manual.pdf. Add the team's vocabulary-review source and actual component documentation.
