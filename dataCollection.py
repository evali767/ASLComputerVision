import cv2
import numpy as np
import math
import time
import os

from cvzone.HandTrackingModule import HandDetector

cap = cv2.VideoCapture(0)
detector = HandDetector(maxHands=1)

offset = 20
imgSize = 500

# ---- General recording config ----
DATA_ROOT = "Data"
SEQ_LEN = 45  # ~1 second at ~30 fps

current_label = "THANK YOU"          # default label
recording = False
frames_buf = []
lm_buf = []                  # list of (21, 3) landmarks per frame

os.makedirs(os.path.join(DATA_ROOT, current_label), exist_ok=True)

def safe_crop(img, x, y, w, h, offset):
    H, W = img.shape[:2]
    x1 = max(x - offset, 0)
    y1 = max(y - offset, 0)
    x2 = min(x + w + offset, W)
    y2 = min(y + h + offset, H)
    return img[y1:y2, x1:x2]

def make_white(imgCrop, w, h, imgSize):
    imgWhite = np.ones((imgSize, imgSize, 3), np.uint8) * 255

    if imgCrop.size == 0 or w == 0 or h == 0:
        return None

    aspectRatio = h / w
    if aspectRatio > 1:
        k = imgSize / h
        wCal = math.ceil(k * w)
        imgResize = cv2.resize(imgCrop, (wCal, imgSize))
        wGap = math.ceil((imgSize - wCal) / 2)
        imgWhite[:, wGap:wCal + wGap] = imgResize
    else:
        k = imgSize / w
        hCal = math.ceil(k * h)
        imgResize = cv2.resize(imgCrop, (imgSize, hCal))
        hGap = math.ceil((imgSize - hCal) / 2)
        imgWhite[hGap:hCal + hGap, :] = imgResize

    return imgWhite

while True:
    success, img = cap.read()
    if not success:
        continue

    hands, img = detector.findHands(img)

    imgWhite = None
    lm_frame = None

    if hands:
        hand = hands[0]
        x, y, w, h = hand["bbox"]

        imgCrop = safe_crop(img, x, y, w, h, offset)
        imgWhite = make_white(imgCrop, w, h, imgSize)

        # landmarks: cvzone gives list of 21 points like [x,y,z]
        lm = hand["lmList"]
        # store as numpy (21,3)
        lm_frame = np.array(lm, dtype=np.float32)

        if imgCrop.size != 0:
            cv2.imshow("ImageCrop", imgCrop)
        if imgWhite is not None:
            cv2.imshow("ImageWhite", imgWhite)

    # overlay status
    status = f"Label: {current_label} | Recording: {recording} | Frames: {len(frames_buf)}/{SEQ_LEN}"
    cv2.putText(img, status, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    cv2.imshow("Image", img)
    key = cv2.waitKey(1) & 0xFF

    # ---- Controls ----
    # press a-z to set label (uppercase)
    if key >= ord('a') and key <= ord('z'):
        current_label = chr(key).upper()
        os.makedirs(os.path.join(DATA_ROOT, current_label), exist_ok=True)
        print("Label set to:", current_label)

    # start/stop recording
    if key == ord('.'):
        recording = True
        frames_buf = []
        lm_buf = []
        print(f"Recording sequence for {current_label}...")

    # quit
    if key == ord('q'):
        break

    # ---- Recording logic ----
    if recording:
        # only record when we actually have a processed frame + landmarks
        if imgWhite is not None and lm_frame is not None:
            frames_buf.append(imgWhite.copy())
            lm_buf.append(lm_frame)

        # stop once we have enough frames
        if len(frames_buf) >= SEQ_LEN:
            seq_id = str(int(time.time() * 1000))
            seq_dir = os.path.join(DATA_ROOT, current_label, f"seq_{seq_id}")
            os.makedirs(seq_dir, exist_ok=True)

            # save frames (optional but useful)
            for i, frame in enumerate(frames_buf):
                cv2.imwrite(os.path.join(seq_dir, f"frame_{i:03d}.jpg"), frame)

            # save landmarks (this is the key for motion)
            np.save(os.path.join(seq_dir, "landmarks.npy"),
                    np.stack(lm_buf, axis=0))  # shape (SEQ_LEN, 21, 3)

            print(f"Saved: {seq_dir}  (frames={len(frames_buf)})")

            recording = False
            frames_buf = []
            lm_buf = []