import { useMemo } from "react";
import { useAppState } from "../state/AppState";

export default function Leaderboard() {
  const { housePoints } = useAppState();

  const rows = useMemo(() => {
    const entries = Object.entries(housePoints).map(([k, v]) => ({ key: k, points: v }));
    entries.sort((a, b) => b.points - a.points);
    return entries;
  }, [housePoints]);

  return (
    <div className="card">
      <h3>House Cup Leaderboard 🏆</h3>
      <p className="small">Points earned by ASL learning sessions.</p>

      <ol className="lb">
        {rows.map((r) => (
          <li key={r.key}>
            <span className="cap">{pretty(r.key)}</span>
            <b>{r.points}</b>
          </li>
        ))}
      </ol>

      <div className="small" style={{ marginTop: 10 }}>
        Tip: earn points in “Learn” and watch your House climb.
      </div>
    </div>
  );
}

function pretty(k) {
  return k.charAt(0).toUpperCase() + k.slice(1);
}