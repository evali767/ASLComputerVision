import { useNavigate } from "react-router-dom";
import { useAppState } from "../state/AppState";

const HOUSES = [
  { key: "gryffindor", title: "Gryffindor", desc: "Bravery • Daring • Nerve" },
  { key: "slytherin",  title: "Slytherin",  desc: "Ambition • Cunning • Resourcefulness" },
  { key: "hufflepuff", title: "Hufflepuff", desc: "Loyalty • Patience • Fairness" },
  { key: "ravenclaw",  title: "Ravenclaw",  desc: "Wisdom • Wit • Learning" },
];

export default function Home() {
  const nav = useNavigate();
  const { playerName, setPlayerName, houseKey, setHouseKey, house } = useAppState();

  return (
    <div className="card">
      <h3>Welcome to ASL Spellcaster ✨</h3>
      <p className="small">
        Learn ASL letters and phrases with camera vision. Earn points for accurate signing —
        your points power up your House in the House Cup leaderboard.
      </p>

      <div className="row" style={{ marginTop: 10 }}>
        <input
          className="input"
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
          placeholder="Your name"
        />
        <button className="btn" onClick={() => nav("/learn")}>
          Start Learning
        </button>
      </div>

      <div className="divider" />

      <h4 style={{ marginBottom: 6 }}>Choose your House</h4>
      <div className="houses">
        {HOUSES.map((h) => (
          <button
            key={h.key}
            className={`houseCard ${houseKey === h.key ? "selected" : ""}`}
            onClick={() => setHouseKey(h.key)}
          >
            <div className="houseTitle">{h.title}</div>
            <div className="small">{h.desc}</div>
          </button>
        ))}
      </div>

      <div className="small" style={{ marginTop: 10 }}>
        Current theme: <b>{house.name}</b>. (If you don’t choose, you’ll stay in magical purple.)
      </div>
    </div>
  );
}