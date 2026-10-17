# Hand sign CV add-on

**Archive update:** For the labeled 28x28 alphabet pictures in `CV/archive`, see [ARCHIVE_TRAINING.md](ARCHIVE_TRAINING.md). They require a separate image-based HOG/SVM model because the sampled pictures did not yield MediaPipe landmarks. Its training command is `train_archive.py`, and its predictor is `predict_archive.py`. The original landmark workflow below remains separate.

This is an independent webcam demonstration for **Gesture to Speech Gloves for Sign Language**. The glove's flex sensors and IMU remain its primary recognition input. This program needs no glove, serial connection, Bluetooth, speech service or sensor model, and the glove needs none of these CV files to operate.

The supplied proposal describes CV as a failsafe. The current request supersedes that scope: this implementation produces its own predictions for a separate demonstration and optional later comparison. The source documents were read as project context; they were not changed.

Start with one visible hand and 12 static demo poses plus a learned `REST` class. These poses are **engineering placeholders, not a claimed ISL/ASL vocabulary or full sign-language translation**. Neither reference document supplies an exact sign list. Before collecting the final dataset, replace them with the team's agreed single-hand static glove signs in `signs.json`, and verify their meaning and execution with a competent signer. Motion, two-hand relationships, facial expression and body position are outside this first version.

## Stage 1: Understand the architecture

```text
TRAINING
Webcam -> MediaPipe 21 points -> normalized 83 features -> labeled CSV
                                                     -> grouped train/validation/test
                                                     -> Random Forest + saved threshold

LIVE DEMO
Webcam -> same landmarks/features -> saved classifier -> confidence gate
                                                    -> consistent-frame gate
                                                    -> label on screen / optional CSV log

SEPARATE MAIN SYSTEM
Flex sensors + IMU -> glove classifier -> glove speech output
```

MediaPipe supplies a pretrained detector for locating hand joints. Our sign classifier is a small Random Forest trained from your examples; no custom deep-learning training is needed. A shared `hand_features.py` keeps collection and inference numerically identical.

The requested four main scripts are included. Small helpers separate camera handling, common file checks and smoothing so each file has a clear purpose:

```text
hand_sign_cv/
  collect_data.py
  hand_features.py
  train_model.py
  realtime_predict.py
  tracking.py                 # stage 2 standalone tracking demo
  prediction.py               # threshold and smoothing logic
  common.py                   # paths, vocabulary, CSV validation
  setup_model.py              # one-time detector download
  signs.json                  # editable label -> pose description
  requirements.txt
  test_pipeline.py
  dataset/hand_signs.csv       # header only until you collect data
  models/hand_landmarker.task # Google's pretrained detector
  models/hand_sign_classifier.pkl            # generated after training
  models/hand_sign_classifier.metrics.json   # generated evaluation
  models/hand_sign_classifier.confusion.csv   # generated confusion matrix
```

The two model files serve different purposes. The `.task` locates joints; the `.pkl` learns your vocabulary. No real sign classifier or accuracy result can be supplied before labeled hand recordings exist.

## Stage 2: Set up OpenCV and hand tracking

Use 64-bit Python 3.11 or 3.12. The project has been set up locally in `.venv`; on this computer, start at the detector/tracking commands below. For a fresh copy, open PowerShell in `hand_sign_cv` and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If Windows provides Python through the launcher, use `py -3.12 -m venv .venv` instead. No environment activation is required. On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows executable path.

```powershell
.\.venv\Scripts\python.exe setup_model.py
.\.venv\Scripts\python.exe tracking.py
```

`setup_model.py` downloads the versioned Hand Landmarker model from Google's public model storage once. Inference then runs locally without a network connection. It does not upload webcam images. The pinned `opencv-contrib-python` package provides `cv2`; do not also install `opencv-python` or a headless OpenCV package into this environment.

OpenCV reads camera frames, mirrors them consistently, and converts BGR to RGB for MediaPipe. MediaPipe's **Tasks Hand Landmarker** runs in VIDEO mode using strictly increasing timestamps. The synchronous loop is easier to understand than callbacks and still processes a live webcam. The system detects up to two hands to reject two-hand input instead of arbitrarily classifying one.

You should see the 21 points connected across your fingers. Press `Q` or Escape to quit. Try `--camera 1` if the default camera is wrong. Fix tracking before collecting any data: use even lighting, show the whole hand, avoid motion blur, and close applications already using the camera.

## Stage 3: Normalize landmarks and extract features

For landmark `i`, MediaPipe gives `(x_i, y_i, z_i)`. Image `x` uses width units, `y` uses height units, and relative depth `z` uses roughly width units. For image width `W` and height `H`, the code first uses a common coordinate scale:

```text
p_i = (W*x_i, H*y_i, W*z_i)
q_i = p_i - p_0                         # landmark 0 is the wrist
s   = mean(||q_5||, ||q_9||, ||q_13||, ||q_17||)
n_i = q_i / s                          # palm-scale normalization
```

Subtracting the wrist removes image position. Dividing by mean wrist-to-knuckle distance reduces effects of hand size and distance to the camera. A zero/invalid palm or collapsed finger joint causes the frame to be skipped. This is approximate invariance: perspective, occlusion and noisy estimated depth can still change the features.

We preserve rotation and left/right differences because orientation may distinguish signs, as it does in your glove's IMU data. This version neither rotates hands into a canonical pose nor mirrors left-hand landmarks into right-hand landmarks. Start with the same signing hand; collect both hands if both need to work. Vary modest wrist angles during collection without changing a sign's meaning.

Each sample contains **83 values**:

| Features | Count | What they capture |
|---|---:|---|
| Flattened normalized `(x,y,z)` landmarks | 63 | Overall pose and orientation |
| Distances between every pair of five fingertips | 10 | Finger spread and pinch/contact patterns |
| Cosines of two bend angles per digit | 10 | Finger bending |

For a joint `(a,b,c)`, the cosine is `dot(n_a-n_b, n_c-n_b) / (length(n_a-n_b)*length(n_c-n_b))`. A straight joint is near `-1`, with other bends changing the value. The forest can combine these features without a separate standardization step. Changing feature logic requires a new `FEATURE_VERSION`, new data and retraining.

## Stage 4: Collect a labeled dataset

Edit `signs.json` before collection. Its starter poses are OPEN_PALM, FIST, THUMB_UP, THUMB_DOWN, INDEX_UP, V_SHAPE, THREE_FINGERS, FOUR_FINGERS, L_SHAPE, PINCH_CIRCLE, LITTLE_UP and THUMB_LITTLE, plus REST. Full pose descriptions are in that file. Labels should be uppercase ASCII with underscores. Keep `REST`; `UNKNOWN` and `NO_SIGN` are reserved runtime outcomes.

```powershell
.\.venv\Scripts\python.exe collect_data.py --participant p01 --session day1
```

Use pseudonyms such as `p01` for each person and keep one session name for the entire recording visit across all labels. Do not manufacture new session IDs for every short burst from the same visit; that defeats evaluation separation.

| Key | Action |
|---|---|
| Space | Start a two-second preparation countdown; press again to pause |
| N / P | Next / previous label; recording automatically pauses |
| Q / Escape | Save existing rows and close |

The default burst records 50 usable frames, at most 5 per second, then pauses. Use `--samples 30 --interval 0.3` to change this. Use `--label REST` to start directly at rest. Only one valid detected hand is saved; frames with no hand, two hands or invalid landmarks are skipped. No raw video/images are stored.

The CSV stores label, participant, session, UTC timestamp, feature version, vocabulary fingerprint and 83 feature columns. Existing compatible data is appended, with each row flushed to disk. A vocabulary change, even a pose-description change, is deliberately rejected for an existing dataset: use a new `--dataset dataset/hand_signs_v2.csv` and retrain so incompatible definitions do not mix.

For a first useful dataset, aim for 200-500 varied rows per class across at least five complete participant/session groups; more groups are more useful than thousands of almost identical frames. Ask all six members to contribute. Record every label, including REST, in each session where possible. Pause, lower the hand, reform the pose and vary position, comfortable camera distance, lighting and background. Keep the pose correct while recording; stop recording before switching signs.

Collect REST with a visible naturally relaxed hand in several idle configurations. Do not label a target pose as REST. **No detected hand becomes `NO_SIGN` by a runtime rule**, so an all-zero landmark sample is never inserted into the classifier. An occluded hand that the detector misses will also produce `NO_SIGN`; it means absence of a detection, not proof of absence of a hand.

Suggested session sequence: all labels on day1, a fresh setup on day2, and further visits/participants until every class has enough groups. REST should have about as many varied samples as a target class. The collector's on-screen count is for the current participant/session, not the total dataset.

## Stage 5: Train and evaluate

```powershell
.\.venv\Scripts\python.exe train_model.py
```

The script validates the complete dataset and requires every configured class, including REST. It trains 200 trees with class balancing and a small minimum leaf size. Random Forest handles nonlinear relationships with little tuning and exposes `predict_proba`; SVM/KNN can be later experiments, but are not necessary for this prototype.

The default split groups rows by **participant + recording session**. Approximately 60% of groups train the classifier, 20% select a confidence threshold, and 20% provide the final test evaluation. Fractions can differ for small datasets. The search only checks class coverage, never test performance. Every class needs at least three groups and at least 15 rows to pass validation; these are software minimums, not a recommendation for adequate data.

Randomly splitting individual adjacent webcam frames would leak near-duplicates into both train and test and can make weak models look excellent. The grouped split prevents this. For a stronger claim about new people, use:

```powershell
.\.venv\Scripts\python.exe train_model.py --group-by participant
```

That keeps each participant entirely in one partition; collect all signs from at least three participants, preferably all six. Session-held-out results measure new sessions, not unseen-person generalization.

The saved outputs include overall raw test accuracy, precision/recall/F1 for every class, confusion matrix (rows actual, columns predicted), partition group lists, dataset fingerprint and threshold sweep. With rejection enabled, inspect **coverage** (fraction accepted), **accepted accuracy** (accuracy among accepted predictions), and **overall accuracy with rejection** (UNKNOWN counts as incorrect for known signs). A high accepted accuracy with tiny coverage is a poor demo.

Read the confusion matrix before changing algorithms. If two labels repeatedly confuse, check annotation consistency, whether both poses actually differ in landmarks, and whether more varied training data is needed. Keep the final test sessions untouched during tuning; if you repeatedly use their results to revise the system, collect a fresh final test set for your report.

The `.pkl` stores the evaluated train-only model and its validation threshold. It is intentionally not refitted using test data. Only load your own trusted pickle/joblib files. Training and prediction must use the same scikit-learn version; the loader checks this.

## Stage 6: Run real-time prediction

```powershell
.\.venv\Scripts\python.exe realtime_predict.py
```

The script reloads the saved classifier, uses the exact collection feature pipeline and displays the accepted label, raw candidate, candidate confidence, threshold, stable-frame count and processing latency. Paths default to this script's directory, so running from another folder still works. The displayed confidence belongs to the **raw candidate**, not a separate probability that the accepted label is correct.

| Output | Meaning |
|---|---|
| A configured sign | Above threshold for enough consecutive frames |
| REST | Learned visible idle-hand pose, also subject to smoothing |
| NO_SIGN | No hand detected; clear previous sign immediately |
| UNKNOWN | Low confidence, unstable candidate, invalid features or multiple hands |

This module displays text and optionally logs predictions. It does not trigger the glove's speech. Quit with `Q`, Escape or the window close button; the camera and detector are released on exit.

## Stage 7: Confidence thresholds and smoothing

Forest confidence is the highest class score from `predict_proba`. It is a heuristic model score, **not a calibrated probability of being correct**. Training evaluates thresholds from 0.50 to 0.95 on validation groups. It chooses the highest-coverage candidate reaching 95% accepted validation accuracy with at least 50% coverage (ties prefer a higher threshold). If none qualifies, it chooses the best macro F1 with rejection and prints a warning. A manually supplied training `--threshold 0.75` uses that value instead.

Try different live settings on separate practice sessions:

```powershell
.\.venv\Scripts\python.exe realtime_predict.py --threshold 0.75 --frames 5
```

A prediction below threshold becomes UNKNOWN before smoothing. The default smoother requires five consecutive matching, above-threshold frames, including for REST. A changed candidate becomes UNKNOWN while stabilizing; low confidence, no hand, multiple hands or a processing gap over 0.5 seconds resets the count. Previously accepted words do not remain on screen while a new pose is uncertain. At 30 processed frames/second, five observations span about 0.13 seconds from the first to the fifth, plus processing/capture delay; slower computers take longer.

Thresholding cannot guarantee rejection of every unseen sign: a closed-set classifier can be confidently wrong on unfamiliar poses. Test untrained poses, transitions and idle hands explicitly. The training metrics assess known-class frame predictions only; they do not measure that open-set behavior, the no-hand rule or temporal smoothing. REST helps idle behavior but is not a universal catch-all for every possible hand shape.

Before demonstrating, perform a small live trial with a held-out person/session:

1. Hold each target sign several times and note correct stable output and time to acceptance.
2. Hold REST, remove the hand, and show two hands; check REST, NO_SIGN and UNKNOWN respectively.
3. Show unfamiliar poses and move between targets; count unintended accepted labels per minute.
4. Repeat at different distances/lighting and note tracking failures separately from classifier errors.
5. Confirm the glove still recognizes and speaks when this CV program is completely closed.

## Stage 8: Compare with the glove later

Both pipelines can agree on a vocabulary and a test protocol while running independently. To save CV results for offline comparison:

```powershell
.\.venv\Scripts\python.exe realtime_predict.py --log logs/cv_trial01.csv
```

The optional log contains UTC capture timestamp, `source=cv`, raw label, candidate confidence, accepted label, reason and processing latency. It refuses to overwrite an existing log. Record glove predictions separately on the same laptop clock, or synchronize clocks and record a shared start cue. Add ground-truth trial IDs, target labels, participant IDs and sign-hold time windows to a separate trial sheet. Pair outputs inside those windows with a documented time tolerance; do not simply zip rows because sampling rates differ.

Compare each system against the **human ground-truth label**, not against the other system as truth. Report per-class accuracy, REST false triggers, UNKNOWN/NO_SIGN rates, time from pose onset to stable label and disagreement rate. Different model confidence scores are not directly comparable unless separately calibrated. CV `latency_ms` measures feature/detector/classifier processing after a captured frame is returned; it excludes camera buffering, smoothing delay and glove speech latency.

Use results to learn whether flex sensing and camera landmarks make different mistakes. No CV validation gate, automatic override, sensor fusion or fallback is added to the main glove pipeline. If the final glove vocabulary contains moving or two-hand signs, compare only the shared supported subset until the CV feature representation is explicitly extended.

## Checks and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_pipeline.py
```

These camera-free tests check translation/scale invariance, aspect ratio correction, preserved orientation, invalid inputs, confidence rejection, smoothing resets, disjoint dataset groups, CSV validation and an end-to-end train/save/reload cycle. Synthetic fixtures exist only in temporary test files; their scores do not measure real hand-sign performance.

Local verification on 18 September 2026: all seven tests passed on Windows with Python 3.12.14 and the pinned dependencies. The MediaPipe detector processed an empty frame, and the laptop camera returned a 640x480 frame that the detector processed successfully. No visible hand was detected during that brief check, so actual landmark quality, sign accuracy and sustained real-time performance still need your live recordings. The delivered dataset has only its header; no trained sign `.pkl` or real-data metrics have been invented.

| Symptom | What to check |
|---|---|
| Missing classifier / empty dataset | Collect every configured sign including REST, then train |
| Missing `.task` | Run `setup_model.py`; internet is needed only for download |
| No camera | Close Teams/Zoom, enable OS camera permission, try `--camera 1` |
| No OpenCV window / GUI error | Use local desktop Python and the pinned non-headless OpenCV package |
| `mp.solutions` missing | This code uses the Tasks API; do not substitute older tutorial snippets |
| Most outputs UNKNOWN | Inspect raw scores and data quality before lowering threshold; check hand/orientation consistency |
| High accuracy but weak live results | Collect fresh sessions/users; check leakage, transitions, unfamiliar poses and class imbalance |
| Model/config mismatch | Restore original vocabulary or recollect/retrain into new files |
| Split cannot cover all classes | Record every label in more complete sessions; do not switch to random frame splitting |

## Technical references

- [MediaPipe Hand Landmarker Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python): Tasks API, timestamps and landmark coordinate conventions.
- [OpenCV video capture](https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html): webcam capture and display.
- [RandomForestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html): classifier and probability scores.
- [GroupShuffleSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html): holding out entire groups.
- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html): environment compatibility and trusted model loading.
