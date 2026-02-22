import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import cv2
import numpy as np
from collections import deque, Counter
import joblib
from cvzone.HandTrackingModule import HandDetector

SEQ_LEN = 45
PRED_EVERY = 1
SMOOTH_WINDOW = 10

bundle = joblib.load("asl_model.joblib")
model = bundle["model"]

cap = cv2.VideoCapture(0)
detector = HandDetector(maxHands=2)

lm_buffer = deque(maxlen=SEQ_LEN)
pred_buffer = deque(maxlen=SMOOTH_WINDOW)

frame_idx = 0
top3_text = ""  # <-- important: define outside loop so it always exists

def reset_buffers():
    lm_buffer.clear()
    pred_buffer.clear()


def majority_vote(preds):
    if not preds:
        return None
    return Counter(preds).most_common(1)[0][0]

# def two_hand_landmarks(hands):
#     """
#     Returns (2,21,3) float32 landmarks.
#     Index 0 = Left hand, Index 1 = Right hand (if available).
#     Missing hand -> zeros.
#     """
#     out = np.zeros((2, 21, 3), dtype=np.float32)

#     # cvzone often provides "type": "Left"/"Right"
#     for h in hands[:2]:
#         hand_type = h.get("type", None)
#         lm = np.array(h["lmList"], dtype=np.float32)  # (21,3)
#         if hand_type == "Left":
#             out[0] = lm
#         elif hand_type == "Right":
#             out[1] = lm

#     # fallback if type isn't present
#     if out.sum() == 0 and len(hands) > 0:
#         out[0] = np.array(hands[0]["lmList"], dtype=np.float32)
#         if len(hands) > 1:
#             out[1] = np.array(hands[1]["lmList"], dtype=np.float32)

#     return out

def two_hand_landmarks(hands):
    """
    Returns (2,21,3) float32 landmarks.

    Rule:
    - If only ONE hand is detected: put it in slot 0, slot 1 = zeros.
    - If TWO hands are detected: slot 0 = Left, slot 1 = Right (best effort).
    """
    out = np.zeros((2, 21, 3), dtype=np.float32)

    if not hands:
        return out

    hands = hands[:2]

    # If exactly one hand: ALWAYS store in slot 0
    if len(hands) == 1:
        out[0] = np.array(hands[0]["lmList"], dtype=np.float32)
        return out

    # Two hands: try to place by type if available
    for h in hands:
        hand_type = h.get("type", None)
        lm = np.array(h["lmList"], dtype=np.float32)
        if hand_type == "Left":
            out[0] = lm
        elif hand_type == "Right":
            out[1] = lm

    # Fallback if type info is missing or unreliable:
    # sort by x of wrist (landmark 0) and assign leftmost->slot0, rightmost->slot1
    if (out.sum(axis=(1, 2)) == 0).any():
        lmA = np.array(hands[0]["lmList"], dtype=np.float32)
        lmB = np.array(hands[1]["lmList"], dtype=np.float32)
        if lmA[0, 0] <= lmB[0, 0]:
            out[0], out[1] = lmA, lmB
        else:
            out[0], out[1] = lmB, lmA

    return out

while True:
    success, img = cap.read()
    if not success:
        continue

    hands, img = detector.findHands(img)
    if not hands:
        # hand left frame -> reset so we capture a fresh full motion next time
        lm_buffer.clear()
        pred_buffer.clear()
        top3_text = ""
        frame_idx += 1
        cv2.putText(img, "No hand - buffer reset", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        cv2.imshow("ASL Live", img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        continue

    if hands:
        # hand = hands[0]
        # lm = np.array(hand["lmList"], dtype=np.float32)
        # lm_buffer.append(lm)

        lm2 = two_hand_landmarks(hands)   # (2,21,3)
        lm_buffer.append(lm2)

        if len(lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
            seq = np.stack(lm_buffer, axis=0)
            feat = seq.reshape(1, -1)

            pred = model.predict(feat)[0]
            pred_buffer.append(pred)

            # Update top-3 text (only when we predict)
            top3_text = ""
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(feat)[0]
                top_idx = np.argsort(probs)[::-1][:3]
                top3 = [(model.classes_[i], probs[i]) for i in top_idx]
                top3_text = " | ".join([f"{c}:{p:.2f}" for c, p in top3])

    smoothed = majority_vote(list(pred_buffer))

    # Draw prediction once (no duplicates)
    if smoothed is not None:
        cv2.putText(img, f"Pred: {smoothed}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    else:
        cv2.putText(img, "Pred: ...", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)

    cv2.putText(img, f"Buffer: {len(lm_buffer)}/{SEQ_LEN}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Show top-3 if available
    if top3_text:
        cv2.putText(img, top3_text, (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    cv2.imshow("ASL Live", img)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

    frame_idx += 1

cap.release()
cv2.destroyAllWindows()