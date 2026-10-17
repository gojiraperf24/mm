# Archive training results

Trained at 2026-09-19T13:21:10.121613+00:00 using 34,627 supplied images.

- Labels: A, B, C, D, E, F, G, H, I, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y. No J, Z or REST examples were supplied.
- Input: 28x28 grayscale images; OpenCV HOG produces 324 edge-pattern features.
- Classifier: RBF SVM, C=10, gamma=scale, balanced class weights.
- Fitting: 21,964; confidence calibration: 2,745; threshold validation: 2,746; untouched test: 7,172 images.
- Test accuracy before rejection: **97.77%**.
- Confidence threshold: 0.70; accepted coverage: **99.99%**; accuracy among accepted images: **97.77%**.
- Accuracy over all test images when UNKNOWN counts as an error: 97.76%.
- Total elapsed training/audit time: 291.6 seconds.

These are scores on this archive, not on a live webcam or new signers. Exact pixel duplicates were excluded where found; related augmentations/near-duplicates cannot be ruled out because source/signer metadata is absent. The model has no learned REST class. The original 83-landmark-feature Random Forest remains a separate pipeline and was not trained with these images.

See the matching metrics JSON, confusion CSV and predictions CSV for the complete results. The audit and exact split assignments are in dataset/archive_training.

All 34,627 images decoded successfully, all filename labels matched their folders, and no exact decoded-pixel duplicates were found. All four partitions have disjoint image fingerprints. The saved model was reloaded and its predictions matched the saved results for one test image from each of the 24 classes.

The largest confusions were U predicted as R (41 images), T as X (21), N as M (21), Y as W (20), V as W (18), and B as K (18). U had the lowest recall at 84.59%, meaning about 85% of actual U images were recognized correctly before rejection. These observations describe the final test; the model was not retuned using them.
