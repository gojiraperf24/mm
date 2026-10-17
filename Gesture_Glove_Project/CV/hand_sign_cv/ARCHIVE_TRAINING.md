# Training with the supplied archive

**Completed run:** the saved model achieved **97.77% test accuracy** on 7,172 images. All 34,627 files decoded successfully, all filename labels matched their folders, and no exact decoded-pixel duplicates were found. See [the measured results](models/archive_hog_classifier.report.md). The saved model was reloaded and reproduced stored predictions for one test image from each of the 24 classes; all ten code tests passed.

The archive is labeled by folder: `Train/A` contains examples labeled A, `Train/B` contains examples labeled B, and so on. Filenames also end in the label, such as `10014_A.jpg`. There are 27,455 training pictures and 7,172 test pictures across 24 letters: A, B, C, D, E, F, G, H, I, K, L, M, N, O, P, Q, R, S, T, U, V, W, X and Y. There are no J, Z or REST folders. Sample poses were visually inspected; the training audit checks all filenames against their folders. This verifies the label structure, not the semantic correctness of every human pose annotation.

## Why these pictures need a different approach

The pictures are only 28x28 pixels and grayscale. The original system asks MediaPipe to identify 21 joints, then trains a Random Forest on their positions. A seeded sample of 240 training pictures (ten per letter) produced no hand detections after enlargement to 224x224. A further L example also failed unmirrored at 224 and 512 pixels, including lower detection settings. Enlargement makes the existing pixels bigger; it does not recover fine joint detail.

Consequently, `train_archive.py` trains a **separate image-based model**. It does not pretend these pictures supplied usable landmark measurements. The original `train_model.py`, `collect_data.py`, vocabulary and webcam landmark pipeline remain available for higher-resolution recordings. Neither system is a dependency of the glove.

## What happens during training

1. **Read and check every picture.** The program reads its folder label and filename label, decodes the picture and records its size. Unreadable files and conflicting labels are excluded and reported.
2. **Check for exact duplicate pictures.** A fingerprint is computed from the decoded grayscale pixels. Identical copies within a split are counted only once. Any exact test copy of a training image is excluded from evaluation. Identical pixels assigned different labels are excluded. The source files remain unchanged.
3. **Turn the picture into numbers.** OpenCV computes HOG, short for Histogram of Oriented Gradients. Think of it as a description of where edges appear and which way they point. Fingers, gaps between fingers and the outside of the hand create different edge patterns. The 28x28 picture is resized to 32x32 for a regular grid, producing 324 numbers. These are not the original 83 landmark features.
4. **Keep learning and checking separate.** From the usable `Train` images, 80% teach the classifier, 10% calibrate its confidence scores and 10% select the confidence cutoff. Each part contains examples of every letter. The supplied `Test` folder is kept separate until the end.
5. **Fit an SVM classifier.** An SVM learns boundaries between the numerical patterns for different letters. Here it uses an RBF kernel, C=10 and gamma=scale, with balanced class weights. These are fixed baseline settings rather than settings repeatedly adjusted against the test answers. There is no new deep neural network to train.
6. **Check confidence.** Separate calibration examples convert model scores into probability estimates using sigmoid calibration. Separate validation examples select an UNKNOWN cutoff. The search tries 0.50 through 0.95, aiming for at least 95% accuracy among accepted validation images while retaining at least half the images. If this is not achieved, it falls back to the best validation macro F1 with rejection. These confidence estimates still do not guarantee that an unfamiliar hand pose is recognized as unknown.
7. **Take the final test.** The saved model predicts the usable test pictures without fitting on them. Results include accuracy, per-letter precision/recall/F1, a confusion matrix and a prediction for each test image. UNKNOWN is counted as a missed answer in the overall rejection-enabled accuracy. Accuracy among accepted predictions must always be read alongside the percentage accepted.
8. **Save the actual fitted model.** The `.pkl` contains the SVM, confidence calibration and cutoff. It is the model that was evaluated, without refitting on test pictures.

The fixed random seed is 42. Exact partition assignments and image fingerprints are saved for reproducibility. The archive contains no identified people, recording sessions or original-image family identifiers. Therefore, random subdivisions of the training folder cannot establish generalization to new people, and near-duplicate/augmented source images may still be related across partitions. Exact duplicate checking does not solve that missing-provenance limitation.

## Files produced

| File | Purpose |
|---|---|
| `models/archive_hog_classifier.pkl` | Trained image model; distinct from `hand_sign_classifier.pkl` |
| `models/archive_hog_classifier.report.md` | Readable results with actual measured scores |
| `models/archive_hog_classifier.metrics.json` | Full metrics, settings, versions and counts |
| `models/archive_hog_classifier.confusion.csv` | Which actual letters were predicted as which letters |
| `models/archive_hog_classifier.predictions.csv` | Actual/predicted letter and confidence for each test image |
| `dataset/archive_training/archive_audit.csv` | File labels, hashes, dimensions and exclusion reasons |
| `dataset/archive_training/archive_partitions.csv` | Which picture went into each training/evaluation partition |
| `dataset/archive_training/archive_hog_features.npz` | Numerical image features |
| `dataset/archive_training/landmark_compatibility.json` | Results of the initial MediaPipe compatibility check |

Run from PowerShell in `CV/hand_sign_cv`:

```powershell
# Reproduce the complete audit and training run:
.\.venv\Scripts\python.exe train_archive.py

# Predict a cropped image from the archive:
.\.venv\Scripts\python.exe predict_archive.py --image "..\archive\Test\A\1003_A.jpg"
```

The archive training command regenerates its own audit/model/results outputs. It never edits archive pictures or the original landmark dataset. Only load trusted model pickle files, and use the supplied pinned dependency versions.

## Can this model recognize signs from the webcam?

There is an **experimental** command:

```powershell
.\.venv\Scripts\python.exe predict_archive.py --camera 0
```

MediaPipe operates on the full-resolution webcam image only to locate a hand and crop around it. The archive classifier then reads the crop's edge features. It does not use the detected joint coordinates as classification features. No hand detected produces NO_SIGN, multiple hands produce UNKNOWN, and confident predictions still need five matching frames. Press Q to quit. Use `--flip-crop` if your signing hand has the opposite image orientation to the examples.

This is not a claim that the archive-trained model has reliable webcam performance. Cropping, lighting, backgrounds, hand size and pose orientation can all differ from the archive. A high archive test score does not measure those differences. Live accuracy needs a separate trial using your team and camera.

There is **no learned REST class** because the archive contains no relaxed-hand examples. An idle visible hand may be confidently mistaken for a letter. UNKNOWN thresholding is not a substitute for REST training. For the original webcam landmark model, collect clear examples of your agreed glove vocabulary and REST using `collect_data.py`, then train using `train_model.py`. The archive alphabet is also different from the original twelve practice poses; it should not be described as already matching the glove vocabulary.

## References

- [OpenCV HOG descriptor](https://docs.opencv.org/4.x/d5/d33/structcv_1_1HOGDescriptor.html)
- [scikit-learn SVM classifier](https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html)
- [scikit-learn confidence calibration](https://scikit-learn.org/stable/modules/calibration.html)
