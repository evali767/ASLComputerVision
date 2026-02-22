import os
import time
import json
import threading
from collections import deque, Counter

import cv2
import numpy as np
import joblib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from cvzone.HandTrackingModule import HandDetector

# ----------------------------
# Config
# ----------------------------
SEQ_LEN = 45                 # must match how you trained
SMOOTH_WINDOW = 10
PRED_EVERY = 3

# How long user must hold correct sign to "pass" (seconds)
# For demo, 2–3 is realistic. If you truly want 45 seconds, set HOLD_SECONDS = 45.
HOLD_SECONDS = float(os.getenv("HOLD_SECONDS", "2.5"))

MODEL_PATH = os.getenv("MODEL_PATH", "asl_model.joblib")

# Word DB (for “known words” -> show video)
# For hackathon: keep it small + reliable
WORD_DB = {
    "hello": {"type": "word", "video": "/assets/hello.mp4"},
    "thank": {"type": "word", "video": "/assets/thank_you.mp4"},
    "you":   {"type": "word", "video": "/assets/you.mp4"},
    "yes":   {"type": "word", "video": "/assets/yes.mp4"},
    "no":    {"type": "word", "video": "/assets/no.mp4"},
}

# ----------------------------
# Helpers
# ----------------------------
def majority_vote(preds):
    if not preds:
        return None
    return Counter(preds).most_common(1)[0][0]

def normalize_landmarks(lm: np.ndarray) -> np.ndarray:
    """
    lm: (21,3) in pixel-ish coords
    Normalize to be less sensitive to position/scale.
    """
    lm = lm.astype(np.float32).copy()
    wrist = lm[0, :2]
    lm[:, :2] -= wrist
    scale = np.linalg.norm(lm[9, :2])  # middle MCP as scale anchor
    if scale > 1e-6:
        lm[:, :2] /= scale
    return lm

# ----------------------------
# Shared state (camera + model)
# ----------------------------
class ASLState:
    def __init__(self):
        self.lock = threading.Lock()

        # game state
        self.sentence = ""
        self.queue = []               # list of targets (word or letter tokens)
        self.current_idx = 0
        self.points = 0
        self.leaderboard = {}         # name -> points (simple in-memory)

        # prediction state
        self.last_frame = None
        self.last_pred = None
        self.top3_text = ""
        self.buffer_fill = 0

        self.hold_started_at = None   # time when correct sign started holding
        self.hold_progress = 0.0      # 0..1

        # camera + detection
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        self.detector = HandDetector(maxHands=1)

        self.lm_buffer = deque(maxlen=SEQ_LEN)
        self.pred_buffer = deque(maxlen=SMOOTH_WINDOW)

        # model
        bundle = joblib.load(MODEL_PATH)
        self.model = bundle["model"]

        # run loop thread
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def set_sentence(self, sentence: str):
        sentence = sentence.strip()
        tokens = [t for t in sentence.split() if t.strip()]
        q = []
        for t in tokens:
            low = t.lower()
            if low in WORD_DB:
                q.append({"kind": "word", "text": low, "video": WORD_DB[low]["video"]})
            else:
                # fallback: spell it
                for ch in t.upper():
                    if ch.isalpha():
                        q.append({"kind": "letter", "text": ch})
        with self.lock:
            self.sentence = sentence
            self.queue = q
            self.current_idx = 0
            self.points = 0
            self.hold_started_at = None
            self.hold_progress = 0.0

            # reset buffers when new session starts
            self.lm_buffer.clear()
            self.pred_buffer.clear()
            self.last_pred = None
            self.top3_text = ""

    def get_target(self):
        with self.lock:
            if not self.queue or self.current_idx >= len(self.queue):
                return None
            return self.queue[self.current_idx]

    def advance_if_correct(self, pred: str):
        """
        If current target is a letter, compare it to pred (like 'J').
        If current target is a word, you can either:
          - accept spelling letters only (simple), or
          - accept dedicated word labels if you train them.
        Here we keep it simple:
          - If target.kind == letter: expect pred == that letter
          - If target.kind == word: (for now) skip verification OR require spelled letters
        """
        with self.lock:
            target = self.get_target()
            if target is None:
                return

            # For hackathon simplicity: verify letters only.
            # Words are "watch video then fingerspell"
            expected = target["text"] if target["kind"] == "letter" else None

            now = time.time()

            if expected is None:
                # word token: auto-advance after video / user click in UI
                self.hold_started_at = None
                self.hold_progress = 0.0
                return

            # letter token: check hold
            if pred == expected:
                if self.hold_started_at is None:
                    self.hold_started_at = now
                elapsed = now - self.hold_started_at
                self.hold_progress = min(1.0, elapsed / HOLD_SECONDS)

                if elapsed >= HOLD_SECONDS:
                    self.points += 10
                    self.current_idx += 1
                    self.hold_started_at = None
                    self.hold_progress = 0.0

                    # reset prediction buffers for next token (important for motion)
                    self.lm_buffer.clear()
                    self.pred_buffer.clear()
            else:
                self.hold_started_at = None
                self.hold_progress = 0.0

    def _loop(self):
        """
        Camera + hand landmarks + model inference loop.
        Stores latest frame and latest prediction.
        """
        frame_idx = 0
        missing = 0
        MISSING_RESET = 5  # reset after N missing frames (prevents flicker resets)

        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            # hands, annotated = self.detector.findHands(frame)
            hands, annotated = self.detector.findHands(frame, draw=False)
            annotated = frame  # keep raw frame for streaming

            if not hands:
                missing += 1
                if missing >= MISSING_RESET:
                    with self.lock:
                        self.lm_buffer.clear()
                        self.pred_buffer.clear()
                        self.last_pred = None
                        self.top3_text = ""
                        self.buffer_fill = 0
                with self.lock:
                    self.last_frame = annotated
                frame_idx += 1
                continue
            else:
                missing = 0

            hand = hands[0]
            lm = np.array(hand["lmList"], dtype=np.float32)  # (21,3)
            lm = normalize_landmarks(lm)

            with self.lock:
                self.lm_buffer.append(lm)
                self.buffer_fill = len(self.lm_buffer)

            # Predict when buffer full
            if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
                seq = np.stack(self.lm_buffer, axis=0)  # (SEQ_LEN,21,3)
                feat = seq.reshape(1, -1)

                pred = self.model.predict(feat)[0]

                with self.lock:
                    self.pred_buffer.append(pred)
                    smoothed = majority_vote(list(self.pred_buffer))
                    self.last_pred = smoothed

                    # top3
                    self.top3_text = ""
                    if hasattr(self.model, "predict_proba"):
                        probs = self.model.predict_proba(feat)[0]
                        top_idx = np.argsort(probs)[::-1][:3]
                        top3 = [(self.model.classes_[i], float(probs[i])) for i in top_idx]
                        self.top3_text = " | ".join([f"{c}:{p:.2f}" for c, p in top3])

                # update progression based on smoothed pred
                self.advance_if_correct(self.last_pred)

            with self.lock:
                self.last_frame = annotated

            frame_idx += 1

    def get_jpeg(self):
        with self.lock:
            frame = self.last_frame
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return buf.tobytes()

    def snapshot_state(self):
        with self.lock:
            target = self.get_target()
            done = (target is None)

            return {
                "pred": self.last_pred,
                "top3": self.top3_text,
                "buffer": self.buffer_fill,
                "seqLen": SEQ_LEN,
                "holdProgress": self.hold_progress,
                "points": self.points,
                "target": target,
                "currentIndex": self.current_idx,
                "total": len(self.queue),
                "done": done,
            }

state = ASLState()

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite or CRA
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def mjpeg_generator():
    target_fps = 12
    delay = 1.0 / target_fps
    last_sent = 0.0

    while True:
        now = time.time()
        if now - last_sent < delay:
            time.sleep(0.002)
            continue

        frame = state.get_jpeg()
        if frame is None:
            time.sleep(0.02)
            continue

        last_sent = now
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

@app.get("/video")
def video():
    return StreamingResponse(mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # send initial state
        await websocket.send_text(json.dumps(state.snapshot_state()))
        while True:
            # client can send commands
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data.get("type") == "set_sentence":
                state.set_sentence(data.get("sentence", ""))

            if data.get("type") == "skip_word":
                # For word tokens: advance (UI button after video plays)
                with state.lock:
                    t = state.get_target()
                    if t and t["kind"] == "word":
                        state.current_idx += 1
                        state.lm_buffer.clear()
                        state.pred_buffer.clear()
                        state.hold_started_at = None
                        state.hold_progress = 0.0

            # Always respond with current state
            await websocket.send_text(json.dumps(state.snapshot_state()))

    except WebSocketDisconnect:
        return