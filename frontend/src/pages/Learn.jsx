import { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "../state/AppState";




export default function Learn() {
  const { houseKey, addHousePoints } = useAppState();


  const [sentence, setSentence] = useState("hello thank you");
  // const [queue, setQueue] = useState([]);
  // const [idx, setIdx] = useState(0);


  const [pred, setPred] = useState(null);
  const [top3, setTop3] = useState("");
  const [holdProgress, setHoldProgress] = useState(0);
  const [points, setPoints] = useState(0);


  // const target = queue[idx] ?? null;
  // const done = queue.length > 0 && idx >= queue.length;


  const wsRef = useRef(null);
  const [gameState, setGameState] = useState(null);


  const target = gameState?.target ?? null;
  const done = gameState?.done ?? false;


  const HOLD_SECONDS = 2.5;
  const TICK_MS = 120;


  const prevPointsRef = useRef(0);


  // const start = () => {
  //   const q = tokenizeSentence(sentence);
  //   setQueue(q);
  //   setIdx(0);
  //   setPoints(0);
  //   setPred(null);
  //   setTop3("");
  //   setHoldProgress(0);
  // };
  const start = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.log("WS not connected yet");
      return;
    }


    prevPointsRef.current = 0;   // ✅ reset delta tracker


    // reset UI-side mirrors (optional)
    setPred(null);
    setTop3("");
    setHoldProgress(0);
    setPoints(0);


    wsRef.current.send(
      JSON.stringify({
        type: "set_sentence",
        sentence,
      })
    );
  };


  // Simulated predictions (swap to backend later)
  // useEffect(() => {
  //   if (!target || done) return;


  //   const timer = setInterval(() => {
  //     if (target.kind === "word") {
  //       setPred(null);
  //       setTop3("");
  //       setHoldProgress(0);
  //       return;
  //     }


  //     const correct = Math.random() < 0.7;
  //     const guess = correct ? target.text : randomOtherLetter(target.text);


  //     setPred(guess);


  //     const p1 = correct ? 0.75 + Math.random() * 0.2 : 0.35 + Math.random() * 0.15;
  //     const p2 = (1 - p1) * 0.6;
  //     const p3 = (1 - p1) * 0.4;
  //     const alt1 = correct ? randomOtherLetter(target.text) : target.text;
  //     const alt2 = randomOtherLetter(alt1);
  //     setTop3(`${guess}:${p1.toFixed(2)} | ${alt1}:${p2.toFixed(2)} | ${alt2}:${p3.toFixed(2)}`);


  //     setHoldProgress((prev) => {
  //       if (guess === target.text) {
  //         const next = prev + (TICK_MS / 1000) / HOLD_SECONDS;
  //         if (next >= 1) {
  //           // +10 personal points
  //           setPoints((p) => p + 10);


  //           // +10 house points (only if house chosen)
  //           addHousePoints(10);


  //           setIdx((i) => i + 1);
  //           return 0;
  //         }
  //         return next;
  //       }
  //       return 0;
  //     });
  //   }, TICK_MS);


  //   return () => clearInterval(timer);
  // }, [target, done, addHousePoints]);


  useEffect(() => {
    if (!gameState) return;


    const newPoints = gameState.points ?? 0;
    const prev = prevPointsRef.current;


    if (newPoints > prev) {
      const delta = newPoints - prev;
      addHousePoints(delta); // contributes to house if selected
      prevPointsRef.current = newPoints;
    }
  }, [gameState, addHousePoints]);


  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");
    wsRef.current = ws;


    ws.onopen = () => console.log("✅ WS connected");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setGameState(data);


      // keep local points state in sync if you still want it
      if (typeof data.points === "number") setPoints(data.points);
      if (typeof data.holdProgress === "number") setHoldProgress(data.holdProgress);
      if (typeof data.pred !== "undefined") setPred(data.pred);
      if (typeof data.top3 !== "undefined") setTop3(data.top3);
    };


    ws.onerror = (e) => console.log("WS error", e);
    ws.onclose = () => console.log("❌ WS closed");


    return () => ws.close();
  }, []);


  // const targetLabel = useMemo(() => {
  //   if (!target) return "(none)";
  //   return target.kind === "letter" ? `Letter: ${target.text}` : `Word: ${target.text}`;
  // }, [target]);
  const targetLabel = useMemo(() => {
    if (!target) return "(none)";
    const label = target.label ?? target.text;
    return target.kind === "letter" ? `Letter: ${label}` : `Word: ${label}`;
  }, [target]);


  return (
    <div className="grid">
      <div className="card">
        <h3>Your Camera</h3>
        <div className="mockVideo" style={{ padding: 0 }}>
          <img
            src="http://127.0.0.1:8000/video"
            alt="Live Camera"
            style={{ width: "100%", borderRadius: 12, display: "block" }}
          />
        </div>


        <div className="small">
          Buffer: {gameState?.buffer ?? "—"} / {gameState?.seqLen ?? "—"}
        </div>
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
                Step {gameState?.total ? Math.min((gameState?.currentIndex ?? 0) + 1, gameState.total) : 0} / {gameState?.total ?? 0}
            </div>
            <div className="small">
                House scoring: {houseKey === "default" ? "Choose a House to contribute points" : "ON ✅"}
            </div>
            <div className="small">Session points: <b>{points}</b></div>
            </div>
            <div className="checkBox" style={{ marginTop: 12 }}>
    <div className="pred"><b>Live Pred:</b> {pred ?? "..."}</div>
    <div className="small">{top3 ?? ""}</div>

    <div className="progressWrap">
        <div className="progressBar">
        <div
            className="progressFill"
            style={{ width: `${Math.round((holdProgress ?? 0) * 100)}%` }}
        />
        </div>
        <div className="small">Hold: {Math.round((holdProgress ?? 0) * 100)}%</div>
    </div>
    </div>

        {target?.kind === "word" ? (
          <div className="wordBox">
            <div className="small">Word in database → tutorial video (placeholder).</div>
            <div className="videoMock" style={{ padding: 0, overflow: "hidden" }}>
            <video
                key={target.video}
                src={target.video}          // should be "/assets/testvid.mp4"
                controls
                autoPlay
                muted
                loop
                playsInline
                style={{ width: "100%", display: "block", borderRadius: 16 }}
                onError={() => console.log("VIDEO FAILED:", target.video)}
            />
            </div>
            <button
              className="btn"
              onClick={() => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: "skip_word" }));
                }
              }}
            >
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
