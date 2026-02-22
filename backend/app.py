# """
# ASL Spellcaster — FastAPI Backend
# Run with:  uvicorn app:app --host 127.0.0.1 --port 8000
# """

# import os, re, time, json, threading
# from collections import deque, Counter
# from pathlib import Path

# import cv2
# import numpy as np
# import joblib

# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import StreamingResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware
# from starlette.websockets import WebSocketState
# import asyncio

# from cvzone.HandTrackingModule import HandDetector

# # ── Paths — always resolved relative to THIS file ──────────────────────────────
# HERE       = Path(__file__).resolve().parent
# MODEL_PATH = Path(os.getenv("MODEL_PATH", str(HERE / "asl_model.joblib")))
# ASSETS_DIR = HERE / "assets"
# ASSETS_DIR.mkdir(exist_ok=True)

# # ── Config ─────────────────────────────────────────────────────────────────────
# SEQ_LEN       = 45
# SMOOTH_WINDOW = 10
# PRED_EVERY    = 1
# HOLD_SECONDS  = float(os.getenv("HOLD_SECONDS", "2.5"))

# # ── Word / Phrase Database ─────────────────────────────────────────────────────
# WORD_DB = {
#     "hello":   {"label": "HELLO",   "video": "/assets/hello.mp4"},
#     "goodbye": {"label": "GOODBYE", "video": "/assets/goodbye.mp4"},
#     "my":      {"label": "MY",      "video": "/assets/my.mp4"},
#     "magic":   {"label": "MAGIC",   "video": "/assets/magic.mp4"},
#     "what":    {"label": "WHAT",    "video": "/assets/what.mp4"},
#     "yes":     {"label": "YES",     "video": "/assets/yes.mp4"},
#     "no":      {"label": "NO",      "video": "/assets/no.mp4"},
#     "your":    {"label": "YOUR",    "video": "/assets/your.mp4"},
#     "please":  {"label": "PLEASE",  "video": "/assets/please.mp4"},
#     "sorry":   {"label": "SORRY",   "video": "/assets/sorry.mp4"},
# }

# PHRASES = {
#     "thank you":    {"label": "THANK YOU",    "video": "/assets/thank_you.mp4"},
#     "name is":      {"label": "NAME IS",      "video": "/assets/name_is.mp4"},
#     "harry potter": {"label": "HARRY POTTER", "video": "/assets/harry_potter.mp4"},
# }

# # ── Helpers ────────────────────────────────────────────────────────────────────
# def canon(s: str) -> str:
#     return re.sub(r"\s+", " ", s.replace("_", " ").strip()).upper()

# def majority_vote(preds):
#     if not preds:
#         return None
#     return Counter(preds).most_common(1)[0][0]

# def two_hand_landmarks(hands) -> np.ndarray:
#     out = np.zeros((2, 21, 3), dtype=np.float32)
#     if not hands:
#         return out
#     hands = hands[:2]
#     if len(hands) == 1:
#         out[0] = np.array(hands[0]["lmList"], dtype=np.float32)
#         return out
#     for h in hands:
#         lm = np.array(h["lmList"], dtype=np.float32)
#         if h.get("type") == "Left":
#             out[0] = lm
#         elif h.get("type") == "Right":
#             out[1] = lm
#     if (out.sum(axis=(1, 2)) == 0).any():
#         lmA = np.array(hands[0]["lmList"], dtype=np.float32)
#         lmB = np.array(hands[1]["lmList"], dtype=np.float32)
#         if lmA[0, 0] <= lmB[0, 0]:
#             out[0], out[1] = lmA, lmB
#         else:
#             out[0], out[1] = lmB, lmA
#     return out

# def tokenise(sentence: str) -> list:
#     cleaned = re.sub(r"[^A-Za-z\s]", " ", sentence)
#     words   = [w.lower() for w in cleaned.split() if w.strip()]
#     tokens  = []
#     i = 0
#     while i < len(words):
#         if i + 1 < len(words):
#             phrase2 = f"{words[i]} {words[i+1]}"
#             if phrase2 in PHRASES:
#                 meta = PHRASES[phrase2]
#                 tokens.append({"kind": "word", "text": phrase2,
#                                 "label": meta["label"], "video": meta["video"]})
#                 i += 2
#                 continue
#         w = words[i]
#         if w in WORD_DB:
#             meta = WORD_DB[w]
#             tokens.append({"kind": "word", "text": w,
#                             "label": meta["label"], "video": meta["video"]})
#         else:
#             for ch in w.upper():
#                 if ch.isalpha():
#                     tokens.append({"kind": "letter", "text": ch, "label": ch})
#         i += 1
#     return tokens

# # ── ASL State ──────────────────────────────────────────────────────────────────
# class ASLState:
#     def __init__(self):
#         self.lock = threading.RLock()

#         self.queue            = []
#         self.current_idx      = 0
#         self.points           = 0
#         self.hold_started     = None
#         self.hold_progress    = 0.0
#         self.waiting_for_next = False
#         self.completed_label  = None

#         self.last_pred    = None
#         self.top3_text    = ""
#         self.buffer_fill  = 0
#         self.lm_buffer    = deque(maxlen=SEQ_LEN)
#         self.pred_buffer  = deque(maxlen=SMOOTH_WINDOW)

#         # Logging throttle — print comparison result at most once per second
#         self._last_log_time = 0.0

#         self.last_frame   = None
#         self.cap          = cv2.VideoCapture(0)
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
#         self.detector     = HandDetector(maxHands=2)

#         print(f"[ASL] Loading model from: {MODEL_PATH}")
#         if not MODEL_PATH.exists():
#             raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train.py first.")
#         bundle = joblib.load(MODEL_PATH)
#         self.model = bundle["model"]
#         self.expected_features = getattr(self.model, "n_features_in_", None)
#         print(f"[ASL] ✅ Model loaded")
#         print(f"[ASL] Classes ({len(self.model.classes_)}): {sorted(self.model.classes_)}")
#         print(f"[ASL] Expected features: {self.expected_features}")

#         self.running = True
#         self._thread = threading.Thread(target=self._loop, daemon=True)
#         self._thread.start()

#     # ── Public API ─────────────────────────────────────────────────────────────
#     def set_sentence(self, sentence: str):
#         tokens = tokenise(sentence)
#         with self.lock:
#             self.queue            = tokens
#             self.current_idx      = 0
#             self.points           = 0
#             self.hold_started     = None
#             self.hold_progress    = 0.0
#             self.waiting_for_next = False
#             self.completed_label  = None
#             self.lm_buffer.clear()
#             self.pred_buffer.clear()
#             self.last_pred        = None
#             self.top3_text        = ""
#             self.buffer_fill      = 0

#         print(f"\n[ASL] ── New sentence: {sentence!r}")
#         for i, t in enumerate(tokens):
#             print(f"  [{i}] kind={t['kind']:6s}  label={t['label']!r}")

#     def next_step(self):
#         """Advance to next token — called when user clicks Next."""
#         with self.lock:
#             t = self._target()
#             if t is None:
#                 return
#             prev = t['label']
#             self.current_idx     += 1
#             self.hold_started     = None
#             self.hold_progress    = 0.0
#             self.waiting_for_next = False
#             self.completed_label  = None
#             self.lm_buffer.clear()
#             self.pred_buffer.clear()
#             self.last_pred        = None
#             self.top3_text        = ""
#             next_t = self._target()
#             print(f"[ASL] ➡  '{prev}' done → next: {next_t['label'] if next_t else '(finished)'}")

#     def snapshot(self) -> dict:
#         with self.lock:
#             target = self._target()
#             return {
#                 "pred":            self.last_pred,
#                 "top3":            self.top3_text,
#                 "buffer":          self.buffer_fill,
#                 "seqLen":          SEQ_LEN,
#                 "holdProgress":    self.hold_progress,
#                 "points":          self.points,
#                 "target":          target,
#                 "currentIndex":    self.current_idx,
#                 "total":           len(self.queue),
#                 "done":            (target is None and len(self.queue) > 0),
#                 "waitingForNext":  self.waiting_for_next,
#                 "completedLabel":  self.completed_label,
#             }

#     def get_jpeg(self) -> bytes | None:
#         with self.lock:
#             frame = self.last_frame
#         if frame is None:
#             return None
#         ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
#         return buf.tobytes() if ok else None

#     # ── Private ────────────────────────────────────────────────────────────────
#     def _target(self):
#         if not self.queue or self.current_idx >= len(self.queue):
#             return None
#         return self.queue[self.current_idx]

#     def _advance_if_correct(self, smoothed_pred):
#         with self.lock:
#             if self.waiting_for_next:
#                 return

#             target = self._target()

#             # ── Throttled logging so terminal stays readable ────────────────
#             now = time.monotonic()
#             do_log = (now - self._last_log_time) >= 1.0

#             if target is None:
#                 if do_log:
#                     print("[ASL] _advance: no target (queue empty or not started)")
#                     self._last_log_time = now
#                 return

#             if target["kind"] != "letter":
#                 if do_log:
#                     print(f"[ASL] _advance: target is a WORD token ({target['label']!r}) — waiting for user to click Next after video")
#                     self._last_log_time = now
#                 return

#             if smoothed_pred is None:
#                 if do_log:
#                     print("[ASL] _advance: smoothed_pred is None (buffer filling…)")
#                     self._last_log_time = now
#                 return

#             predicted = canon(str(smoothed_pred))
#             expected  = canon(str(target["label"]))
#             match     = (predicted == expected)

#             if do_log:
#                 print(f"[ASL] comparing  pred={predicted!r}  expected={expected!r}  match={match}  "
#                       f"hold={self.hold_progress:.2f}  progress={round(self.hold_progress*100)}%")
#                 self._last_log_time = now

#             if match:
#                 if self.hold_started is None:
#                     self.hold_started = now
#                     print(f"[ASL] ⏱  Hold started for '{expected}'")

#                 elapsed = now - self.hold_started
#                 self.hold_progress = min(1.0, elapsed / HOLD_SECONDS)

#                 if elapsed >= HOLD_SECONDS:
#                     self.points          += 10
#                     self.hold_progress    = 1.0
#                     self.waiting_for_next = True
#                     self.completed_label  = expected
#                     print(f"[ASL] ✅ '{expected}' correct! +10 pts  total={self.points}")
#             else:
#                 if self.hold_started is not None:
#                     print(f"[ASL] ✗  Hold broken for '{expected}' (got {predicted!r})")
#                 self.hold_started  = None
#                 self.hold_progress = 0.0

#     # ── Camera / inference loop ────────────────────────────────────────────────
#     # Mirrors predict_live.py exactly:
#     #   1. findHands() every frame
#     #   2. No hands → immediate buffer reset
#     #   3. Landmarks appended every frame with a hand
#     def _loop(self):
#         frame_idx = 0

#         while self.running:
#             ok, img = self.cap.read()
#             if not ok:
#                 time.sleep(0.01)
#                 continue

#             with self.lock:
#                 self.last_frame = img.copy()

#             # 1 — detect every frame
#             hands, _ = self.detector.findHands(img, draw=False)

#             # 2 — no hands → immediate reset
#             if not hands:
#                 with self.lock:
#                     self.lm_buffer.clear()
#                     self.pred_buffer.clear()
#                     self.last_pred   = None
#                     self.top3_text   = ""
#                     self.buffer_fill = 0
#                     if not self.waiting_for_next:
#                         self.hold_started  = None
#                         self.hold_progress = 0.0
#                 frame_idx += 1
#                 time.sleep(0.001)
#                 continue

#             # 3 — append every frame with a hand
#             lm2 = two_hand_landmarks(hands)
#             with self.lock:
#                 self.lm_buffer.append(lm2)
#                 self.buffer_fill = len(self.lm_buffer)

#             # Inference when buffer is full
#             if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
#                 try:
#                     seq  = np.stack(self.lm_buffer, axis=0)  # (45,2,21,3)
#                     feat = seq.reshape(1, -1)

#                     if (self.expected_features is not None
#                             and feat.shape[1] != self.expected_features):
#                         feat = seq[:, 0, :, :].reshape(1, -1)

#                     pred_raw = self.model.predict(feat)[0]

#                     with self.lock:
#                         self.pred_buffer.append(pred_raw)
#                         smoothed = majority_vote(list(self.pred_buffer))
#                         self.last_pred = smoothed

#                         self.top3_text = ""
#                         if hasattr(self.model, "predict_proba"):
#                             probs   = self.model.predict_proba(feat)[0]
#                             top_idx = np.argsort(probs)[::-1][:3]
#                             self.top3_text = " | ".join(
#                                 f"{self.model.classes_[i]}:{probs[i]:.2f}"
#                                 for i in top_idx
#                             )

#                     self._advance_if_correct(smoothed)

#                 except Exception as e:
#                     with self.lock:
#                         self.last_pred = f"err:{type(e).__name__}"
#                         self.top3_text = str(e)[:80]
#                     print(f"[ASL] Inference error: {e}")

#             frame_idx += 1
#             time.sleep(0.001)


# # ── FastAPI ────────────────────────────────────────────────────────────────────
# app   = FastAPI(title="ASL Spellcaster")
# state = ASLState()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "http://localhost:3000",
#                    "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# # ── Debug endpoints ────────────────────────────────────────────────────────────
# @app.get("/debug")
# def debug():
#     """Open in browser to see what model is loaded and current game state."""
#     snap = state.snapshot()
#     return {
#         "model_path":        str(MODEL_PATH),
#         "model_exists":      MODEL_PATH.exists(),
#         "classes":           sorted(state.model.classes_.tolist()),
#         "num_classes":       len(state.model.classes_),
#         "expected_features": state.expected_features,
#         "cwd":               os.getcwd(),
#         "game": {
#             "queue_length":    len(state.queue),
#             "current_idx":     state.current_idx,
#             "current_target":  snap["target"],
#             "last_pred":       snap["pred"],
#             "hold_progress":   snap["holdProgress"],
#             "waiting_for_next": snap["waitingForNext"],
#             "points":          snap["points"],
#         }
#     }

# # ── MJPEG ──────────────────────────────────────────────────────────────────────
# def _mjpeg_generator():
#     delay = 1.0 / 15
#     last  = 0.0
#     while True:
#         now = time.time()
#         if now - last < delay:
#             time.sleep(0.002)
#             continue
#         frame = state.get_jpeg()
#         if frame is None:
#             time.sleep(0.02)
#             continue
#         last = now
#         yield (b"--frame\r\n"
#                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

# @app.get("/video")
# def video():
#     return StreamingResponse(_mjpeg_generator(),
#                              media_type="multipart/x-mixed-replace; boundary=frame")

# # ── WebSocket ──────────────────────────────────────────────────────────────────
# @app.websocket("/ws")
# async def ws_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     tick = 1.0 / 10

#     async def reader():
#         while True:
#             raw  = await websocket.receive_text()
#             data = json.loads(raw)
#             if data.get("type") == "set_sentence":
#                 state.set_sentence(data.get("sentence", ""))
#             elif data.get("type") == "next_step":
#                 state.next_step()

#     reader_task = asyncio.create_task(reader())
#     try:
#         await websocket.send_text(json.dumps(state.snapshot()))
#         while websocket.client_state == WebSocketState.CONNECTED:
#             try:
#                 await websocket.send_text(json.dumps(state.snapshot()))
#             except RuntimeError:
#                 break
#             await asyncio.sleep(tick)
#     except WebSocketDisconnect:
#         pass
#     finally:
#         reader_task.cancel()
#         try:
#             await reader_task
#         except Exception:
#             pass



import os
import time
import json
import threading
from collections import deque, Counter
import re
import asyncio








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
# WORD_DB = {
#     "hello": {"type": "word", "video": "/assets/hello.mp4"},
#     "thank": {"type": "word", "video": "/assets/thank_you.mp4"},
#     "you":   {"type": "word", "video": "/assets/you.mp4"},
#     "yes":   {"type": "word", "video": "/assets/yes.mp4"},
#     "no":    {"type": "word", "video": "/assets/no.mp4"},
# }
# ----------------------------
# Word & Phrase DB
# ----------------------------




WORD_DB = {
    "hello": {"label": "HELLO", "video": "/assets/testvid.mp4"},
    "goodbye": {"label": "GOODBYE", "video": "/assets/GOODBYE.mp4"},
    "my": {"label": "MY", "video": "/assets/MY.mp4"},
    "magic": {"label": "MAGIC", "video": "/assets/MAGIC.mp4"},
    "what": {"label": "WHAT", "video": "/assets/WHAT.mp4"},
    "please": {"label": "please", "video": "/assets/PLEASE.mp4"},
    "no": {"label": "NO", "video": "/assets/NO.mp4"},
    "your": {"label": "YOUR", "video": "/assets/YOUR.mp4"},
}




PHRASES = {
    "thank you": {"label": "THANK YOU", "video": "/assets/THANK_YOU.mp4"},
    "name is": {"label": "NAME IS", "video": "/assets/NAME_IS.mp4"},
    "harry potter": {"label": "HARRY POTTER", "video": "/assets/HARRY_POTTER.mp4"},
}




# ----------------------------
# Helpers
# ----------------------------




def canon(s: str) -> str:
    # canonical form: uppercase, spaces, no underscores, no extra whitespace
    return re.sub(r"\s+", " ", s.replace("_", " ").strip()).upper()








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




    # Fallback: assign leftmost wrist->slot0
    if (out.sum(axis=(1, 2)) == 0).any():
        lmA = np.array(hands[0]["lmList"], dtype=np.float32)
        lmB = np.array(hands[1]["lmList"], dtype=np.float32)
        if lmA[0, 0] <= lmB[0, 0]:
            out[0], out[1] = lmA, lmB
        else:
            out[0], out[1] = lmB, lmA




    return out
# ----------------------------
# Shared state (camera + model)
# ----------------------------
class ASLState:
    def __init__(self):
        # self.lock = threading.Lock()
        self.lock = threading.RLock()


        # bundle = joblib.load(MODEL_PATH)
        # self.model = bundle["model"]
        # self.detector = HandDetector(maxHands=2)  # or whatever predict_live.py uses


        # # self.infer = LiveInfer(self.model, self.detector, seq_len=SEQ_LEN, smooth=SMOOTH_WINDOW)




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
        self.detector = HandDetector(maxHands=2)




        self.lm_buffer = deque(maxlen=SEQ_LEN)
        self.pred_buffer = deque(maxlen=SMOOTH_WINDOW)




        # model
        bundle = joblib.load(MODEL_PATH)
        self.model = bundle["model"]


        # how many features the model expects (sklearn models have this)
        self.expected_features = getattr(self.model, "n_features_in_", None)
        print("MODEL expects features:", self.expected_features)




        # run loop thread
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()




    # def set_sentence(self, sentence: str):
    #     sentence = sentence.strip()
    #     tokens = [t for t in sentence.split() if t.strip()]
    #     q = []
    #     for t in tokens:
    #         low = t.lower()
    #         if low in WORD_DB:
    #             q.append({"kind": "word", "text": low, "video": WORD_DB[low]["video"]})
    #         else:
    #             # fallback: spell it
    #             for ch in t.upper():
    #                 if ch.isalpha():
    #                     q.append({"kind": "letter", "text": ch})
    #     with self.lock:
    #         self.sentence = sentence
    #         self.queue = q
    #         self.current_idx = 0
    #         self.points = 0
    #         self.hold_started_at = None
    #         self.hold_progress = 0.0




    #         # reset buffers when new session starts
    #         self.lm_buffer.clear()
    #         self.pred_buffer.clear()
    #         self.last_pred = None
    #         self.top3_text = ""








    def set_sentence(self, sentence: str):
        sentence = sentence.strip()




        # normalize punctuation -> spaces
        cleaned = re.sub(r"[^A-Za-z\s]", " ", sentence)
        words = [w.lower() for w in cleaned.split() if w.strip()]




        q = []
        i = 0
        while i < len(words):
            # try 2-word phrase (you can extend to 3 if needed)
            if i + 1 < len(words):
                phrase2 = f"{words[i]} {words[i+1]}"
                if phrase2 in PHRASES:
                    meta = PHRASES[phrase2]
                    q.append({
                        "kind": "word",
                        "text": phrase2,
                        "label": meta["label"],
                        "video": meta["video"],
                    })
                    i += 2
                    continue




            w = words[i]
            if w in WORD_DB:
                meta = WORD_DB[w]
                q.append({
                    "kind": "word",
                    "text": w,
                    "label": meta["label"],
                    "video": meta["video"],
                })
            else:
                # fallback: spell it
                for ch in w.upper():
                    if ch.isalpha():
                        q.append({
                            "kind": "letter",
                            "text": ch,
                            "label": ch,
                        })
            i += 1




        with self.lock:
            self.sentence = sentence
            self.queue = q
            self.current_idx = 0
            self.points = 0
            self.hold_started_at = None
            self.hold_progress = 0.0
            self.lm_buffer.clear()
            self.pred_buffer.clear()
            self.last_pred = None
            self.top3_text = ""




    # def get_target(self):
    #     with self.lock:
    #         if not self.queue or self.current_idx >= len(self.queue):
    #             return None
    #         return self.queue[self.current_idx]




    def _get_target_nolock(self):
        if not self.queue or self.current_idx >= len(self.queue):
            return None
        return self.queue[self.current_idx]




    def get_target(self):
        with self.lock:
            return self._get_target_nolock()








    # def advance_if_correct(self, pred: str):
    #     with self.lock:
    #         target = self.get_target()
    #         if target is None or pred is None:
    #             return




    #         expected = target.get("label")  # label matches model classes (or letter)
    #         now = time.time()




    #         if pred == expected:
    #             if self.hold_started_at is None:
    #                 self.hold_started_at = now




    #             elapsed = now - self.hold_started_at
    #             self.hold_progress = min(1.0, elapsed / HOLD_SECONDS)




    #             if elapsed >= HOLD_SECONDS:
    #                 self.points += 10
    #                 self.current_idx += 1
    #                 self.hold_started_at = None
    #                 self.hold_progress = 0.0
    #                 self.lm_buffer.clear()
    #                 self.pred_buffer.clear()
    #         else:
    #             self.hold_started_at = None
    #             self.hold_progress = 0.0




    # def advance_if_correct(self, pred: str):
    #     with self.lock:
    #         target = self._get_target_nolock()
    #         if target is None or pred is None:
    #             return




    #         expected = target.get("label")
    #         now = time.time()




    #         if pred == expected:
    #             if self.hold_started_at is None:
    #                 self.hold_started_at = now




    #             elapsed = now - self.hold_started_at
    #             self.hold_progress = min(1.0, elapsed / HOLD_SECONDS)




    #             if elapsed >= HOLD_SECONDS:
    #                 self.points += 10
    #                 self.current_idx += 1
    #                 self.hold_started_at = None
    #                 self.hold_progress = 0.0
    #                 self.lm_buffer.clear()
    #                 self.pred_buffer.clear()
    #         else:
    #             self.hold_started_at = None
    #             self.hold_progress = 0.0




    def advance_if_correct(self, pred: str):
        with self.lock:
            target = self._get_target_nolock()
            if target is None or pred is None:
                return




            expected = target.get("label")
            if expected is None:
                return




            now = time.time()




            # ✅ canonical compare
            pred_c = canon(str(pred))
            exp_c  = canon(str(expected))




            if pred_c == exp_c:
                if self.hold_started_at is None:
                    self.hold_started_at = now




                elapsed = now - self.hold_started_at
                self.hold_progress = min(1.0, elapsed / HOLD_SECONDS)




                if elapsed >= HOLD_SECONDS:
                    self.points += 10
                    self.current_idx += 1
                    self.hold_started_at = None
                    self.hold_progress = 0.0
                    self.lm_buffer.clear()
                    self.pred_buffer.clear()
            else:
                self.hold_started_at = None
                self.hold_progress = 0.0




    def _loop(self):
        """
        Camera + hand landmarks + model inference loop.


        Key changes to prevent "freezing when buffer fills":
        1) Always update self.last_frame immediately after reading frame (so /video keeps moving).
        2) Throttle hand detection + inference so heavy work doesn't block capture as much.
        3) (Optional) disable predict_proba/top3 for speed.
        """
        frame_idx = 0
        missing = 0
        MISSING_RESET = 5


        DETECT_EVERY = 2   # run hand detection every N frames (2 = every other frame)
        # Increase these if you still see stutter
        # DETECT_EVERY = 3


        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue


            # ✅ Always refresh streaming frame immediately (prevents MJPEG "freeze")
            with self.lock:
                self.last_frame = frame


            # Throttle detection work
            hands = []
            if frame_idx % DETECT_EVERY == 0:
                try:
                    hands, _ = self.detector.findHands(frame, draw=False)
                except Exception:
                    hands = []


            if not hands:
                missing += 1
                if missing >= MISSING_RESET:
                    with self.lock:
                        self.lm_buffer.clear()
                        self.pred_buffer.clear()
                        self.last_pred = None
                        self.top3_text = ""
                        self.buffer_fill = 0
                frame_idx += 1
                continue
            else:
                missing = 0


            # Build 2-hand landmarks (2,21,3)
            lm2 = two_hand_landmarks(hands)


            with self.lock:
                self.lm_buffer.append(lm2)
                self.buffer_fill = len(self.lm_buffer)
           
            if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
                try:
                    seq = np.stack(self.lm_buffer, axis=0)   # either (45,2,21,3) OR (45,21,3)


                    # Build features in a way that matches what the model expects.
                    # If model was trained on 1-hand (2835), reduce 2-hand -> 1-hand.
                    if self.expected_features is not None:
                        if seq.ndim == 4:
                            # seq is (45,2,21,3)
                            feat2 = seq.reshape(1, -1)  # 5670


                            if feat2.shape[1] == self.expected_features:
                                feat = feat2
                            else:
                                # fallback: use only first hand => (45,21,3) => 2835
                                feat1 = seq[:, 0, :, :].reshape(1, -1)
                                feat = feat1
                        else:
                            # seq is already (45,21,3)
                            feat = seq.reshape(1, -1)
                    else:
                        # no n_features_in_, just flatten whatever we have
                        feat = seq.reshape(1, -1)


                    pred = self.model.predict(feat)[0]


                    with self.lock:
                        self.pred_buffer.append(pred)
                        smoothed = majority_vote(list(self.pred_buffer))
                        self.last_pred = smoothed


                        self.top3_text = ""
                        if hasattr(self.model, "predict_proba"):
                            probs = self.model.predict_proba(feat)[0]
                            top_idx = np.argsort(probs)[::-1][:3]
                            top3 = [(self.model.classes_[i], float(probs[i])) for i in top_idx]
                            self.top3_text = " | ".join([f"{c}:{p:.2f}" for c, p in top3])


                    self.advance_if_correct(self.last_pred)


                except Exception as e:
                    with self.lock:
                        self.last_pred = f"infer_err:{type(e).__name__}"
                        self.top3_text = str(e)[:120]  # short error text


            # ✅ Only infer occasionally (PRED_EVERY controls how often)
            # If your UI still stutters, increase PRED_EVERY at top of file (e.g. 6 or 8)
            # if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
            #     try:
            #         seq = np.stack(self.lm_buffer, axis=0)  # (SEQ_LEN,2,21,3)
            #         feat = seq.reshape(1, -1)


            #         pred = self.model.predict(feat)[0]


            #         with self.lock:
            #             self.pred_buffer.append(pred)
            #             self.last_pred = majority_vote(list(self.pred_buffer))


            #             # OPTIONAL (expensive): top3 probabilities
            #             # Commented out for speed. Re-enable later if needed.
            #             self.top3_text = ""
            #             # if hasattr(self.model, "predict_proba"):
            #             #     probs = self.model.predict_proba(feat)[0]
            #             #     top_idx = np.argsort(probs)[::-1][:3]
            #             #     top3 = [(self.model.classes_[i], float(probs[i])) for i in top_idx]
            #             #     self.top3_text = " | ".join([f"{c}:{p:.2f}" for c, p in top3])


            #         # update progression based on smoothed pred
            #         self.advance_if_correct(self.last_pred)


            #     except Exception as e:
            #         # Don't let inference errors kill streaming
            #         with self.lock:
            #             self.top3_text = f"infer_err:{type(e).__name__}"
            #         # small breather so it doesn't spam
            #         time.sleep(0.005)


            frame_idx += 1
            # Tiny sleep reduces CPU pegging and improves responsiveness on macOS
            time.sleep(0.001)
    # def _loop(self):
    #     """
    #     Camera + hand landmarks + model inference loop.
    #     Stores latest frame and latest prediction.
    #     """
    #     frame_idx = 0
    #     missing = 0
    #     MISSING_RESET = 5  # reset after N missing frames (prevents flicker resets)




    #     while self.running:
    #         ok, frame = self.cap.read()
    #         if not ok:
    #             time.sleep(0.01)
    #             continue
    #         with self.lock:
    #             self.last_frame = frame




    #         # hands, annotated = self.detector.findHands(frame)
    #         hands, annotated = self.detector.findHands(frame, draw=False)
    #         annotated = frame  # keep raw frame for streaming




    #         if not hands:
    #             missing += 1
    #             if missing >= MISSING_RESET:
    #                 with self.lock:
    #                     self.lm_buffer.clear()
    #                     self.pred_buffer.clear()
    #                     self.last_pred = None
    #                     self.top3_text = ""
    #                     self.buffer_fill = 0
    #             with self.lock:
    #                 self.last_frame = annotated
    #             frame_idx += 1
    #             continue
    #         else:
    #             missing = 0




    #         # hand = hands[0]
    #         # lm = np.array(hand["lmList"], dtype=np.float32)  # (21,3)
    #         # lm = normalize_landmarks(lm)




    #         # with self.lock:
    #         #     self.lm_buffer.append(lm)
    #         #     self.buffer_fill = len(self.lm_buffer)




    #         # # Predict when buffer full
    #         # if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
    #         #     seq = np.stack(self.lm_buffer, axis=0)  # (SEQ_LEN,21,3)
    #         #     feat = seq.reshape(1, -1)




    #         lm2 = two_hand_landmarks(hands)  # (2,21,3)




    #         with self.lock:
    #             self.lm_buffer.append(lm2)
    #             self.buffer_fill = len(self.lm_buffer)




    #         if len(self.lm_buffer) == SEQ_LEN and (frame_idx % PRED_EVERY == 0):
    #             seq = np.stack(self.lm_buffer, axis=0)  # (45,2,21,3)
    #             feat = seq.reshape(1, -1)
    #             pred = self.model.predict(feat)[0]
       
    #             with self.lock:
    #                 self.pred_buffer.append(pred)
    #                 smoothed = majority_vote(list(self.pred_buffer))
    #                 self.last_pred = smoothed




    #                 # top3
    #                 self.top3_text = ""
    #                 if hasattr(self.model, "predict_proba"):
    #                     probs = self.model.predict_proba(feat)[0]
    #                     top_idx = np.argsort(probs)[::-1][:3]
    #                     top3 = [(self.model.classes_[i], float(probs[i])) for i in top_idx]
    #                     self.top3_text = " | ".join([f"{c}:{p:.2f}" for c, p in top3])




    #             # update progression based on smoothed pred
    #             self.advance_if_correct(self.last_pred)




    #         with self.lock:
    #             self.last_frame = annotated




    #         frame_idx += 1




    def get_jpeg(self):
        with self.lock:
            frame = self.last_frame
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return buf.tobytes()




    # def snapshot_state(self):
    #     with self.lock:
    #         target = self.get_target()
    #         done = (target is None)




    #         return {
    #             "pred": self.last_pred,
    #             "top3": self.top3_text,
    #             "buffer": self.buffer_fill,
    #             "seqLen": SEQ_LEN,
    #             "holdProgress": self.hold_progress,
    #             "points": self.points,
    #             "target": target,
    #             "currentIndex": self.current_idx,
    #             "total": len(self.queue),
    #             "done": done,
    #         }




    def snapshot_state(self):
        with self.lock:
            target = self._get_target_nolock()
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




# @app.websocket("/ws")
# async def ws(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         # send initial state
#         await websocket.send_text(json.dumps(state.snapshot_state()))
#         while True:
#             # client can send commands
#             msg = await websocket.receive_text()
#             data = json.loads(msg)




#             if data.get("type") == "set_sentence":
#                 state.set_sentence(data.get("sentence", ""))




#             if data.get("type") == "skip_word":
#                 # For word tokens: advance (UI button after video plays)
#                 with state.lock:
#                     t = state.get_target()
#                     if t and t["kind"] == "word":
#                         state.current_idx += 1
#                         state.lm_buffer.clear()
#                         state.pred_buffer.clear()
#                         state.hold_started_at = None
#                         state.hold_progress = 0.0




#             # Always respond with current state
#             await websocket.send_text(json.dumps(state.snapshot_state()))




#     except WebSocketDisconnect:
#         return




# @app.websocket("/ws")
# async def ws(websocket: WebSocket):
#     await websocket.accept()




#     SEND_HZ = 10
#     tick = 1.0 / SEND_HZ




#     try:
#         # initial state
#         await websocket.send_text(json.dumps(state.snapshot_state()))




#         while True:
#             # Wait for a message, but don't block forever
#             try:
#                 msg = await asyncio.wait_for(websocket.receive_text(), timeout=tick)
#                 data = json.loads(msg)




#                 if data.get("type") == "set_sentence":
#                     state.set_sentence(data.get("sentence", ""))




#                 elif data.get("type") == "skip_word":
#                     with state.lock:
#                         t = state._get_target_nolock()
#                         if t and t["kind"] == "word":
#                             state.current_idx += 1
#                             state.lm_buffer.clear()
#                             state.pred_buffer.clear()
#                             state.hold_started_at = None
#                             state.hold_progress = 0.0




#             except asyncio.TimeoutError:
#                 # no message this tick; just stream state
#                 pass




#             # Always push current state
#             await websocket.send_text(json.dumps(state.snapshot_state()))




#     except WebSocketDisconnect:
#         return




from starlette.websockets import WebSocketState


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()


    SEND_HZ = 10
    tick = 1.0 / SEND_HZ


    async def reader_loop():
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)


            if data.get("type") == "set_sentence":
                state.set_sentence(data.get("sentence", ""))


            elif data.get("type") == "skip_word":
                with state.lock:
                    t = state._get_target_nolock()
                    if t and t["kind"] == "word":
                        state.current_idx += 1
                        state.lm_buffer.clear()
                        state.pred_buffer.clear()
                        state.hold_started_at = None
                        state.hold_progress = 0.0


    reader_task = asyncio.create_task(reader_loop())


    try:
        while True:
            # If client disconnected, stop sending
            if websocket.client_state != WebSocketState.CONNECTED:
                break


            try:
                await websocket.send_text(json.dumps(state.snapshot_state()))
            except RuntimeError:
                # happens if socket closed between checks
                break


            await asyncio.sleep(tick)


    except WebSocketDisconnect:
        pass
    finally:
        reader_task.cancel()
        # optional: swallow cancellation errors
        try:
            await reader_task
        except:
            pass

