import { createContext, useContext, useEffect, useMemo, useState } from "react";

const HOUSE_THEMES = {
  gryffindor: { name: "Gryffindor", primary: "#7F0909", accent: "#FFC500" },
  slytherin: { name: "Slytherin", primary: "#0D6217", accent: "#AAAAAA" },
  hufflepuff:{ name: "Hufflepuff", primary: "#ECB939", accent: "#372E29" },
  ravenclaw: { name: "Ravenclaw", primary: "#0E1A40", accent: "#946B2D" },
  default:   { name: "Wanderer", primary: "#6D28D9", accent: "#A78BFA" }, // magical purple
};

const AppContext = createContext(null);

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function AppProvider({ children }) {
  const [playerName, setPlayerName] = useState(() => localStorage.getItem("playerName") || "Player");
  const [houseKey, setHouseKey] = useState(() => localStorage.getItem("houseKey") || "default");

  // house points leaderboard
  const [housePoints, setHousePoints] = useState(() =>
    readJSON("housePoints", {
      gryffindor: 120,
      slytherin: 90,
      hufflepuff: 60,
      ravenclaw: 80,
    })
  );

  useEffect(() => localStorage.setItem("playerName", playerName), [playerName]);
  useEffect(() => localStorage.setItem("houseKey", houseKey), [houseKey]);
  useEffect(() => localStorage.setItem("housePoints", JSON.stringify(housePoints)), [housePoints]);

  // Apply theme via CSS variables on <html>
  useEffect(() => {
    const t = HOUSE_THEMES[houseKey] || HOUSE_THEMES.default;
    document.documentElement.style.setProperty("--primary", t.primary);
    document.documentElement.style.setProperty("--accent", t.accent);
  }, [houseKey]);

  const house = useMemo(() => HOUSE_THEMES[houseKey] || HOUSE_THEMES.default, [houseKey]);

  const addHousePoints = (delta) => {
    // If player never chose, send points to default? (we’ll keep default as “Wanderer”, but not in leaderboard)
    // Better: if default, do nothing or prompt to choose. We’ll still allow but not count.
    if (houseKey === "default") return;
    setHousePoints((prev) => ({ ...prev, [houseKey]: (prev[houseKey] || 0) + delta }));
  };

  const value = {
    playerName, setPlayerName,
    houseKey, setHouseKey,
    house,
    housePoints, addHousePoints,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used inside AppProvider");
  return ctx;
}