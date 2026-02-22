import os
import numpy as np
from collections import Counter

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
import joblib

DATA_ROOT = "Data"
TEST_SIZE = 0.2
RANDOM_STATE = 42

TARGET_LEN = 45 

def fix_length(arr, target_len=TARGET_LEN):
    T = arr.shape[0]
    if T == target_len:
        return arr
    if T > target_len:
        return arr[:target_len]
    pad = np.repeat(arr[-1][None, :, :], target_len - T, axis=0)
    return np.concatenate([arr, pad], axis=0)

# ---- Load dataset ----
X = []
y = []

labels = sorted([
    d for d in os.listdir(DATA_ROOT)
    if os.path.isdir(os.path.join(DATA_ROOT, d))
])

for label in labels:
    label_dir = os.path.join(DATA_ROOT, label)
    for seq in os.listdir(label_dir):
        seq_dir = os.path.join(label_dir, seq)
        lm_path = os.path.join(seq_dir, "landmarks.npy")
        if os.path.exists(lm_path):
            # arr = np.load(lm_path)      # (T, 21, 3)
            # feat = arr.reshape(-1)      # flatten -> (T*21*3,)
            # X.append(feat)
            # y.append(label)
            arr = np.load(lm_path)          # (T,21,3)
            arr = fix_length(arr)           # (45,21,3)
            feat = arr.reshape(-1)          # (45*21*3,)
            X.append(feat)
            y.append(label)

X = np.array(X)
y = np.array(y)

print("Loaded:", X.shape, "labels:", set(y))

# ---- (Optional) focus on I vs J for now ----
KEEP_ONLY_IJ = False  # set True if you want just I vs J
if KEEP_ONLY_IJ:
    keep = {"I", "J"}
    mask = np.array([lbl in keep for lbl in y])
    X = X[mask]
    y = y[mask]
    print("After filtering:", X.shape, "labels:", set(y))

# ---- Sanity checks ----
counts = Counter(y)
print("Counts per label:", counts)

if len(counts) < 2:
    raise ValueError(f"Need at least 2 labels to train. Currently have: {list(counts.keys())}")

n_classes = len(counts)
n_samples = len(y)
n_test = int(np.ceil(n_samples * TEST_SIZE))

# Stratify only if the test set can include >= 1 sample per class (and each class has >=2 total)
use_stratify = (n_test >= n_classes) and (min(counts.values()) >= 2)
stratify_arg = y if use_stratify else None
if not use_stratify:
    print("Not enough data to stratify yet; splitting without stratify for now.")
    print(f"(n_samples={n_samples}, test_size={TEST_SIZE} => n_test={n_test}, n_classes={n_classes}, min_class={min(counts.values())})")

# ---- Train/test split ----
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=stratify_arg
)

# ---- Train model ----
clf = LogisticRegression(max_iter=3000)
clf.fit(X_train, y_train)

# ---- Evaluate ----
pred = clf.predict(X_test)
print(classification_report(y_test, pred))

# use consistent label order
label_order = sorted(list(counts.keys()))
print("Confusion matrix:\n", confusion_matrix(y_test, pred, labels=label_order))

# ---- Save ----
joblib.dump({"model": clf, "labels": label_order}, "asl_model.joblib")
print("Saved model to asl_model.joblib")