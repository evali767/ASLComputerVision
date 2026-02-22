// import { useEffect, useMemo, useRef, useState } from "react";
// import { useAppState } from "../state/AppState";

// export default function Learn() {
//   const { houseKey, addHousePoints } = useAppState();

//   const [sentence, setSentence]         = useState("eva");   // default: pure letters so detection is exercised immediately
//   const [gameState, setGameState]       = useState(null);
//   const [pred, setPred]                 = useState(null);
//   const [top3, setTop3]                 = useState("");
//   const [holdProgress, setHoldProgress] = useState(0);
//   const [points, setPoints]             = useState(0);
//   const [wsReady, setWsReady]           = useState(false);
//   const [showDebug, setShowDebug]       = useState(true);   // toggle debug strip

//   const wsRef         = useRef(null);
//   const prevPointsRef = useRef(0);

//   const target         = gameState?.target         ?? null;
//   const done           = gameState?.done           ?? false;
//   const waitingForNext = gameState?.waitingForNext ?? false;
//   const completedLabel = gameState?.completedLabel ?? null;

//   // ── WebSocket ───────────────────────────────────────────────────────────────
//   useEffect(() => {
//     const ws = new WebSocket("ws://127.0.0.1:8000/ws");
//     wsRef.current = ws;

//     ws.onopen  = () => setWsReady(true);
//     ws.onclose = () => setWsReady(false);
//     ws.onerror = (e) => console.warn("WS error", e);

//     ws.onmessage = (event) => {
//       const data = JSON.parse(event.data);
//       setGameState(data);
//       if (typeof data.points       === "number") setPoints(data.points);
//       if (typeof data.holdProgress === "number") setHoldProgress(data.holdProgress);
//       if (data.pred !== undefined) setPred(data.pred);
//       if (data.top3 !== undefined) setTop3(data.top3);
//     };

//     return () => ws.close();
//   }, []);

//   // ── Sync house points ───────────────────────────────────────────────────────
//   useEffect(() => {
//     if (!gameState) return;
//     const delta = (gameState.points ?? 0) - prevPointsRef.current;
//     if (delta > 0) {
//       addHousePoints(delta);
//       prevPointsRef.current = gameState.points;
//     }
//   }, [gameState, addHousePoints]);

//   // ── Helpers ─────────────────────────────────────────────────────────────────
//   const send = (msg) => {
//     if (wsRef.current?.readyState === WebSocket.OPEN)
//       wsRef.current.send(JSON.stringify(msg));
//   };

//   const start = () => {
//     if (!wsReady) return;
//     prevPointsRef.current = 0;
//     setPred(null); setTop3(""); setHoldProgress(0); setPoints(0);
//     send({ type: "set_sentence", sentence });
//   };

//   const goNext = () => send({ type: "next_step" });

//   const targetLabel = useMemo(() => {
//     if (!target) return done ? "All done! 🎉" : "(press Start)";
//     const label = target.label ?? target.text;
//     return target.kind === "letter" ? `Letter: ${label}` : `Word: ${label}`;
//   }, [target, done]);

//   const stepText = gameState?.total
//     ? `Step ${Math.min((gameState.currentIndex ?? 0) + 1, gameState.total)} / ${gameState.total}`
//     : "—";

//   // What the backend expects vs what it sees — shown in debug strip
//   const expectedLabel = target?.label ?? null;
//   const predMatchesExpected = pred && expectedLabel
//     && pred.trim().toUpperCase() === expectedLabel.trim().toUpperCase();

//   return (
//     <div className="grid">

//       {/* ── Left: camera ──────────────────────────────────────────────────── */}
//       <div className="card">
//         <h3>Your Camera</h3>
//         <div className="mockVideo" style={{ padding: 0 }}>
//           <img
//             src="http://127.0.0.1:8000/video"
//             alt="Live Camera"
//             style={{ width: "100%", borderRadius: 12, display: "block" }}
//           />
//         </div>
//         <div className="small" style={{ marginTop: 6 }}>
//           Buffer: {gameState?.buffer ?? 0} / {gameState?.seqLen ?? 45}
//           {!wsReady && (
//             <span style={{ color: "tomato", marginLeft: 8 }}>⚠ WS disconnected</span>
//           )}
//         </div>

//         {/* ── Debug strip (toggle with button) ──────────────────────────── */}
//         <div style={{ marginTop: 10 }}>
//           <button
//             onClick={() => setShowDebug(v => !v)}
//             style={{
//               fontSize: "0.7rem", padding: "4px 10px", borderRadius: 8,
//               border: "1px solid rgba(34,26,51,0.2)", background: "rgba(255,255,255,0.6)",
//               cursor: "pointer", color: "var(--ink)",
//             }}
//           >
//             {showDebug ? "Hide" : "Show"} debug
//           </button>

//           {showDebug && (
//             <div style={{
//               marginTop: 8, padding: "10px 12px", borderRadius: 12,
//               background: "rgba(34,26,51,0.08)", fontSize: "0.72rem",
//               lineHeight: 1.7, fontFamily: "monospace", color: "var(--ink)",
//             }}>
//               <div><b>WS:</b> {wsReady ? "✅ connected" : "❌ disconnected"}</div>
//               <div><b>Queue length:</b> {gameState?.total ?? 0}</div>
//               <div><b>Current idx:</b> {gameState?.currentIndex ?? "—"}</div>
//               <div>
//                 <b>Target kind:</b>{" "}
//                 <span style={{ color: target?.kind === "letter" ? "green" : "darkorange" }}>
//                   {target?.kind ?? "none (not started)"}
//                 </span>
//               </div>
//               <div><b>Expected label:</b> {JSON.stringify(expectedLabel)}</div>
//               <div><b>Model pred:</b> {JSON.stringify(pred)}</div>
//               <div>
//                 <b>Labels match:</b>{" "}
//                 <span style={{ color: predMatchesExpected ? "green" : "crimson", fontWeight: "bold" }}>
//                   {expectedLabel === null ? "n/a" : predMatchesExpected ? "✅ YES" : "❌ NO"}
//                 </span>
//               </div>
//               <div><b>Hold progress:</b> {Math.round((holdProgress ?? 0) * 100)}%</div>
//               <div><b>waitingForNext:</b> {String(waitingForNext)}</div>
//               <div><b>Points:</b> {points}</div>
//               <div style={{ marginTop: 4, color: "dimgray" }}>
//                 Check backend terminal for per-second comparison logs.
//                 <br />Also visit <a href="http://127.0.0.1:8000/debug" target="_blank" rel="noreferrer">/debug</a> in your browser.
//               </div>
//             </div>
//           )}
//         </div>
//       </div>

//       {/* ── Right: practice ───────────────────────────────────────────────── */}
//       <div className="card">
//         <h3>Practice</h3>

//         {/* Input */}
//         <div className="row">
//           <input
//             className="input"
//             value={sentence}
//             onChange={(e) => setSentence(e.target.value)}
//             placeholder="Type a sentence to sign..."
//           />
//           <button className="btn" onClick={start} disabled={!wsReady}>
//             Start
//           </button>
//         </div>

//         {/* Step info */}
//         <div className="target">
//           <div><b>Current:</b> {targetLabel}</div>
//           <div className="small">{stepText}</div>
//           <div className="small">
//             House scoring:{" "}
//             {houseKey === "default" ? "Choose a House to contribute points" : "ON ✅"}
//           </div>
//           <div className="small">Session points: <b>{points}</b></div>
//         </div>

//         {/* ── Success banner ─────────────────────────────────────────────── */}
//         {waitingForNext && (
//           <div className="successBox">
//             <div className="successEmoji">✨</div>
//             <div className="successTitle">Correct!</div>
//             <div className="successSub">
//               You signed <b>{completedLabel}</b> perfectly. +10 pts!
//             </div>
//             <button className="btn successBtn" onClick={goNext}>
//               Next →
//             </button>
//           </div>
//         )}

//         {/* ── Live pred — always visible except during success pause ───────── */}
//         {!waitingForNext && (
//           <div className="checkBox" style={{ marginTop: 12 }}>
//             <div className="pred">
//               <b>Live Pred:</b>{" "}
//               <span style={{ color: predMatchesExpected ? "green" : "inherit" }}>
//                 {pred ?? "…"}
//               </span>
//               {predMatchesExpected && (
//                 <span style={{ marginLeft: 8, fontSize: "0.8em" }}>✅</span>
//               )}
//             </div>
//             {top3 && <div className="small">{top3}</div>}

//             <div className="progressWrap">
//               <div className="progressBar">
//                 <div
//                   className="progressFill"
//                   style={{ width: `${Math.round((holdProgress ?? 0) * 100)}%` }}
//                 />
//               </div>
//               <div className="small">
//                 {target?.kind === "letter" && predMatchesExpected
//                   ? `Hold "${target.label}" steady: ${Math.round((holdProgress ?? 0) * 100)}%`
//                   : target?.kind === "letter"
//                   ? `Sign "${target?.label ?? "?"}" — Hold: ${Math.round((holdProgress ?? 0) * 100)}%`
//                   : `Hold: ${Math.round((holdProgress ?? 0) * 100)}%`
//                 }
//               </div>
//             </div>
//           </div>
//         )}

//         {/* ── Word: show video + next button ───────────────────────────────── */}
//         {target?.kind === "word" && !waitingForNext && (
//           <div className="wordBox">
//             <div className="small">Watch the sign, then click Next ↓</div>
//             <div className="videoMock" style={{ padding: 0, overflow: "hidden" }}>
//               <video
//                 key={target.video}
//                 src={target.video}
//                 controls autoPlay muted loop playsInline
//                 style={{ width: "100%", display: "block", borderRadius: 16 }}
//                 onError={() => console.warn("Video not found:", target.video)}
//               />
//             </div>
//             <button className="btn" onClick={goNext} style={{ marginTop: 10 }}>
//               I watched it → Next
//             </button>
//           </div>
//         )}

//         {/* ── Done ─────────────────────────────────────────────────────────── */}
//         {done && (
//           <div className="done">
//             ✅ Finished! Session points: <b>{points}</b>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// }


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




        {/* <div className="small">
          Buffer: {gameState?.buffer ?? "—"} / {gameState?.seqLen ?? "—"}
        </div> */}
        {(() => {
            const buf = gameState?.buffer ?? 0;
            const len = gameState?.seqLen ?? 1;
            const pct = Math.max(0, Math.min(100, Math.round((buf / len) * 100)));

            return (
                <div className="bufferUI">
                <div className="bufferTop">
                    <span className="bufferLabel">Casting meter</span>
                    <span className="bufferPct">{pct}%</span>
                </div>

                <div className="bufferBar" aria-label={`Buffer ${pct}%`}>
                    <div className="bufferFill" style={{ width: `${pct}%` }} />
                </div>

                <div className="bufferHint">
                    {buf} / {len} frames
                </div>
                </div>
            );
            })()}
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
            <div>Current {targetLabel}</div>
            <div className="small">
                Step {gameState?.total ? Math.min((gameState?.currentIndex ?? 0) + 1, gameState.total) : 0} / {gameState?.total ?? 0}
            </div>
            <div className="small">
                House scoring: {houseKey === "default" ? "Choose a House to contribute points" : "ON ✅"}
            </div>
            <div className="small">Session points: <b>{points}</b></div>
            </div>
            <div className="checkBox" style={{ marginTop: 12 }}>
                <div className="pred"><b>Live Prediction:</b> {pred ?? "..."}</div>
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
                {/* your word UI */}
            </div>
            ) : target?.kind === "letter" && !done ? (
            <div className="checkBox">
                <div className="pred"><b>Pred:</b> {pred ?? "..."}</div>
                <div className="small">{top3}</div>

                <div className="progressWrap">
                <div className="progressBar">
                    <div
                    className="progressFill"
                    style={{ width: `${Math.round(holdProgress * 100)}%` }}
                    />
                </div>
                <div className="small">
                    Hold correct sign: {Math.round(holdProgress * 100)}%
                </div>
                </div>
            </div>
            ) : null}




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



