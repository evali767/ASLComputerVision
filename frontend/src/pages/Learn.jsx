import { useEffect, useMemo, useState } from "react";
import { useAppState } from "../state/AppState";

const WORD_DB = new Set(["hello", "thank", "you", "yes", "no"]);

function tokenizeSentence(sentence) {
  const tokens = sentence.trim().split(/\s+/).filter(Boolean);
  const queue = [];
  for (const w of tokens) {
    const low = w.toLowerCase();
    if (WORD_DB.has(low)) queue.push({ kind: "word", text: low, video: `/assets/${low}.mp4` });
    else for (const ch of w.toUpperCase()) if (/[A-Z]/.test(ch)) queue.push({ kind: "letter", text: ch });
  }
  return queue;
}

export default function Learn() {
  const { houseKey, addHousePoints } = useAppState();

  const [sentence, setSentence] = useState("hello thank you");
  const [queue, setQueue] = useState([]);
  const [idx, setIdx] = useState(0);

  const [pred, setPred] = useState(null);
  const [top3, setTop3] = useState("");
  const [holdProgress, setHoldProgress] = useState(0);
  const [points, setPoints] = useState(0);

  const target = queue[idx] ?? null;
  const done = queue.length > 0 && idx >= queue.length;

  const HOLD_SECONDS = 2.5;
  const TICK_MS = 120;

  const start = () => {
    const q = tokenizeSentence(sentence);
    setQueue(q);
    setIdx(0);
    setPoints(0);
    setPred(null);
    setTop3("");
    setHoldProgress(0);
  };

  // Simulated predictions (swap to backend later)
  useEffect(() => {
    if (!target || done) return;

    const timer = setInterval(() => {
      if (target.kind === "word") {
        setPred(null);
        setTop3("");
        setHoldProgress(0);
        return;
      }

      const correct = Math.random() < 0.7;
      const guess = correct ? target.text : randomOtherLetter(target.text);

      setPred(guess);

      const p1 = correct ? 0.75 + Math.random() * 0.2 : 0.35 + Math.random() * 0.15;
      const p2 = (1 - p1) * 0.6;
      const p3 = (1 - p1) * 0.4;
      const alt1 = correct ? randomOtherLetter(target.text) : target.text;
      const alt2 = randomOtherLetter(alt1);
      setTop3(`${guess}:${p1.toFixed(2)} | ${alt1}:${p2.toFixed(2)} | ${alt2}:${p3.toFixed(2)}`);

      setHoldProgress((prev) => {
        if (guess === target.text) {
          const next = prev + (TICK_MS / 1000) / HOLD_SECONDS;
          if (next >= 1) {
            // +10 personal points
            setPoints((p) => p + 10);

            // +10 house points (only if house chosen)
            addHousePoints(10);

            setIdx((i) => i + 1);
            return 0;
          }
          return next;
        }
        return 0;
      });
    }, TICK_MS);

    return () => clearInterval(timer);
  }, [target, done, addHousePoints]);

  const targetLabel = useMemo(() => {
    if (!target) return "(none)";
    return target.kind === "letter" ? `Letter: ${target.text}` : `Word: ${target.text}`;
  }, [target]);

  return (
    <div className="grid">
      <div className="card">
        <h3>Your Camera</h3>
        <div className="mockVideo">
          <div className="small">Camera preview placeholder</div>
          <div className="small">(Backend stream goes here later)</div>
        </div>
        <div className="small">Buffer: — / —</div>
      </div>

      <div className="card">
        <h3>Practice</h3>

        <div className="row">
          <input
            className="input"
            value={sentence}
            onChange={(e) => setSentence(e.target.value)}
            placeholder="Type a sentence to sign..."
          />
          <button className="btn" onClick={start}>
            Start
          </button>
        </div>

        <div className="target">
          <div><b>Current:</b> {targetLabel}</div>
          <div className="small">
            Step {queue.length ? Math.min(idx + 1, queue.length) : 0} / {queue.length}
          </div>
          <div className="small">
            House scoring: {houseKey === "default" ? "Choose a House to contribute points" : "ON ✅"}
          </div>
          <div className="small">Session points: <b>{points}</b></div>
        </div>

        {target?.kind === "word" ? (
          <div className="wordBox">
            <div className="small">Word in database → tutorial video (placeholder).</div>
            <div className="videoMock">
              <div className="small">Video: {target.video}</div>
            </div>
            <button className="btn" onClick={() => setIdx((i) => i + 1)}>
              I watched it → Next
            </button>
          </div>
        ) : (
          <div className="checkBox">
            <div className="pred"><b>Pred:</b> {pred ?? "..."}</div>
            <div className="small">{top3}</div>

            <div className="progressWrap">
              <div className="progressBar">
                <div className="progressFill" style={{ width: `${Math.round(holdProgress * 100)}%` }} />
              </div>
              <div className="small">Hold correct sign: {Math.round(holdProgress * 100)}%</div>
            </div>
          </div>
        )}

        {done ? (
          <div className="done">
            ✅ Finished! Session points: <b>{points}</b>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function randomOtherLetter(except) {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").filter((c) => c !== except);
  return letters[Math.floor(Math.random() * letters.length)];
}